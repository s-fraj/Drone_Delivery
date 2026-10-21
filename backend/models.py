from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base
import enum

class OrderStatus(str, enum.Enum):
    pending    = "pending"     # order created, not paid yet
    confirmed  = "confirmed"   # paid; waiting to be handed to the drone fleet
    dispatched = "dispatched"  # mission created on the drone service (queued or drone assigned)
    in_transit = "in_transit"  # drone is airborne (pickup or delivery leg)
    delivered  = "delivered"   # mission completed
    cancelled  = "cancelled"

class PaymentStatus(str, enum.Enum):
    unpaid = "unpaid"
    paid   = "paid"
    failed = "failed"

class User(Base):
    __tablename__ = "users"

    id         = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=False)
    last_name  = Column(String(100), nullable=False)
    email      = Column(String(255), unique=True, index=True, nullable=False)
    phone      = Column(String(30))
    password   = Column(String(255), nullable=False)
    is_admin   = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    orders    = relationship("Order", back_populates="user")
    locations = relationship("SavedLocation", back_populates="user")


class Order(Base):
    __tablename__ = "orders"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    pickup_address  = Column(String(500), nullable=False)
    dropoff_address = Column(String(500), nullable=False)
    # Required (not nullable): the drone fleet cannot be dispatched without real coordinates.
    pickup_lat      = Column(Float, nullable=False)
    pickup_lng      = Column(Float, nullable=False)
    dropoff_lat     = Column(Float, nullable=False)
    dropoff_lng     = Column(Float, nullable=False)
    # Additional stops beyond the primary drop-off above, for a multi-stop
    # delivery — [{"lat":, "lng":, "address":}, ...]. Empty/null for a
    # normal single-stop order (the common case).
    extra_dropoffs  = Column(JSON, nullable=True)
    package_weight  = Column(Float, nullable=False)         # kg
    package_desc    = Column(String(500))
    recipient_name  = Column(String(200))
    recipient_phone = Column(String(30))
    notes           = Column(Text)
    price           = Column(Float, nullable=False)
    status          = Column(Enum(OrderStatus), default=OrderStatus.pending)
    payment_status  = Column(Enum(PaymentStatus), default=PaymentStatus.unpaid)
    created_at      = Column(DateTime, default=datetime.utcnow)
    estimated_delivery = Column(DateTime)
    rating          = Column(Integer, nullable=True)   # 1-5, set by the customer after delivery
    rating_comment  = Column(Text, nullable=True)

    user     = relationship("User", back_populates="orders")
    tracking = relationship("DroneTracking", back_populates="order", uselist=False)
    payment  = relationship("Payment", back_populates="order", uselist=False)


class DroneTracking(Base):
    """
    Mirrors the state of the mission on the Python/MAVLink drone service.
    We only store what that service actually reports (mission_id, status
    text, assigned drone, queue position, error) — no fabricated GPS/
    battery/speed values, since the drone service does not expose live
    telemetry, only mission status.
    """
    __tablename__ = "drone_tracking"

    id             = Column(Integer, primary_key=True)
    order_id       = Column(Integer, ForeignKey("orders.id"), unique=True)
    mission_id     = Column(String(64))                 # id returned by the drone service
    drone_number   = Column(String(20))                  # fleet drone key, e.g. "1"
    mission_status = Column(String(50), default="Not dispatched")
    queue_position = Column(Integer)
    error_message  = Column(Text)
    distance_km    = Column(Float)                       # live distance to next waypoint — customer-safe (no raw coords)
    stops_total    = Column(Integer)                     # total drop-offs on this mission (1 for a normal order)
    stops_done     = Column(Integer)                      # how many of those have been delivered so far
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    order = relationship("Order", back_populates="tracking")


class Payment(Base):
    __tablename__ = "payments"

    id             = Column(Integer, primary_key=True)
    order_id       = Column(Integer, ForeignKey("orders.id"), unique=True)
    amount         = Column(Float, nullable=False)
    card_last4     = Column(String(4))
    card_brand     = Column(String(20))
    status         = Column(String(20), default="succeeded")
    transaction_id = Column(String(100))
    paid_at        = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="payment")


class SavedLocation(Base):
    __tablename__ = "saved_locations"

    id      = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    label   = Column(String(50))          # e.g. "Home", "Office"
    address = Column(String(500))
    lat     = Column(Float)
    lng     = Column(Float)

    user = relationship("User", back_populates="locations")


class AdminAuditLog(Base):
    """A record of admin-only actions (status overrides, aborts, retries,
    pause/emergency-stop toggles) — who did what, and when."""
    __tablename__ = "admin_audit_log"

    id         = Column(Integer, primary_key=True)
    admin_id   = Column(Integer, ForeignKey("users.id"), nullable=False)
    action     = Column(String(100), nullable=False)   # e.g. "abort_order", "set_status", "emergency_stop"
    details    = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    admin = relationship("User")

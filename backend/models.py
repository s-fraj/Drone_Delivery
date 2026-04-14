from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base
import enum

class OrderStatus(str, enum.Enum):
    pending    = "pending"
    confirmed  = "confirmed"
    dispatched = "dispatched"
    in_transit = "in_transit"
    delivered  = "delivered"
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
    created_at = Column(DateTime, default=datetime.utcnow)

    orders    = relationship("Order", back_populates="user")
    locations = relationship("SavedLocation", back_populates="user")


class Order(Base):
    __tablename__ = "orders"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    pickup_address  = Column(String(500), nullable=False)
    dropoff_address = Column(String(500), nullable=False)
    pickup_lat      = Column(Float)
    pickup_lng      = Column(Float)
    dropoff_lat     = Column(Float)
    dropoff_lng     = Column(Float)
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

    user     = relationship("User", back_populates="orders")
    tracking = relationship("DroneTracking", back_populates="order", uselist=False)
    payment  = relationship("Payment", back_populates="order", uselist=False)


class DroneTracking(Base):
    __tablename__ = "drone_tracking"

    id         = Column(Integer, primary_key=True)
    order_id   = Column(Integer, ForeignKey("orders.id"), unique=True)
    drone_id   = Column(String(50), default="DRONE-001")
    current_lat = Column(Float)
    current_lng = Column(Float)
    battery_pct = Column(Integer, default=100)
    altitude_m  = Column(Float, default=0)
    speed_kmh   = Column(Float, default=0)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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

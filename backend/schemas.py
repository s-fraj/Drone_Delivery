from pydantic import BaseModel, EmailStr, model_validator
from typing import Optional
from datetime import datetime
import math
import os

# ── AUTH ──────────────────────────────────────────────────────────────
class UserCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    password: str

class UserOut(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    phone: Optional[str]
    is_admin: bool
    created_at: datetime
    class Config: from_attributes = True

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str

# ── ORDERS ────────────────────────────────────────────────────────────
class ExtraDropoff(BaseModel):
    """An additional stop beyond the order's primary drop-off, for a
    multi-stop delivery (one drone, several destinations)."""
    address: str
    lat: float
    lng: float

class OrderCreate(BaseModel):
    pickup_address: str
    dropoff_address: str
    # Required: the drone fleet needs real GPS coordinates to fly the mission.
    pickup_lat: float
    pickup_lng: float
    dropoff_lat: float
    dropoff_lng: float
    # Extra stops after the primary drop-off above — empty for a normal
    # single-stop order. Order.html lets the customer add these via the
    # same map picker used for pickup/drop-off.
    extra_dropoffs: Optional[list[ExtraDropoff]] = None
    package_weight: float
    package_desc: Optional[str] = None
    recipient_name: Optional[str] = None
    recipient_phone: Optional[str] = None
    notes: Optional[str] = None

    # Wide margin around the fleet's actual home base (see DRONES in
    # delivery-system/python/mission.py) — keeps obviously-wrong input
    # (wrong continent, swapped lat/lng, a map click gone wrong) from
    # being accepted and then failing 15 minutes later as a flight timeout.
    # Configurable via env so the deployed service area isn't locked to code.
    _SERVICE_AREA = {
        "lat_min": float(os.environ.get("SERVICE_AREA_LAT_MIN", "32.5")),
        "lat_max": float(os.environ.get("SERVICE_AREA_LAT_MAX", "34.5")),
        "lng_min": float(os.environ.get("SERVICE_AREA_LNG_MIN", "9.5")),
        "lng_max": float(os.environ.get("SERVICE_AREA_LNG_MAX", "11.5")),
    }
    _MAX_LEG_KM = float(os.environ.get("MAX_LEG_KM", "12.0"))
    _MAX_ROUTE_KM = float(os.environ.get("MAX_ROUTE_KM", "20.0"))  # total pickup→stop1→stop2→... distance

    @staticmethod
    def _haversine_km(lat1, lon1, lat2, lon2):
        R = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @model_validator(mode="after")
    def _validate_coordinates(self):
        b = self._SERVICE_AREA
        stops = [("Pickup", self.pickup_lat, self.pickup_lng),
                 ("Drop-off", self.dropoff_lat, self.dropoff_lng)]
        for i, d in enumerate(self.extra_dropoffs or [], start=2):
            stops.append((f"Drop-off #{i}", d.lat, d.lng))

        for label, lat, lng in stops:
            if not (b["lat_min"] <= lat <= b["lat_max"] and b["lng_min"] <= lng <= b["lng_max"]):
                raise ValueError(f"{label} location is outside our drone service area")

        # Total route: pickup -> dropoff -> extra_dropoffs in order.
        route = [(self.pickup_lat, self.pickup_lng), (self.dropoff_lat, self.dropoff_lng)]
        route += [(d.lat, d.lng) for d in (self.extra_dropoffs or [])]
        total_km = sum(
            self._haversine_km(*route[i], *route[i + 1]) for i in range(len(route) - 1)
        )
        cap = self._MAX_LEG_KM if not self.extra_dropoffs else self._MAX_ROUTE_KM
        if total_km > cap:
            raise ValueError(
                f"This route is {total_km:.1f} km total — our drones have a {cap:.0f} km range per trip"
            )
        return self

class OrderOut(BaseModel):
    id: int
    pickup_address: str
    dropoff_address: str
    pickup_lat: float
    pickup_lng: float
    dropoff_lat: float
    dropoff_lng: float
    extra_dropoffs: Optional[list[ExtraDropoff]] = None
    package_weight: float
    package_desc: Optional[str]
    recipient_name: Optional[str]
    recipient_phone: Optional[str]
    notes: Optional[str]
    price: float
    status: str
    payment_status: str
    created_at: datetime
    estimated_delivery: Optional[datetime]
    rating: Optional[int] = None
    rating_comment: Optional[str] = None
    class Config: from_attributes = True

class RatingIn(BaseModel):
    rating: int   # 1-5
    comment: Optional[str] = None

    @model_validator(mode="after")
    def _validate_rating(self):
        if not (1 <= self.rating <= 5):
            raise ValueError("Rating must be between 1 and 5")
        return self

# ── TRACKING ──────────────────────────────────────────────────────────
class TrackingInfo(BaseModel):
    order_id: int
    mission_id: Optional[str]
    drone_number: Optional[str]
    mission_status: str
    queue_position: Optional[int]
    error_message: Optional[str]
    distance_km: Optional[float]
    stops_total: Optional[int] = None
    stops_done: Optional[int] = None
    updated_at: Optional[datetime]
    class Config: from_attributes = True

# ── PAYMENT ───────────────────────────────────────────────────────────
class PaymentIn(BaseModel):
    card_number: str       # will only store last 4
    card_expiry: str       # MM/YY
    card_cvc: str
    card_holder: str

class PaymentOut(BaseModel):
    id: int
    order_id: int
    amount: float
    card_last4: str
    card_brand: str
    status: str
    transaction_id: str
    paid_at: datetime
    class Config: from_attributes = True

# ── LOCATIONS ─────────────────────────────────────────────────────────
class LocationCreate(BaseModel):
    label: str
    address: str
    lat: Optional[float] = None
    lng: Optional[float] = None

class LocationOut(BaseModel):
    id: int
    label: str
    address: str
    lat: Optional[float]
    lng: Optional[float]
    class Config: from_attributes = True

# ── ADMIN ─────────────────────────────────────────────────────────────
class AdminOrderOut(OrderOut):
    user_id: int
    user_name: str
    user_email: str
    tracking: Optional[TrackingInfo] = None

class AdminStatusUpdate(BaseModel):
    status: str

class ServiceStatusOut(BaseModel):
    accepting_orders: bool
    message: Optional[str] = None

class ServiceStatusUpdate(BaseModel):
    accepting_orders: bool
    message: Optional[str] = None

class EmergencyStopIn(BaseModel):
    message: Optional[str] = None

class AuditLogOut(BaseModel):
    id: int
    admin_id: int
    admin_name: Optional[str] = None
    action: str
    details: Optional[str]
    created_at: datetime
    class Config: from_attributes = True

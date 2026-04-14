from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

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
class OrderCreate(BaseModel):
    pickup_address: str
    dropoff_address: str
    pickup_lat: Optional[float] = None
    pickup_lng: Optional[float] = None
    dropoff_lat: Optional[float] = None
    dropoff_lng: Optional[float] = None
    package_weight: float
    package_desc: Optional[str] = None
    recipient_name: Optional[str] = None
    recipient_phone: Optional[str] = None
    notes: Optional[str] = None

class OrderOut(BaseModel):
    id: int
    pickup_address: str
    dropoff_address: str
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
    class Config: from_attributes = True

class StatusUpdate(BaseModel):
    status: str

# ── TRACKING ──────────────────────────────────────────────────────────
class TrackingInfo(BaseModel):
    order_id: int
    drone_id: str
    current_lat: Optional[float]
    current_lng: Optional[float]
    battery_pct: Optional[int]
    altitude_m: Optional[float]
    speed_kmh: Optional[float]
    updated_at: Optional[datetime]
    class Config: from_attributes = True

class TrackingUpdate(BaseModel):
    drone_id: Optional[str] = None
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None
    battery_pct: Optional[int] = None
    altitude_m: Optional[float] = None
    speed_kmh: Optional[float] = None

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

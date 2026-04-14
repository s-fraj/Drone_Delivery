from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import models, schemas, auth
import uuid, math

# ── PRICING FORMULA ───────────────────────────────────────────────────
def calculate_price(weight_kg: float, pickup_lat=None, pickup_lng=None,
                    dropoff_lat=None, dropoff_lng=None) -> float:
    base = 5.0
    weight_cost = weight_kg * 2.5
    distance_cost = 0
    if all([pickup_lat, pickup_lng, dropoff_lat, dropoff_lng]):
        # Haversine distance in km
        R = 6371
        dlat = math.radians(dropoff_lat - pickup_lat)
        dlng = math.radians(dropoff_lng - pickup_lng)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(pickup_lat)) * \
            math.cos(math.radians(dropoff_lat)) * math.sin(dlng/2)**2
        distance_km = R * 2 * math.asin(math.sqrt(a))
        distance_cost = distance_km * 0.5
    return round(base + weight_cost + distance_cost, 2)

# ── USERS ─────────────────────────────────────────────────────────────
def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed = auth.hash_password(user.password)
    db_user = models.User(
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        phone=user.phone,
        password=hashed
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, user_id: int, updates: schemas.UserUpdate):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    for field, value in updates.dict(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user

# ── ORDERS ────────────────────────────────────────────────────────────
def create_order(db: Session, order: schemas.OrderCreate, user_id: int):
    price = calculate_price(
        order.package_weight,
        order.pickup_lat, order.pickup_lng,
        order.dropoff_lat, order.dropoff_lng
    )
    eta = datetime.utcnow() + timedelta(hours=1, minutes=30)
    db_order = models.Order(
        user_id=user_id,
        price=price,
        estimated_delivery=eta,
        **order.dict()
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    # Create initial tracking record
    tracking = models.DroneTracking(
        order_id=db_order.id,
        current_lat=order.pickup_lat,
        current_lng=order.pickup_lng
    )
    db.add(tracking)
    db.commit()
    return db_order

def get_order(db: Session, order_id: int):
    return db.query(models.Order).filter(models.Order.id == order_id).first()

def get_orders_by_user(db: Session, user_id: int):
    return db.query(models.Order).filter(
        models.Order.user_id == user_id
    ).order_by(models.Order.created_at.desc()).all()

def update_order_status(db: Session, order_id: int, status: str):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if order:
        order.status = status
        db.commit()
        db.refresh(order)
    return order

# ── TRACKING ──────────────────────────────────────────────────────────
def get_tracking(db: Session, order_id: int):
    return db.query(models.DroneTracking).filter(
        models.DroneTracking.order_id == order_id
    ).first()

def update_tracking(db: Session, order_id: int, data: schemas.TrackingUpdate):
    t = db.query(models.DroneTracking).filter(
        models.DroneTracking.order_id == order_id
    ).first()
    if not t:
        t = models.DroneTracking(order_id=order_id)
        db.add(t)
    for field, value in data.dict(exclude_unset=True).items():
        setattr(t, field, value)
    t.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(t)
    return t

# ── PAYMENT ───────────────────────────────────────────────────────────
def process_payment(db: Session, order_id: int, payment: schemas.PaymentIn):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    # Simulate card brand detection
    num = payment.card_number.replace(" ", "")
    brand = "Visa" if num.startswith("4") else \
            "Mastercard" if num.startswith("5") else \
            "Amex" if num.startswith("3") else "Card"
    txn_id = str(uuid.uuid4()).upper()[:16]
    db_payment = models.Payment(
        order_id=order_id,
        amount=order.price,
        card_last4=num[-4:],
        card_brand=brand,
        status="succeeded",
        transaction_id=txn_id
    )
    db.add(db_payment)
    order.payment_status = models.PaymentStatus.paid
    order.status = models.OrderStatus.confirmed
    db.commit()
    db.refresh(db_payment)
    return db_payment

# ── LOCATIONS ─────────────────────────────────────────────────────────
def get_locations(db: Session, user_id: int):
    return db.query(models.SavedLocation).filter(
        models.SavedLocation.user_id == user_id
    ).all()

def add_location(db: Session, loc: schemas.LocationCreate, user_id: int):
    db_loc = models.SavedLocation(user_id=user_id, **loc.dict())
    db.add(db_loc)
    db.commit()
    db.refresh(db_loc)
    return db_loc

def delete_location(db: Session, loc_id: int, user_id: int):
    loc = db.query(models.SavedLocation).filter(
        models.SavedLocation.id == loc_id,
        models.SavedLocation.user_id == user_id
    ).first()
    if loc:
        db.delete(loc)
        db.commit()

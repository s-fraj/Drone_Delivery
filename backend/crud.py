from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import models, schemas, auth
import uuid, math

# ── PRICING FORMULA ───────────────────────────────────────────────────
def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * \
        math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))

EXTRA_STOP_FEE = 3.0  # flat fee per additional drop-off beyond the first

def calculate_price(weight_kg: float, pickup_lat: float, pickup_lng: float,
                    dropoff_lat: float, dropoff_lng: float,
                    extra_dropoffs: list = None) -> float:
    base = 5.0
    weight_cost = weight_kg * 2.5

    route = [(pickup_lat, pickup_lng), (dropoff_lat, dropoff_lng)]
    for d in (extra_dropoffs or []):
        # d may be an ExtraDropoff pydantic model or a plain dict, depending on caller.
        lat = d.lat if hasattr(d, "lat") else d["lat"]
        lng = d.lng if hasattr(d, "lng") else d["lng"]
        route.append((lat, lng))

    total_distance_km = sum(
        _haversine_km(*route[i], *route[i + 1]) for i in range(len(route) - 1)
    )
    distance_cost = total_distance_km * 0.5
    stop_fee = EXTRA_STOP_FEE * len(extra_dropoffs or [])
    return round(base + weight_cost + distance_cost + stop_fee, 2)

# ── USERS ─────────────────────────────────────────────────────────────
def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed = auth.hash_password(user.password)
    # The very first account created on a fresh install becomes the admin,
    # so there's always at least one admin without needing a separate
    # seeding script or a hardcoded superuser.
    is_first_user = db.query(models.User).count() == 0
    db_user = models.User(
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        phone=user.phone,
        password=hashed,
        is_admin=is_first_user,
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

def get_all_users(db: Session):
    return db.query(models.User).order_by(models.User.created_at.desc()).all()

# ── ORDERS ────────────────────────────────────────────────────────────
def create_order(db: Session, order: schemas.OrderCreate, user_id: int):
    price = calculate_price(
        order.package_weight,
        order.pickup_lat, order.pickup_lng,
        order.dropoff_lat, order.dropoff_lng,
        extra_dropoffs=order.extra_dropoffs,
    )
    eta = datetime.utcnow() + timedelta(hours=1, minutes=30)
    order_data = order.dict()
    db_order = models.Order(
        user_id=user_id,
        price=price,
        estimated_delivery=eta,
        **order_data
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    # Create the (empty, not-yet-dispatched) tracking record up front so the
    # frontend always has something to read from /orders/{id}/track.
    stops_total = 1 + len(order.extra_dropoffs or [])
    tracking = models.DroneTracking(order_id=db_order.id, mission_status="Not dispatched",
                                     stops_total=stops_total, stops_done=0)
    db.add(tracking)
    db.commit()
    return db_order

def get_order(db: Session, order_id: int):
    return db.query(models.Order).filter(models.Order.id == order_id).first()

def get_orders_by_user(db: Session, user_id: int):
    return db.query(models.Order).filter(
        models.Order.user_id == user_id
    ).order_by(models.Order.created_at.desc()).all()

def get_all_orders(db: Session):
    return db.query(models.Order).order_by(models.Order.created_at.desc()).all()

def get_active_orders_with_missions(db: Session):
    """Orders that have an in-flight mission_id and haven't reached a final state."""
    return (
        db.query(models.Order)
        .join(models.DroneTracking)
        .filter(
            models.DroneTracking.mission_id.isnot(None),
            models.Order.status.notin_([models.OrderStatus.delivered, models.OrderStatus.cancelled]),
        )
        .all()
    )

def set_order_status(db: Session, order_id: int, status: str):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if order:
        order.status = status
        db.commit()
        db.refresh(order)
    return order

# ── TRACKING ──────────────────────────────────────────────────────────
def get_tracking(db: Session, order_id: int):
    t = db.query(models.DroneTracking).filter(
        models.DroneTracking.order_id == order_id
    ).first()
    if not t:
        t = models.DroneTracking(order_id=order_id, mission_status="Not dispatched")
        db.add(t)
        db.commit()
        db.refresh(t)
    return t

def set_mission(db: Session, order_id: int, mission_id: str, mission_status: str,
                 drone_number: str = None, queue_position: int = None, error_message: str = None,
                 distance_km: float = None, stops_total: int = None, stops_done: int = None):
    t = get_tracking(db, order_id)
    t.mission_id = mission_id
    t.mission_status = mission_status
    t.drone_number = drone_number
    t.queue_position = queue_position
    t.error_message = error_message
    t.distance_km = distance_km
    if stops_total is not None:
        t.stops_total = stops_total
    if stops_done is not None:
        t.stops_done = stops_done
    t.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(t)
    return t

def set_rating(db: Session, order_id: int, rating: int, comment: str = None):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if order:
        order.rating = rating
        order.rating_comment = comment
        db.commit()
        db.refresh(order)
    return order

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

# ── ADMIN AUDIT LOG ───────────────────────────────────────────────────
def log_admin_action(db: Session, admin_id: int, action: str, details: str = None):
    entry = models.AdminAuditLog(admin_id=admin_id, action=action, details=details)
    db.add(entry)
    db.commit()
    return entry

def get_audit_log(db: Session, limit: int = 100):
    return (
        db.query(models.AdminAuditLog)
        .order_by(models.AdminAuditLog.created_at.desc())
        .limit(limit)
        .all()
    )

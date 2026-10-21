import asyncio
import logging

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

import models, schemas, crud, auth, drone_bridge, drone_client
from drone_client import DroneServiceError
from database import SessionLocal, engine

logging.basicConfig(level=logging.INFO)

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Drovery API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user = auth.verify_token(token, db)
    if user is None:
        raise credentials_exception
    return user


async def get_current_admin(current_user=Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


@app.on_event("startup")
async def start_background_poller():
    # Keeps every order's status in sync with the real drone missions
    # running on the Flask/MAVLink service, without the frontend having
    # to poll that service directly (and without needing it to expose
    # any auth beyond the one internal API key).
    asyncio.create_task(drone_bridge.poller_loop())


# ── PUBLIC ────────────────────────────────────────────────────────────
@app.get("/public/service-status", response_model=schemas.ServiceStatusOut)
async def public_service_status():
    """No auth — order.html checks this before showing the order form."""
    try:
        state = await drone_client.get_service_state()
        return schemas.ServiceStatusOut(**state)
    except DroneServiceError:
        return schemas.ServiceStatusOut(
            accepting_orders=False,
            message="We're briefly offline for maintenance — please check back shortly."
        )

# ── AUTH ──────────────────────────────────────────────────────────────
@app.post("/auth/signup", response_model=schemas.UserOut, status_code=201)
def signup(user: schemas.UserCreate, db: Session = Depends(get_db)):
    if crud.get_user_by_email(db, user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db, user)

@app.post("/auth/login", response_model=schemas.Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = auth.authenticate_user(db, form.username, form.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    token = auth.create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}

# ── USER ──────────────────────────────────────────────────────────────
@app.get("/users/me", response_model=schemas.UserOut)
def get_me(current_user=Depends(get_current_user)):
    return current_user

@app.put("/users/me", response_model=schemas.UserOut)
def update_me(updates: schemas.UserUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return crud.update_user(db, current_user.id, updates)

# ── ORDERS ────────────────────────────────────────────────────────────
@app.post("/orders", response_model=schemas.OrderOut, status_code=201)
async def create_order(order: schemas.OrderCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    try:
        state = await drone_client.get_service_state()
    except DroneServiceError:
        # Fail safe: if we can't even ask whether the fleet is accepting
        # orders, don't let a customer pay for something we can't dispatch.
        raise HTTPException(status_code=503, detail="We're briefly unable to take new orders — please try again shortly.")
    if not state.get("accepting_orders", True):
        raise HTTPException(status_code=503, detail=state.get("message") or "We're not accepting new orders right now.")
    return crud.create_order(db, order, current_user.id)

@app.get("/orders", response_model=list[schemas.OrderOut])
def get_my_orders(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return crud.get_orders_by_user(db, current_user.id)

@app.get("/orders/{order_id}", response_model=schemas.OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    order = crud.get_order(db, order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.post("/orders/{order_id}/cancel", response_model=schemas.OrderOut)
async def cancel_order(order_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    order = crud.get_order(db, order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status in (models.OrderStatus.delivered, models.OrderStatus.cancelled):
        raise HTTPException(status_code=400, detail="This order can no longer be cancelled")
    try:
        await drone_bridge.cancel_order(db, order)
    except DroneServiceError as e:
        raise HTTPException(status_code=502, detail=f"Could not reach the drone in flight: {e}")
    db.refresh(order)
    return order

@app.post("/orders/{order_id}/rating", response_model=schemas.OrderOut)
def rate_order(order_id: int, rating: schemas.RatingIn, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    order = crud.get_order(db, order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != models.OrderStatus.delivered:
        raise HTTPException(status_code=400, detail="You can only rate a delivered order")
    return crud.set_rating(db, order_id, rating.rating, rating.comment)

# Note: there is no longer a public PUT /orders/{id}/status endpoint.
# The original had none — any client could rewrite any order's status
# with no authentication at all. Status now only ever changes as a
# result of payment (crud.process_payment) or the drone_bridge poller
# reading real mission state, or an authenticated admin override below.

# ── DRONE TRACKING (read-only) ───────────────────────────────────────
@app.get("/orders/{order_id}/track", response_model=schemas.TrackingInfo)
def track_order(order_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    order = crud.get_order(db, order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    tracking = crud.get_tracking(db, order_id)
    result = schemas.TrackingInfo.model_validate(tracking)
    # Customers never see the raw internal exception text (MAVLink/PreArm
    # details etc.) — that stays admin-only via /admin/orders.
    if result.error_message:
        result.error_message = "We're resolving an issue with your delivery."
    return result

# Note: there is no longer a public POST /orders/{id}/track endpoint either.
# Tracking data now comes exclusively from drone_bridge polling the real
# drone service — nothing external can inject fake telemetry into it.

# ── PAYMENT ───────────────────────────────────────────────────────────
@app.post("/orders/{order_id}/pay", response_model=schemas.PaymentOut)
async def process_payment(order_id: int, payment: schemas.PaymentIn, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    order = crud.get_order(db, order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.payment_status == "paid":
        raise HTTPException(status_code=400, detail="Order already paid")
    result = crud.process_payment(db, order_id, payment)
    # Payment succeeded — hand the order to the real drone fleet. If the
    # drone service can't be reached, the payment still stands; the
    # failure is recorded on the tracking row and an admin can retry it.
    db.refresh(order)
    await drone_bridge.dispatch_order(db, order)
    return result

# ── SAVED LOCATIONS ───────────────────────────────────────────────────
@app.get("/locations", response_model=list[schemas.LocationOut])
def get_locations(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return crud.get_locations(db, current_user.id)

@app.post("/locations", response_model=schemas.LocationOut, status_code=201)
def add_location(loc: schemas.LocationCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return crud.add_location(db, loc, current_user.id)

@app.delete("/locations/{loc_id}", status_code=204)
def delete_location(loc_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    crud.delete_location(db, loc_id, current_user.id)

# ── ADMIN ─────────────────────────────────────────────────────────────
def _to_admin_order_out(order: models.Order) -> schemas.AdminOrderOut:
    return schemas.AdminOrderOut(
        **schemas.OrderOut.model_validate(order).model_dump(),
        user_id=order.user_id,
        user_name=f"{order.user.first_name} {order.user.last_name}",
        user_email=order.user.email,
        tracking=schemas.TrackingInfo.model_validate(order.tracking) if order.tracking else None,
    )

@app.get("/admin/orders", response_model=list[schemas.AdminOrderOut])
def admin_list_orders(db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    return [_to_admin_order_out(o) for o in crud.get_all_orders(db)]

@app.get("/admin/orders/{order_id}", response_model=schemas.AdminOrderOut)
def admin_get_order(order_id: int, db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return _to_admin_order_out(order)

@app.put("/admin/orders/{order_id}/status", response_model=schemas.AdminOrderOut)
def admin_set_status(order_id: int, payload: schemas.AdminStatusUpdate, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if payload.status not in [s.value for s in models.OrderStatus]:
        raise HTTPException(status_code=400, detail="Invalid status")
    crud.set_order_status(db, order_id, payload.status)
    crud.log_admin_action(db, admin.id, "set_status", f"Order #{order_id} → {payload.status}")
    db.refresh(order)
    return _to_admin_order_out(order)

@app.post("/admin/orders/{order_id}/retry-dispatch", response_model=schemas.AdminOrderOut)
async def admin_retry_dispatch(order_id: int, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.payment_status != "paid":
        raise HTTPException(status_code=400, detail="Order isn't paid yet")
    await drone_bridge.retry_dispatch(db, order)
    crud.log_admin_action(db, admin.id, "retry_dispatch", f"Order #{order_id}")
    db.refresh(order)
    return _to_admin_order_out(order)

@app.post("/admin/orders/{order_id}/abort", response_model=schemas.AdminOrderOut)
async def admin_abort_order(order_id: int, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status in (models.OrderStatus.delivered, models.OrderStatus.cancelled):
        raise HTTPException(status_code=400, detail="This order is already finished")
    try:
        await drone_bridge.cancel_order(db, order)
    except DroneServiceError as e:
        raise HTTPException(status_code=502, detail=f"Could not reach the drone in flight: {e}")
    crud.log_admin_action(db, admin.id, "abort_order", f"Order #{order_id}")
    db.refresh(order)
    return _to_admin_order_out(order)

@app.get("/admin/users", response_model=list[schemas.UserOut])
def admin_list_users(db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    return crud.get_all_users(db)

@app.get("/admin/fleet")
async def admin_fleet_status(_admin=Depends(get_current_admin)):
    try:
        return await drone_client.get_fleet_status()
    except DroneServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/admin/drone-service-health")
async def admin_drone_health(_admin=Depends(get_current_admin)):
    return {"healthy": await drone_client.is_healthy()}

@app.get("/admin/service-state", response_model=schemas.ServiceStatusOut)
async def admin_get_service_state(_admin=Depends(get_current_admin)):
    try:
        return schemas.ServiceStatusOut(**await drone_client.get_service_state())
    except DroneServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.post("/admin/service-state", response_model=schemas.ServiceStatusOut)
async def admin_set_service_state(payload: schemas.ServiceStatusUpdate, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    try:
        state = await drone_client.set_service_state(payload.accepting_orders, payload.message)
    except DroneServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
    crud.log_admin_action(
        db, admin.id, "pause" if not payload.accepting_orders else "resume",
        payload.message or ""
    )
    return schemas.ServiceStatusOut(**state)

@app.post("/admin/emergency-stop", response_model=schemas.ServiceStatusOut)
async def admin_emergency_stop(payload: schemas.EmergencyStopIn, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    try:
        state = await drone_client.emergency_stop(payload.message)
    except DroneServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
    crud.log_admin_action(db, admin.id, "emergency_stop", state.get("message", ""))
    return schemas.ServiceStatusOut(accepting_orders=state.get("accepting_orders", False),
                                      message=state.get("message"))

@app.get("/admin/audit-log", response_model=list[schemas.AuditLogOut])
def admin_audit_log(db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    entries = crud.get_audit_log(db)
    out = []
    for e in entries:
        out.append(schemas.AuditLogOut(
            id=e.id, admin_id=e.admin_id,
            admin_name=f"{e.admin.first_name} {e.admin.last_name}" if e.admin else None,
            action=e.action, details=e.details, created_at=e.created_at,
        ))
    return out

@app.get("/admin/orders/export")
def admin_export_orders_csv(db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    import csv, io
    from fastapi.responses import Response

    orders = crud.get_all_orders(db)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id", "user_name", "user_email", "pickup_address", "dropoff_address",
        "extra_stops", "price", "status", "payment_status", "rating", "created_at",
    ])
    for o in orders:
        writer.writerow([
            o.id, f"{o.user.first_name} {o.user.last_name}", o.user.email,
            o.pickup_address, o.dropoff_address, len(o.extra_dropoffs or []),
            o.price, o.status.value if hasattr(o.status, "value") else o.status,
            o.payment_status.value if hasattr(o.payment_status, "value") else o.payment_status,
            o.rating or "", o.created_at.isoformat(),
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=orders.csv"},
    )

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
import models, schemas, crud, auth
from database import SessionLocal, engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Drovery API", version="1.0.0")

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
def create_order(order: schemas.OrderCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
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

@app.put("/orders/{order_id}/status", response_model=schemas.OrderOut)
def update_order_status(order_id: int, payload: schemas.StatusUpdate, db: Session = Depends(get_db)):
    # In production, this would be called by the drone system
    order = crud.update_order_status(db, order_id, payload.status)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

# ── DRONE TRACKING ────────────────────────────────────────────────────
@app.get("/orders/{order_id}/track", response_model=schemas.TrackingInfo)
def track_order(order_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    order = crud.get_order(db, order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    return crud.get_tracking(db, order_id)

@app.post("/orders/{order_id}/track", response_model=schemas.TrackingInfo)
def update_tracking(order_id: int, data: schemas.TrackingUpdate, db: Session = Depends(get_db)):
    return crud.update_tracking(db, order_id, data)

# ── PAYMENT ───────────────────────────────────────────────────────────
@app.post("/orders/{order_id}/pay", response_model=schemas.PaymentOut)
def process_payment(order_id: int, payment: schemas.PaymentIn, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    order = crud.get_order(db, order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.payment_status == "paid":
        raise HTTPException(status_code=400, detail="Order already paid")
    return crud.process_payment(db, order_id, payment)

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

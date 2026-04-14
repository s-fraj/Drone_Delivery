# 🚁 Drovery — Drone Delivery Platform

Full-stack drone delivery web app. FastAPI + MySQL backend, plain HTML/CSS/JS frontend.

---

## 📁 Project Structure

```
drovery/
├── backend/
│   ├── main.py              # FastAPI app + all routes
│   ├── database.py          # MySQL connection (SQLAlchemy)
│   ├── models.py            # DB tables: User, Order, DroneTracking, Payment, SavedLocation
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── crud.py              # DB operations + pricing logic
│   ├── auth.py              # JWT auth + bcrypt hashing
│   ├── drone_simulator.py   # Simulates drone movement (run separately)
│   └── requirements.txt
│
└── frontend/
    ├── shared.css           # ← Unified design system (all pages use this)
    ├── api.js               # ← Shared fetch wrapper + token management
    ├── func.js              # ← Counter animation
    ├── index.html           # Home page
    ├── style.css            # Home page extra styles
    ├── login.html           # Login
    ├── signup.html          # Sign up
    ├── order.html           # New order form + card payment
    ├── profile.html         # User dashboard + order history + live tracking
    ├── services.html        # Services + pricing table
    ├── about_us.html        # About page
    └── contact.html         # Contact page + form
```

---

## ⚙️ Backend Setup

### 1. Create MySQL database
```sql
CREATE DATABASE drovery CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2. Configure credentials
Edit `backend/database.py` or set environment variables:
```bash
export DB_USER=root
export DB_PASSWORD=yourpassword
export DB_HOST=localhost
export DB_PORT=3306
export DB_NAME=drovery
export SECRET_KEY=your-random-secret-key
```

### 3. Install dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 4. Run the server
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API docs available at: http://localhost:8000/docs

---

## 🌐 Frontend Setup

No build step needed — pure HTML/CSS/JS.

Open `frontend/index.html` directly in a browser, OR serve with:
```bash
cd frontend
python -m http.server 5500
```
Then visit http://localhost:5500

> **Important:** The frontend calls `http://localhost:8000` by default.
> To change the API URL, edit the `API` constant in `frontend/api.js`.

---

## 🚁 Drone Simulator

After placing and paying for an order, run the drone simulator to animate it:

```bash
cd backend
python drone_simulator.py --order-id 1
```

The simulator:
- Moves status from `confirmed` → `dispatched` → `in_transit` → `delivered`
- Updates GPS coordinates, battery %, altitude, and speed every 3 seconds
- The profile page tracks this live (auto-refreshes every 5 seconds)

---

## 🔐 API Endpoints Summary

| Method | Path | Description |
|--------|------|-------------|
| POST | /auth/signup | Register |
| POST | /auth/login | Login → JWT token |
| GET | /users/me | Get current user |
| PUT | /users/me | Update profile |
| POST | /orders | Create order |
| GET | /orders | My orders |
| GET | /orders/{id} | Single order |
| POST | /orders/{id}/pay | Card payment |
| GET | /orders/{id}/track | Live tracking data |
| POST | /orders/{id}/track | Update tracking (drone) |
| PUT | /orders/{id}/status | Update status (drone) |
| GET | /locations | Saved locations |
| POST | /locations | Add location |
| DELETE | /locations/{id} | Delete location |

---

## 💰 Pricing Formula

```
Total = $5.00 (base) + weight_kg × $2.50 + distance_km × $0.50
```
Distance cost only applies when coordinates are provided.

---

## 🎨 Design System

All pages share `shared.css` which defines:
- CSS variables (colors, shadows, radius)
- Navbar, buttons, form elements, badges, cards
- Unified color palette: **Deep Navy + Electric Blue**
- Fonts: Inter (body) + Space Mono (mono/code)

---

## 🔧 User Flow

1. User visits `index.html`
2. Clicks "Sign Up" → fills `signup.html`
3. Logs in via `login.html` → JWT stored in `localStorage`
4. Places order on `order.html` (package info + card payment)
5. Views `profile.html` → sees active orders + history
6. Clicks "Track" → live drone tracking modal opens
7. Run `drone_simulator.py --order-id N` to animate the delivery

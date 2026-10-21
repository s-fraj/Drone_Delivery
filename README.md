# Drovery — Drone Delivery Platform (full stack, real drone dispatch)

This is the merged project: the **Drovery** web app (FastAPI + MySQL + HTML/CSS/JS)
now dispatches real missions to the **drone-service** (Flask + MAVLink) instead of
faking deliveries with a random-movement simulator.

```
drovery/
├── backend/              FastAPI app — users, orders, payments, admin
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   ├── crud.py
│   ├── auth.py
│   ├── database.py
│   ├── drone_client.py   <- talks HTTP to the drone service
│   ├── drone_bridge.py   <- dispatch + background status poller
│   └── requirements.txt
│
├── frontend/              Vite + React 18 + TypeScript (strict)
│   ├── src/pages/         Home, Services, About, Contact, Login, Signup,
│   │                      Order, Profile, Admin (Order/Profile/Admin are lazy-loaded)
│   ├── src/lib/           typed API client, types mirroring schemas.py, geo, pricing
│   ├── src/hooks/         TanStack Query hooks (polling = live status, no manual refresh)
│   ├── src/auth/          AuthContext + route guards (customer / admin / guest)
│   └── src/components/    Layout, Modal, MapPicker (react-leaflet), FleetMap, Toast
│
├── frontend-legacy/       The previous plain HTML/CSS/JS frontend (reference only)
│
└── delivery-system/          Flask + pymavlink — flies the real drones
    ├── python/server.py, mission.py, drone.py
    ├── data/missions.json
    └── requirements.txt
```

## How the two halves are connected

1. A customer places & pays for an order in the web app (`order.html`).
2. `POST /orders/{id}/pay` in the FastAPI backend, right after marking the
   order paid, calls `drone_bridge.dispatch_order()`, which calls
   `drone_client.start_delivery()`, which does `POST /start-delivery` on
   the Flask drone service — the same contract described in the drone
   service's own docs (pickup/dropoff lat-lng, `commande_id`).
3. The drone service either assigns an idle drone immediately or queues
   the mission. `drone.py` then really flies it over MAVLink.
4. FastAPI never talks to MAVLink. A background task
   (`drone_bridge.poller_loop`, started on app startup) polls
   `GET /mission-status/<id>` on the Flask service every few seconds and
   mirrors the real mission status onto the order/tracking rows in MySQL.
5. The frontend just reads `/orders/{id}/track` from FastAPI as before —
   it never talks to the Flask service directly.

Because the drone service only reports **mission status**, not live
GPS/battery/speed telemetry, the tracking UI now shows the real mission
status ("Going to pickup", "Delivered", queue position, assigned drone,
error message) instead of the old simulator's fabricated battery %,
altitude and speed.

## What was removed and why

- **`backend/drone_simulator.py`** — deleted. It faked drone movement with
  random numbers, and its self-run HTTP calls used a hardcoded
  `Authorization: Bearer INTERNAL` header that isn't a valid JWT, so it
  was actually failing its own auth check whenever it ran.
- **`PUT /orders/{id}/status`** and **`POST /orders/{id}/track`** — deleted.
  Neither required authentication, so anyone could rewrite any order's
  status or inject fake tracking data with an unauthenticated request.
  Status now only changes as a result of a real payment, the background
  poller reading real mission state, or an authenticated admin override.
- Fabricated `battery_pct` / `altitude_m` / `speed_kmh` / live `current_lat`
  fields — dropped from `DroneTracking`, since the drone service has no
  way to supply real values for them.
- `pickup_lat/lng` and `dropoff_lat/lng` are now **required**, not optional
  — a drone can't fly to a street address, and the old "optional" fields
  meant orders could be created that were physically impossible to dispatch.

## New: Admin

- The **first account ever created** on a fresh database automatically
  becomes an admin (`is_admin=True`) — no separate seeding step needed.
- Admins get a `🛠️ Admin` link in the navbar and `admin.html`, which shows:
  live fleet status (idle/busy drones + queue), every order with its real
  mission status, a manual status override, a "retry dispatch" button for
  orders that failed to reach the drone service, and the full user list.
- All `/admin/*` endpoints require `is_admin` (checked server-side).

## Bug fix: bcrypt/passlib

`requirements.txt` pinned `passlib[bcrypt]==1.7.4` without pinning `bcrypt`
itself. Recent `bcrypt` releases removed an internal attribute passlib 1.7.4
reads to detect the version, which makes `auth.hash_password()` crash on a
fresh `pip install`. Fixed by pinning `bcrypt==4.0.1` alongside it.

## Running it

### 1. Drone service (Flask + MAVLink)
```bash
cd delivery-system/python
pip install -r requirements.txt
# edit the DRONES dict in mission.py with your SITL ports
export DRONE_API_KEY=some-long-random-secret
python server.py            # listens on :5000
```

### 2. Backend (FastAPI + MySQL)
```sql
CREATE DATABASE drovery CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```
```bash
cd backend
pip install -r requirements.txt
export DB_USER=root DB_PASSWORD=yourpassword DB_HOST=localhost DB_NAME=drovery
export SECRET_KEY=your-random-secret-key
export DRONE_SERVICE_URL=http://127.0.0.1:5000
export DRONE_SERVICE_API_KEY=some-long-random-secret   # must match DRONE_API_KEY above
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend
```bash
cd frontend
python -m http.server 5500
```
Visit http://localhost:5500. The first account you sign up with becomes the admin.

## Pricing formula (unchanged)
```
Total = $5.00 (base) + weight_kg × $2.50 + distance_km × $0.50
```
Distance is now always computed, since coordinates are required.

## API summary

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /auth/signup | — | Register (first user becomes admin) |
| POST | /auth/login | — | Login → JWT |
| GET/PUT | /users/me | user | Profile |
| POST | /orders | user | Create order (coords required) |
| GET | /orders, /orders/{id} | user | List / fetch own orders |
| POST | /orders/{id}/pay | user | Pay → dispatches the real drone mission |
| GET | /orders/{id}/track | user | Read-only real mission status |
| GET/POST/DELETE | /locations | user | Saved locations |
| GET | /admin/orders, /admin/orders/{id} | admin | All orders, with tracking |
| PUT | /admin/orders/{id}/status | admin | Manual status override |
| POST | /admin/orders/{id}/retry-dispatch | admin | Retry a failed dispatch |
| GET | /admin/users | admin | All users |
| GET | /admin/fleet | admin | Live fleet/queue status |
| GET | /admin/drone-service-health | admin | Is the Flask service reachable |


## Running the frontend

```bash
cd frontend
cp .env.example .env     # VITE_API_URL=http://localhost:8000
npm install
npm run dev              # http://localhost:5173
npm run build            # typecheck + production build into dist/
```

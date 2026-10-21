import json
import math
import os
import threading
import time
import uuid
from datetime import datetime, timezone

MISSIONS_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'missions.json')

# Each drone has a MAVLink connection string and a "home" position — where
# it launches from and automatically returns to after every delivery.
# Adjust the home lat/lng to wherever your SITL --custom-location actually
# spawns each instance. You don't need to comment any of these out to run
# fewer than 3 drones — the health checker (see start_health_checks below)
# detects which ones actually have a SITL running and takes the rest out
# of the assignment pool automatically.
DRONES = {
    1: {"connection": "udp:127.0.0.1:14551", "home": {"lat": 33.3429998, "lng": 10.4910735}},
    2: {"connection": "udp:127.0.0.1:14561", "home": {"lat": 33.3439998, "lng": 10.4920735}},
    3: {"connection": "udp:127.0.0.1:14571", "home": {"lat": 33.3449998, "lng": 10.4930735}},
}

_lock = threading.Lock()

HEALTH_CHECK_INTERVAL_S = 10
MAX_TRAIL_POINTS = 400  # ~3-6 min of flight history at the 0.5s telemetry rate

# Simulated-battery fallback — only used on ticks where real MAVLink
# BATTERY_STATUS telemetry wasn't available (e.g. a SITL build with no
# battery model). Configurable via env so you don't have to edit code to
# tune it.
BATTERY_DRAIN_PCT_PER_TICK = float(os.environ.get("BATTERY_DRAIN_PCT_PER_TICK", "0.08"))
LOW_BATTERY_THRESHOLD = float(os.environ.get("LOW_BATTERY_THRESHOLD_PCT", "20.0"))

# status: "offline" (no SITL detected yet) | "idle" (grounded, reachable) |
# "busy" (flying a mission) | "returning_home" (airborne, free, still assignable)
fleet_state = {
    drone_id: {
        "status": "offline",
        "mission_id": None,
        "lat": cfg["home"]["lat"],
        "lng": cfg["home"]["lng"],
        "alt": 0.0,
        "battery_pct": 100.0,
        "battery_source": "sim",  # "sim" or "telemetry" — which one is currently driving battery_pct
        "trail": [],  # recent [lat, lng] points — recorded at true flight
                      # telemetry rate (every ~0.5s), independent of how
                      # often the admin dashboard happens to poll it, so
                      # the drawn path is as smooth as the SITL console.
    }
    for drone_id, cfg in DRONES.items()
}

missions = {}
queue = []

# Pause ("soft stop": stop accepting new orders, let in-flight ones finish
# and drones return home normally) / Emergency stop ("hard stop": pause +
# immediately recall every airborne drone) — see set_accepting_orders() and
# emergency_stop() below.
service_state = {"accepting_orders": True, "message": None}


def _health_check_loop():
    """
    Runs for the lifetime of the process. Only ever touches drones that are
    currently "idle" or "offline" — a drone that's "busy" or
    "returning_home" already has its own live MAVLink connection via
    launch_drone, so we leave it alone entirely rather than opening a
    second competing connection to the same SITL.
    """
    from drone import is_drone_reachable
    while True:
        for drone_id in list(DRONES.keys()):
            with _lock:
                current = fleet_state[drone_id]["status"]
            if current not in ("idle", "offline"):
                continue

            reachable = is_drone_reachable(drone_id)

            with _lock:
                if fleet_state[drone_id]["status"] not in ("idle", "offline"):
                    continue
                fleet_state[drone_id]["status"] = "idle" if reachable else "offline"

        _try_assign()
        time.sleep(HEALTH_CHECK_INTERVAL_S)


def start_health_checks():
    threading.Thread(target=_health_check_loop, daemon=True).start()


def _haversine(lat1, lon1, lat2, lon2):
    """Distance in meters between two GPS points."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _load():
    global missions, queue, service_state
    if not os.path.exists(MISSIONS_FILE):
        return
    try:
        with open(MISSIONS_FILE, 'r') as f:
            data = json.load(f)
        missions = data.get('missions', {})
        queue = data.get('queue', [])
        service_state = data.get('service_state', service_state)
        for i, mid in enumerate(queue):
            if mid in missions:
                missions[mid]['queue_position'] = i + 1
    except Exception as e:
        print(f"[mission.py] Failed to load missions.json: {e}")


def _save():
    try:
        with _lock:
            payload = {'missions': missions, 'queue': queue, 'service_state': service_state}
        with open(MISSIONS_FILE, 'w') as f:
            json.dump(payload, f, default=str)
    except Exception as e:
        print(f"[mission.py] Failed to save missions.json: {e}")


_load()


# ─── Service pause / emergency stop ──────────────────────────────────────────

def get_service_state():
    with _lock:
        return dict(service_state)


def set_accepting_orders(accepting, message=None):
    with _lock:
        service_state["accepting_orders"] = bool(accepting)
        service_state["message"] = message
    _save()
    return get_service_state()


def emergency_stop(message=None):
    """
    Hard stop: pauses new orders AND immediately recalls every currently-
    flying drone (it aborts its current leg and heads home, same mechanism
    as a customer/admin cancel — see flight_interrupt_check). Drones
    already 'returning_home' or 'idle' are unaffected, they're not doing
    anything that needs stopping.
    """
    set_accepting_orders(
        False,
        message or "We've paused deliveries for an emergency stop. All drones are returning to base."
    )
    with _lock:
        busy_mission_ids = [
            s["mission_id"] for s in fleet_state.values()
            if s["status"] == "busy" and s["mission_id"]
        ]
    for mid in busy_mission_ids:
        request_abort(mid)
    return len(busy_mission_ids)


# ─── Mission creation & assignment ───────────────────────────────────────────

def create_mission(data):
    state = get_service_state()
    if not state["accepting_orders"]:
        raise ValueError(state["message"] or "Service temporarily unavailable — please try again shortly.")

    try:
        pickup = data["pickup"]
        pickup_lat = float(pickup["lat"])
        pickup_lng = float(pickup["lng"])

        # Accept either the new multi-stop shape ("dropoffs": [...]) or the
        # older single-stop shape ("dropoff": {...}) for backward compatibility.
        raw_dropoffs = data.get("dropoffs")
        if raw_dropoffs is None:
            raw_dropoffs = [data["dropoff"]]
        if not raw_dropoffs:
            raise ValueError("At least one drop-off is required")
        dropoffs = [{"lat": float(d["lat"]), "lng": float(d["lng"])} for d in raw_dropoffs]
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(f"Invalid delivery payload: {e}")

    mission_id = str(uuid.uuid4())

    with _lock:
        missions[mission_id] = {
            "mission_id": mission_id,
            "commande_id": data.get("commande_id"),
            "pickup": {"lat": pickup_lat, "lng": pickup_lng},
            "dropoffs": dropoffs,
            "current_dropoff_index": 0,
            "status": "Waiting for drone",
            "drone_id": None,
            "queue_position": None,
            "error": None,
            "abort_requested": False,
            "next_target": {"lat": pickup_lat, "lng": pickup_lng},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        queue.append(mission_id)
        _recompute_queue_positions_locked()

    _save()
    _try_assign()

    return missions[mission_id]


def _recompute_queue_positions_locked():
    for i, mid in enumerate(queue):
        missions[mid]["queue_position"] = i + 1


def _try_assign():
    """
    Assigns the oldest queued mission (FIFO — customers served in the order
    they ordered) to the nearest AVAILABLE drone. "Available" means idle
    (grounded) or returning_home (airborne but free) — whichever is
    physically closer to the pickup point right now wins.
    """
    from drone import launch_drone

    with _lock:
        available = [d for d, s in fleet_state.items()
                     if s["status"] in ("idle", "returning_home")]
        if not available or not queue:
            return None

        mission_id = queue[0]
        pickup = missions[mission_id]["pickup"]

        def distance_to_pickup(drone_id):
            s = fleet_state[drone_id]
            return _haversine(s["lat"], s["lng"], pickup["lat"], pickup["lng"])

        chosen = min(available, key=lambda d: (distance_to_pickup(d), d))
        prev_status = fleet_state[chosen]["status"]

        queue.pop(0)
        fleet_state[chosen]["status"] = "busy"
        fleet_state[chosen]["mission_id"] = mission_id
        missions[mission_id]["drone_id"] = chosen
        missions[mission_id]["queue_position"] = None
        _recompute_queue_positions_locked()

    _save()

    if prev_status == "idle":
        with _lock:
            fleet_state[chosen]["trail"] = []
        threading.Thread(target=launch_drone, args=(chosen, mission_id), daemon=True).start()
    # If prev_status was "returning_home", that drone's launch_drone thread
    # is already running and will notice the redirect via check_redirect().

    return mission_id


def update_status(mission_id, status, error=None, target=None):
    """`target`, when given, is the {"lat","lng"} the drone is now flying
    toward — stored so the backend can compute a customer-facing distance
    without needing to know which leg of a (possibly multi-stop) mission
    it's looking at."""
    with _lock:
        if mission_id in missions:
            missions[mission_id]["status"] = status
            if error is not None:
                missions[mission_id]["error"] = error
            if target is not None:
                missions[mission_id]["next_target"] = target
            elif status in ("Delivered", "Completed", "Cancelled"):
                missions[mission_id]["next_target"] = None
    _save()


def set_current_dropoff_index(mission_id, index):
    """Persists progress through a multi-stop mission's drop-off list, so
    a post-restart resume (see recover_fleet/resume_drone) knows which
    stop to continue from instead of re-flying completed ones."""
    with _lock:
        if mission_id in missions:
            missions[mission_id]["current_dropoff_index"] = index
    _save()


def update_position(drone_id, lat, lng, alt=None, real_battery_pct=None):
    """
    Called continuously by drone.py while a drone is airborne. Publishes
    live position (for assignment + the admin map) and updates battery:
    if drone.py passed a real reading from MAVLink's BATTERY_STATUS
    message, that's used directly; otherwise falls back to a simple
    simulated drain so the low-battery/RTH logic still works on a SITL
    build with no battery model.
    """
    with _lock:
        if drone_id in fleet_state:
            s = fleet_state[drone_id]
            s["lat"] = lat
            s["lng"] = lng
            if alt is not None:
                s["alt"] = alt
            trail = s["trail"]
            trail.append([lat, lng])
            if len(trail) > MAX_TRAIL_POINTS:
                del trail[0:len(trail) - MAX_TRAIL_POINTS]

            if s["status"] in ("busy", "returning_home"):
                if real_battery_pct is not None:
                    s["battery_pct"] = float(real_battery_pct)
                    s["battery_source"] = "telemetry"
                else:
                    s["battery_pct"] = max(0.0, s.get("battery_pct", 100.0) - BATTERY_DRAIN_PCT_PER_TICK)
                    s["battery_source"] = "sim"


def check_low_battery(drone_id):
    with _lock:
        s = fleet_state.get(drone_id)
        return bool(s and s.get("battery_pct", 100.0) <= LOW_BATTERY_THRESHOLD)


def request_abort(mission_id):
    """Customer/admin requested cancellation of an in-flight mission (also
    used internally by emergency_stop()). The drone's current leg will
    notice this via flight_interrupt_check and divert home."""
    with _lock:
        m = missions.get(mission_id)
        if not m or m["status"] in ("Completed", "Delivered", "Error", "Cancelled"):
            return False
        m["abort_requested"] = True
    _save()
    return True


def check_abort(mission_id):
    with _lock:
        m = missions.get(mission_id)
        return bool(m and m.get("abort_requested"))


def flight_interrupt_check(drone_id, mission_id):
    """Polled during pickup/drop-off legs. Returns "ABORT_CANCEL",
    "ABORT_BATTERY", or None (continue as planned)."""
    if check_abort(mission_id):
        return "ABORT_CANCEL"
    if check_low_battery(drone_id):
        return "ABORT_BATTERY"
    return None


def requeue_mission(mission_id):
    """A mission aborted for a system reason (low battery) — not cancelled
    by the customer — goes back to the FRONT of the queue so the next
    available drone picks it up immediately."""
    with _lock:
        m = missions.get(mission_id)
        if not m:
            return
        m["status"] = "Waiting for drone"
        m["drone_id"] = None
        m["error"] = None
        m["abort_requested"] = False
        m["current_dropoff_index"] = 0
        m["next_target"] = m["pickup"]
        if mission_id not in queue:
            queue.insert(0, mission_id)
        _recompute_queue_positions_locked()
    _save()
    _try_assign()


def mark_returning_home(drone_id):
    with _lock:
        if drone_id in fleet_state:
            fleet_state[drone_id]["status"] = "returning_home"
            fleet_state[drone_id]["mission_id"] = None
    _save()
    _try_assign()


def check_redirect(drone_id):
    with _lock:
        s = fleet_state.get(drone_id)
        if s and s["status"] == "busy" and s["mission_id"]:
            return s["mission_id"]
    return None


def mark_idle(drone_id):
    """Drone has landed at home with nothing else assigned. Simulates an
    instant battery swap/recharge at base."""
    with _lock:
        if drone_id in fleet_state:
            fleet_state[drone_id]["status"] = "idle"
            fleet_state[drone_id]["mission_id"] = None
            fleet_state[drone_id]["battery_pct"] = 100.0
            fleet_state[drone_id]["battery_source"] = "sim"
    _save()
    _try_assign()


def recover_fleet():
    """
    Called once at server startup. Reconnects to any drone that was
    mid-flight when the service last stopped and resumes its mission
    (see drone.resume_drone) instead of leaving it stranded. Best-effort:
    if the drone can't be reached or already landed unsupervised, the
    mission is marked as an error for the admin to retry.
    """
    from drone import resume_drone

    to_resume = []
    with _lock:
        for drone_id in DRONES:
            for mid, m in missions.items():
                if m.get("drone_id") == drone_id and m.get("status") not in (
                    "Completed", "Delivered", "Error", "Cancelled", "Dispatch failed"
                ):
                    fleet_state[drone_id]["status"] = "busy"
                    fleet_state[drone_id]["mission_id"] = mid
                    to_resume.append((drone_id, mid))
                    break

    for drone_id, mid in to_resume:
        print(f"[mission.py] Attempting recovery: drone {drone_id}, mission {mid}")
        threading.Thread(target=resume_drone, args=(drone_id, mid), daemon=True).start()


def get_mission(mission_id):
    with _lock:
        mission = missions.get(mission_id)
        if not mission:
            return None
        mission = dict(mission)
        drone_id = mission.get("drone_id")
        if drone_id is not None and drone_id in fleet_state:
            s = fleet_state[drone_id]
            mission["drone_position"] = {"lat": s["lat"], "lng": s["lng"]}
        return mission


def get_fleet_status():
    with _lock:
        return {
            "drones": {str(d): dict(s) for d, s in fleet_state.items()},
            "queue_length": len(queue),
            "queue": list(queue),
            "service_state": dict(service_state),
        }

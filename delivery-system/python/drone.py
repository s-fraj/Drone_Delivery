print("NEW MAVLINK DRONE CODE LOADED")
from pymavlink import mavutil
import time
import math

from mission import (
    DRONES, get_mission, update_status, update_position,
    mark_returning_home, check_redirect, mark_idle, flight_interrupt_check,
    requeue_mission, set_current_dropoff_index,
)


# ─── Helpers GPS ─────────────────────────────────────────────────────────────

def _haversine(lat1, lon1, lat2, lon2):
    """Distance en mètres entre deux points GPS (lat/lon en degrés)."""
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def _get_current_position(connection):
    """Récupère la dernière position GPS connue du drone."""
    msg = connection.recv_match(type='GLOBAL_POSITION_INT', blocking=False)
    if msg:
        return msg.lat / 1e7, msg.lon / 1e7, msg.relative_alt / 1000.0
    return None, None, None


def _get_battery_pct(connection):
    """
    Lit le niveau de batterie réel via MAVLink (SYS_STATUS.battery_remaining,
    envoyé par défaut par le modèle de batterie simulé d'ArduPilot SITL).
    Renvoie un pourcentage 0-100, ou None si l'info n'est pas disponible
    (auquel cas mission.py utilise une simulation de secours).
    """
    msg = connection.recv_match(type='SYS_STATUS', blocking=False)
    if msg is not None and msg.battery_remaining is not None and msg.battery_remaining >= 0:
        return float(msg.battery_remaining)
    return None


def _get_current_mode(connection):
    """Récupère le mode de vol actuel du drone."""
    msg = connection.recv_match(type='HEARTBEAT', blocking=False)
    if msg:
        return mavutil.mode_string_v10(msg)
    return None


def _ensure_guided(connection, drone_id):
    """S'assure que le drone est en mode GUIDED."""
    mode = _get_current_mode(connection)
    if mode != 'GUIDED':
        print(f"[Drone {drone_id}] Mode is {mode}, switching to GUIDED")
        connection.set_mode('GUIDED')
        time.sleep(2)
        for _ in range(10):
            time.sleep(0.5)
            mode = _get_current_mode(connection)
            if mode == 'GUIDED':
                print(f"[Drone {drone_id}] Now in GUIDED mode")
                return True
        raise TimeoutError(f"Drone {drone_id} failed to enter GUIDED mode")
    return True


def _send_goto(connection, lat, lon, alt=10):
    """Envoie une commande GOTO. À appeler régulièrement en GUIDED."""
    connection.mav.send(
        mavutil.mavlink.MAVLink_set_position_target_global_int_message(
            0,
            connection.target_system,
            connection.target_component,
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
            int(0b110111111000),
            int(lat * 10**7),
            int(lon * 10**7),
            alt,
            0, 0, 0,
            0, 0, 0,
            0, 0
        )
    )


def _wait_for_altitude(connection, drone_id, target_alt, threshold_m=1.0, timeout_s=60):
    """Attend que l'altitude relative soit atteinte (pour le décollage)."""
    print(f"[Drone {drone_id}] Waiting for altitude {target_alt}m "
          f"(threshold={threshold_m}m, timeout={timeout_s}s)")

    start = time.time()
    while True:
        time.sleep(0.5)

        lat, lon, alt = _get_current_position(connection)
        if alt is None:
            continue

        diff = abs(alt - target_alt)
        print(f"[Drone {drone_id}] Alt: {alt:.1f}m | Diff: {diff:.1f}m")

        if diff <= threshold_m:
            print(f"[Drone {drone_id}] ✅ Altitude reached")
            return True

        if time.time() - start > timeout_s:
            raise TimeoutError(
                f"Drone {drone_id} did not reach altitude {target_alt}m "
                f"within {timeout_s}s (last: {alt:.1f}m)"
            )


def _wait_for_arrival(connection, drone_id, target_lat, target_lon, target_alt=None,
                      threshold_m=2.0, timeout_s=180, poll_hz=2, redirect_check=None):
    """
    Attend que le drone soit à moins de `threshold_m` mètres de la cible GPS.
    Envoie le setpoint GOTO régulièrement pour maintenir la navigation.
    Publie la position (et la batterie, réelle si disponible sinon simulée)
    à chaque cycle.

    `redirect_check`, si fourni, est interrogé à chaque cycle et peut
    renvoyer :
      - None                 → continuer normalement
      - "ABORT_CANCEL"        → annulation demandée   → ("aborted", "cancel")
      - "ABORT_BATTERY"       → batterie faible        → ("aborted", "battery")
      - un mission_id (str)  → redirection en vol      → ("redirected", id)
    """
    print(f"[Drone {drone_id}] Target: {target_lat}, {target_lon} "
          f"(threshold={threshold_m}m, timeout={timeout_s}s)")

    start = time.time()
    interval = 1.0 / poll_hz

    while True:
        time.sleep(interval)

        # CRUCIAL : renvoyer le setpoint en boucle (sinon ArduPilot passe en LOITER)
        _send_goto(connection, target_lat, target_lon, target_alt or 10)

        lat, lon, alt = _get_current_position(connection)
        battery = _get_battery_pct(connection)

        if lat is None:
            continue

        update_position(drone_id, lat, lon, alt, real_battery_pct=battery)

        if redirect_check is not None:
            signal = redirect_check()
            if signal == "ABORT_CANCEL":
                print(f"[Drone {drone_id}] 🛑 Abort requested mid-flight")
                return ("aborted", "cancel")
            if signal == "ABORT_BATTERY":
                print(f"[Drone {drone_id}] 🔋 Low battery mid-flight, aborting to base")
                return ("aborted", "battery")
            if signal:
                print(f"[Drone {drone_id}] 🔀 Redirected mid-flight to mission {signal}")
                return ("redirected", signal)

        dist = _haversine(lat, lon, target_lat, target_lon)
        status_line = f"[Drone {drone_id}] Pos: {lat:.7f}, {lon:.7f} | Dist: {dist:.1f}m"

        reached = dist <= threshold_m

        if target_alt is not None:
            alt_diff = abs(alt - target_alt)
            status_line += f" | Alt diff: {alt_diff:.1f}m"
            reached = reached and (alt_diff <= 1.0)

        print(status_line)

        if reached:
            print(f"[Drone {drone_id}] ✅ Reached target ({dist:.1f}m away)")
            return True

        if time.time() - start > timeout_s:
            raise TimeoutError(
                f"Drone {drone_id} did not reach target within {timeout_s}s "
                f"(last distance: {dist:.1f}m)"
            )


# ─── MAVLink helpers ─────────────────────────────────────────────────────────

def _connect(drone_id):
    conn_string = DRONES[drone_id]["connection"]

    print(f"[Drone {drone_id}] Connecting via {conn_string}...")
    connection = mavutil.mavlink_connection(conn_string)

    print(f"[Drone {drone_id}] Waiting for heartbeat...")
    heartbeat = connection.wait_heartbeat(timeout=30)
    if heartbeat is None:
        raise TimeoutError(
            f"No heartbeat from drone {drone_id} on {conn_string} after 30s "
            f"— is SITL actually running on this port?"
        )

    print(f"[Drone {drone_id}] Connected!")
    return connection


def _wait_armed(connection, drone_id, timeout_s=8):
    """
    Poll heartbeats until the ARMED bit is set, or timeout. Also collects
    any STATUSTEXT messages seen in the meantime (that's where ArduPilot
    reports the actual PreArm rejection reason, e.g. "PreArm: Need 3D Fix"),
    returning them so a failed attempt can report *why*, not just *that*.
    """
    start = time.time()
    statustexts = []
    while time.time() - start < timeout_s:
        msg = connection.recv_match(type=['HEARTBEAT', 'STATUSTEXT'], blocking=True, timeout=1)
        if msg is None:
            continue
        if msg.get_type() == 'STATUSTEXT':
            texte = msg.text if isinstance(msg.text, str) else msg.text.decode(errors='ignore')
            statustexts.append(texte)
        elif msg.get_type() == 'HEARTBEAT' and (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED):
            return True, statustexts
    return False, statustexts


def _arm_and_takeoff(connection, drone_id, target_alt=10):
    print(f"[Drone {drone_id}] Changing mode to GUIDED")
    _ensure_guided(connection, drone_id)

    # Juste après un atterrissage, ArduCopter rejette parfois une première
    # tentative d'armement (PreArm check, delai anti-rearm...). On vérifie
    # que l'armement a réellement pris effet plutôt que de supposer que
    # arducopter_arm() a fonctionné, et on réessaie si ce n'est pas le cas.
    print(f"[Drone {drone_id}] Arming drone")
    armed = False
    tous_messages = []
    for attempt in range(1, 4):
        connection.arducopter_arm()
        armed, messages = _wait_armed(connection, drone_id, timeout_s=8)
        tous_messages.extend(messages)
        if armed:
            break
        raison = f" — {messages[-1]}" if messages else ""
        print(f"[Drone {drone_id}] Arm attempt {attempt}/3 not confirmed{raison}, retrying in 2s...")
        time.sleep(2)

    if not armed:
        derniere_raison = tous_messages[-1] if tous_messages else "no PreArm message received — check SITL console"
        raise TimeoutError(
            f"Drone {drone_id} failed to arm after 3 attempts: {derniere_raison}"
        )

    print(f"[Drone {drone_id}] Armed! Sending takeoff command to {target_alt}m")
    connection.mav.command_long_send(
        connection.target_system,
        connection.target_component,
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
        0,
        0, 0, 0, 0, 0, 0,
        target_alt
    )

    _wait_for_altitude(connection, drone_id, target_alt, threshold_m=1.0, timeout_s=60)
    # Laisser le drone se stabiliser horizontalement avant de partir
    time.sleep(3)
    print(f"[Drone {drone_id}] Takeoff complete")


def _goto_location(connection, drone_id, lat, lon, alt=10, redirect_check=None):
    print(f"[Drone {drone_id}] GOTO: {lat}, {lon}, alt={alt}m")

    _ensure_guided(connection, drone_id)

    # Timeout dynamique : distance / 3 m/s + 60s de marge
    current_lat, current_lon, _ = _get_current_position(connection)
    if current_lat is not None:
        distance = _haversine(current_lat, current_lon, lat, lon)
        timeout = max(180, int(distance / 3) + 60)
        print(f"[Drone {drone_id}] Distance to target: {distance:.0f}m | Timeout: {timeout}s")
    else:
        timeout = 300

    return _wait_for_arrival(connection, drone_id, lat, lon, target_alt=alt,
                      threshold_m=2.0, timeout_s=timeout, redirect_check=redirect_check)


def _land(connection, drone_id):
    print(f"[Drone {drone_id}] Landing")

    connection.mav.command_long_send(
        connection.target_system,
        connection.target_component,
        mavutil.mavlink.MAV_CMD_NAV_LAND,
        0,
        0, 0, 0, 0, 0, 0, 0
    )

    start = time.time()
    while True:
        time.sleep(2)
        lat, lon, alt = _get_current_position(connection)
        if alt is not None and alt < 0.5:
            print(f"[Drone {drone_id}] ✅ Landed")
            break
        if time.time() - start > 60:
            print(f"[Drone {drone_id}] ⚠️ Land timeout, assuming landed")
            break

    # Désarmement explicite : on ne compte pas sur le DISARM_DELAY
    # automatique d'ArduCopter, dont le timing n'est pas garanti avant que
    # la mission suivante ne tente de réarmer ce même drone.
    print(f"[Drone {drone_id}] Disarming")
    connection.arducopter_disarm()
    for _ in range(10):
        time.sleep(0.5)
        msg = connection.recv_match(type='HEARTBEAT', blocking=False)
        if msg and not (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED):
            print(f"[Drone {drone_id}] ✅ Disarmed")
            break


def is_drone_reachable(drone_id, timeout=3):
    """
    Quick liveness probe used only by the fleet health checker — never
    called on a drone that's already busy/returning_home.
    """
    conn_string = DRONES[drone_id]["connection"]
    try:
        connection = mavutil.mavlink_connection(conn_string)
        hb = connection.wait_heartbeat(timeout=timeout)
        connection.close()
        return hb is not None
    except Exception:
        return False


# ─── Mission orchestration ───────────────────────────────────────────────────

def _fly_leg(connection, drone_id, mission_id, lat, lng, interrupt_check=None):
    """Flies one leg and returns a plain signal for the caller to act on:
    None (arrived normally), "cancel", "battery", or a new mission_id
    string (redirect — only relevant for the return-home leg)."""
    result = _goto_location(connection, drone_id, lat, lng, redirect_check=interrupt_check)
    if isinstance(result, tuple):
        kind, payload = result
        if kind == "aborted":
            return payload  # "cancel" or "battery"
        if kind == "redirected":
            return payload  # new mission_id
    return None


def _abort_and_return_home(connection, drone_id, mission_id, reason):
    """A delivery leg was interrupted (cancel or low battery). Heads
    straight home, lands, and either closes the mission out (cancel) or
    requeues it for another drone (battery)."""
    if reason == "battery":
        print(f"[Drone {drone_id}] Low battery — aborting mission {mission_id}, will requeue")
        requeue_mission(mission_id)
    else:
        print(f"[Drone {drone_id}] Mission {mission_id} cancelled — returning home")
        update_status(mission_id, "Cancelled")

    home = DRONES.get(drone_id, {}).get("home")
    if home:
        try:
            _goto_location(connection, drone_id, home["lat"], home["lng"])
        except Exception as e:
            print(f"[Drone {drone_id}] Error returning home after abort: {e}")

    _land(connection, drone_id)
    mark_idle(drone_id)


def _fly_mission_loop(connection, drone_id, mission_id, airborne):
    """
    Shared flight logic for a fresh dispatch (launch_drone) or a
    post-restart resume (resume_drone). Handles an arbitrary number of
    drop-offs in sequence: pickup → dropoff[0] → dropoff[1] → ... → home.
    """
    while mission_id:
        mission = get_mission(mission_id)
        if not mission:
            print(f"[Drone {drone_id}] Mission {mission_id} not found, aborting")
            break

        pickup = mission["pickup"]
        dropoffs = mission["dropoffs"]
        current_status = mission.get("status")
        interrupt = lambda: flight_interrupt_check(drone_id, mission_id)

        if not airborne:
            update_status(mission_id, "Taking off", target=pickup)
            _arm_and_takeoff(connection, drone_id)
            airborne = True

        # Fly to pickup unless we're resuming a mission that already got past it.
        if current_status in ("Waiting for drone", "Taking off", "Going to pickup"):
            update_status(mission_id, "Going to pickup", target=pickup)
            signal = _fly_leg(connection, drone_id, mission_id, pickup["lat"], pickup["lng"], interrupt)
            if signal:
                return _abort_and_return_home(connection, drone_id, mission_id, signal)

            update_status(mission_id, "Package picked")
            time.sleep(3)
            start_index = 0
        else:
            # Resuming mid-delivery — continue from whichever stop was in progress.
            start_index = mission.get("current_dropoff_index", 0)

        # Fly each remaining drop-off in order.
        idx = start_index
        while idx < len(dropoffs):
            stop = dropoffs[idx]
            set_current_dropoff_index(mission_id, idx)
            label = "Going to client"
            update_status(mission_id, label, target=stop)

            signal = _fly_leg(connection, drone_id, mission_id, stop["lat"], stop["lng"], interrupt)
            if signal:
                return _abort_and_return_home(connection, drone_id, mission_id, signal)

            idx += 1
            if idx < len(dropoffs):
                time.sleep(2)  # brief pause between stops (package handoff)

        update_status(mission_id, "Delivered")
        update_status(mission_id, "Completed")
        print(f"[Drone {drone_id}] Mission {mission_id} completed ({len(dropoffs)} stop(s))")

        home = DRONES.get(drone_id, {}).get("home")
        if not home:
            break  # no home configured — land right here

        mark_returning_home(drone_id)
        print(f"[Drone {drone_id}] Returning to home position")
        result = _goto_location(
            connection, drone_id, home["lat"], home["lng"],
            redirect_check=lambda: check_redirect(drone_id)
        )

        if isinstance(result, tuple) and result[0] == "redirected":
            mission_id = result[1]
            continue  # already airborne — loop flies straight to new pickup

        break  # reached home, nothing pending

    _land(connection, drone_id)
    mark_idle(drone_id)
    print(f"[Drone {drone_id}] Back home and idle")


def launch_drone(drone_id, mission_id):
    """
    Master life-cycle entry point for a freshly-dispatched drone: connect,
    fly the given mission (pickup + all its drop-offs), then automatically
    return to base — staying available and redirectable while doing so.
    """
    connection = None
    try:
        connection = _connect(drone_id)
        _fly_mission_loop(connection, drone_id, mission_id, airborne=False)

    except Exception as e:
        print(f"[Drone {drone_id}] Error: {e}")
        if mission_id:
            update_status(mission_id, "Error", error=str(e))
        mark_idle(drone_id)

    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


def resume_drone(drone_id, mission_id):
    """
    Called once at server startup by mission.recover_fleet() for any
    mission still mid-flight when the service last stopped. Reconnects
    and, if the drone is still reachable and armed, continues the mission
    from wherever its status record says it was (including which drop-off
    it was on). If it can't be reached, or landed/disarmed on its own
    while unsupervised, the mission is marked as an error for the admin
    to retry rather than silently left stranded.
    """
    connection = None
    try:
        conn_string = DRONES[drone_id]["connection"]
        print(f"[Drone {drone_id}] Recovery: reconnecting via {conn_string}...")
        connection = mavutil.mavlink_connection(conn_string)
        if connection.wait_heartbeat(timeout=5) is None:
            raise ConnectionError("No heartbeat during recovery — is the SITL/drone still up?")
        if not connection.motors_armed():
            raise RuntimeError("Drone was disarmed/landed while the service was down")

        print(f"[Drone {drone_id}] Recovered contact mid-flight — resuming mission {mission_id}")
        _fly_mission_loop(connection, drone_id, mission_id, airborne=True)

    except Exception as e:
        print(f"[Drone {drone_id}] Recovery failed: {e}")
        if mission_id:
            update_status(
                mission_id, "Error",
                error="Lost contact with the drone after a service restart — please retry dispatch."
            )
        mark_idle(drone_id)

    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

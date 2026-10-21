# server.py
#
# Flask API — the only thing Laravel ever talks to. This process never
# touches MAVLink directly; it delegates flight logic to drone.py via
# mission.py's fleet manager.

import os

from flask import Flask, request, jsonify
from flask_cors import CORS

from mission import (
    create_mission, get_mission, get_fleet_status, start_health_checks,
    recover_fleet, request_abort, get_service_state, set_accepting_orders,
    emergency_stop,
)

app = Flask(__name__)
CORS(app)

# Begins probing each configured drone's SITL connection every 10s so the
# fleet automatically knows which drones are actually up, without needing
# DRONES edited by hand when you're only running 1 or 2 of the 3.
start_health_checks()

# If this process crashed or was restarted while a drone was mid-flight,
# reconnect to it and resume that mission instead of leaving it stranded.
recover_fleet()

# Shared secret Laravel must send as the "X-API-Key" header on every
# request. Set this to the same value as DRONE_SERVICE_API_KEY in
# Laravel's .env.
# <-- SET A REAL SECRET HERE (or via the DRONE_API_KEY env var) -->
API_KEY = os.environ.get("DRONE_API_KEY", "1f2r3t5g4u4yt132154")


@app.before_request
def require_api_key():
    # /health is left open so you can check the service is up without
    # needing the key (e.g. from an uptime check or curl).
    if request.path == "/health":
        return

    if request.headers.get("X-API-Key") != API_KEY:
        return jsonify({"error": "Invalid or missing API key"}), 401


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/start-delivery", methods=["POST"])
def start():
    data = request.get_json(silent=True) or {}

    try:
        mission = create_mission(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "message": "Delivery request received",
        "mission": mission,
    })


@app.route("/mission-status/<mission_id>")
def status(mission_id):
    mission = get_mission(mission_id)

    if not mission:
        return jsonify({"error": "Unknown mission_id"}), 404

    return jsonify(mission)


@app.route("/mission-abort/<mission_id>", methods=["POST"])
def abort(mission_id):
    ok = request_abort(mission_id)
    if not ok:
        return jsonify({"error": "Mission not found, or already finished"}), 404
    return jsonify({"message": "Abort requested — drone will return to base"})


@app.route("/fleet-status")
def fleet_status():
    return jsonify(get_fleet_status())


@app.route("/fleet-live")
def fleet_live():
    # Same data as /fleet-status (positions are already included in
    # fleet_state) — kept as its own route so the admin-only consumer is
    # explicit and can diverge later without touching /fleet-status.
    return jsonify(get_fleet_status())


@app.route("/service-state")
def service_state_route():
    return jsonify(get_service_state())


@app.route("/service-state", methods=["POST"])
def set_service_state_route():
    data = request.get_json(silent=True) or {}
    accepting = bool(data.get("accepting_orders", True))
    message = data.get("message")
    return jsonify(set_accepting_orders(accepting, message))


@app.route("/emergency-stop", methods=["POST"])
def emergency_stop_route():
    data = request.get_json(silent=True) or {}
    message = data.get("message")
    recalled = emergency_stop(message)
    return jsonify({"message": f"Emergency stop triggered — {recalled} drone(s) recalled",
                     **get_service_state()})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

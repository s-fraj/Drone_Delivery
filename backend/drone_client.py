"""
drone_client.py
----------------
Thin async wrapper around the Python/Flask/MAVLink drone service
(delivery-system/python/server.py). This is the ONLY module in the
FastAPI backend that talks to that service — it never touches MAVLink
or drone.py directly, exactly like the drone service's own README
describes for its intended caller.

Configure with the same two env vars the drone service's README
documents:
    DRONE_SERVICE_URL      e.g. http://127.0.0.1:5000
    DRONE_SERVICE_API_KEY  must match DRONE_API_KEY on the drone service
"""
import os
import httpx

DRONE_SERVICE_URL = os.getenv("DRONE_SERVICE_URL", "http://127.0.0.1:5000").rstrip("/")
DRONE_SERVICE_API_KEY = os.getenv("DRONE_SERVICE_API_KEY", "1f2r3t5g4u4yt132154")

_HEADERS = {"X-API-Key": DRONE_SERVICE_API_KEY}
_TIMEOUT = 10.0


class DroneServiceError(Exception):
    """Raised whenever the drone service can't be reached or rejects a request."""


async def start_delivery(pickup_lat: float, pickup_lng: float,
                          dropoffs: list[dict],
                          commande_id: int) -> dict:
    """`dropoffs` is a list of {"lat":, "lng":} in delivery order — the
    primary drop-off followed by any extra stops."""
    payload = {
        "pickup": {"lat": pickup_lat, "lng": pickup_lng},
        "dropoffs": dropoffs,
        "commande_id": commande_id,
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            res = await client.post(f"{DRONE_SERVICE_URL}/start-delivery",
                                     json=payload, headers=_HEADERS)
    except httpx.HTTPError as e:
        raise DroneServiceError(f"Could not reach drone service: {e}") from e

    if res.status_code != 200:
        detail = res.json().get("error", res.text) if res.content else res.text
        raise DroneServiceError(f"Drone service rejected mission: {detail}")

    return res.json()["mission"]


async def get_mission_status(mission_id: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            res = await client.get(f"{DRONE_SERVICE_URL}/mission-status/{mission_id}",
                                    headers=_HEADERS)
    except httpx.HTTPError as e:
        raise DroneServiceError(f"Could not reach drone service: {e}") from e

    if res.status_code == 404:
        return None
    if res.status_code != 200:
        raise DroneServiceError(f"Drone service error: {res.text}")
    return res.json()


async def abort_mission(mission_id: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            res = await client.post(f"{DRONE_SERVICE_URL}/mission-abort/{mission_id}",
                                     headers=_HEADERS)
    except httpx.HTTPError as e:
        raise DroneServiceError(f"Could not reach drone service: {e}") from e

    if res.status_code != 200:
        detail = res.json().get("error", res.text) if res.content else res.text
        raise DroneServiceError(f"Drone service rejected abort: {detail}")
    return res.json()


async def get_fleet_status() -> dict:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            res = await client.get(f"{DRONE_SERVICE_URL}/fleet-status", headers=_HEADERS)
    except httpx.HTTPError as e:
        raise DroneServiceError(f"Could not reach drone service: {e}") from e

    if res.status_code != 200:
        raise DroneServiceError(f"Drone service error: {res.text}")
    return res.json()


async def is_healthy() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(f"{DRONE_SERVICE_URL}/health")
        return res.status_code == 200
    except httpx.HTTPError:
        return False


async def get_service_state() -> dict:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            res = await client.get(f"{DRONE_SERVICE_URL}/service-state", headers=_HEADERS)
    except httpx.HTTPError as e:
        raise DroneServiceError(f"Could not reach drone service: {e}") from e
    if res.status_code != 200:
        raise DroneServiceError(f"Drone service error: {res.text}")
    return res.json()


async def set_service_state(accepting_orders: bool, message: str | None = None) -> dict:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            res = await client.post(f"{DRONE_SERVICE_URL}/service-state",
                                     json={"accepting_orders": accepting_orders, "message": message},
                                     headers=_HEADERS)
    except httpx.HTTPError as e:
        raise DroneServiceError(f"Could not reach drone service: {e}") from e
    if res.status_code != 200:
        raise DroneServiceError(f"Drone service error: {res.text}")
    return res.json()


async def emergency_stop(message: str | None = None) -> dict:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            res = await client.post(f"{DRONE_SERVICE_URL}/emergency-stop",
                                     json={"message": message}, headers=_HEADERS)
    except httpx.HTTPError as e:
        raise DroneServiceError(f"Could not reach drone service: {e}") from e
    if res.status_code != 200:
        raise DroneServiceError(f"Drone service error: {res.text}")
    return res.json()

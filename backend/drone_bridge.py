"""
drone_bridge.py
----------------
Connects the two halves of the project:
  - Drone_Delivery-main's FastAPI backend (orders, users, payments)
  - delivery-system's Flask/MAVLink drone service (real flight control)

Two responsibilities:
  1. dispatch_order()  — called right after a paid order is confirmed;
     creates a mission on the drone service.
  2. poll_active_missions() — runs on a loop in the background, asks the
     drone service for the current status of every order that has a
     mission in flight, and mirrors that status onto the Order /
     DroneTracking rows so the frontend just reads from our own DB.

The FastAPI app never talks to MAVLink; it only ever calls drone_client,
which only ever calls the Flask service — same boundary the drone
service's own README describes.
"""
import asyncio
import logging
import math

import crud, models
from database import SessionLocal
import drone_client
from drone_client import DroneServiceError

logger = logging.getLogger("drone_bridge")

POLL_INTERVAL_SECONDS = 4


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# Raw mission-service status strings -> our own OrderStatus.
# "Error" is intentionally absent: on error we keep whatever status the
# order already had and just attach the error message, instead of
# silently downgrading a real-world failure into a normal status.
MISSION_TO_ORDER_STATUS = {
    "Waiting for drone": models.OrderStatus.dispatched,
    "Taking off":        models.OrderStatus.dispatched,
    "Going to pickup":   models.OrderStatus.dispatched,
    "Package picked":    models.OrderStatus.in_transit,
    "Going to client":   models.OrderStatus.in_transit,
    "Delivered":         models.OrderStatus.in_transit,
    "Completed":         models.OrderStatus.delivered,
    "Cancelled":         models.OrderStatus.cancelled,
}


async def dispatch_order(db, order: models.Order) -> None:
    """
    Send a freshly-paid order to the drone service. Never raises: dispatch
    failures (drone service down, all drones busy forever, etc.) are
    recorded on the tracking row so the order isn't stuck in limbo and an
    admin can retry it from /admin/orders/{id}/retry-dispatch.
    """
    dropoffs = [{"lat": order.dropoff_lat, "lng": order.dropoff_lng}]
    for d in (order.extra_dropoffs or []):
        dropoffs.append({"lat": d["lat"], "lng": d["lng"]})

    try:
        mission = await drone_client.start_delivery(
            pickup_lat=order.pickup_lat, pickup_lng=order.pickup_lng,
            dropoffs=dropoffs,
            commande_id=order.id,
        )
    except DroneServiceError as e:
        logger.warning("Dispatch failed for order %s: %s", order.id, e)
        crud.set_mission(db, order.id, mission_id=None,
                          mission_status="Dispatch failed", error_message=str(e))
        return

    crud.set_mission(
        db, order.id,
        mission_id=mission["mission_id"],
        mission_status=mission["status"],
        queue_position=mission.get("queue_position"),
        stops_total=len(dropoffs),
        stops_done=0,
    )
    crud.set_order_status(db, order.id, models.OrderStatus.dispatched)


async def retry_dispatch(db, order: models.Order) -> None:
    """Used by the admin panel to re-send an order that failed to dispatch."""
    await dispatch_order(db, order)


async def cancel_order(db, order: models.Order) -> None:
    """
    Cancels an order. Before dispatch, this is instant (just flips the DB
    status). Once a drone is actually flying it, we ask the drone service
    to abort — the drone diverts home immediately and the poller will
    reflect "Cancelled" within one poll cycle (a few seconds), rather than
    us optimistically marking it cancelled before the drone has actually
    turned around.
    """
    tracking = order.tracking
    if tracking and tracking.mission_id and order.status not in (
        models.OrderStatus.delivered, models.OrderStatus.cancelled
    ):
        try:
            await drone_client.abort_mission(tracking.mission_id)
        except DroneServiceError as e:
            logger.warning("Abort failed for order %s: %s", order.id, e)
            raise
    else:
        crud.set_order_status(db, order.id, models.OrderStatus.cancelled)


async def _sync_one(db, order: models.Order) -> None:
    tracking = order.tracking
    if not tracking or not tracking.mission_id:
        return
    try:
        mission = await drone_client.get_mission_status(tracking.mission_id)
    except DroneServiceError as e:
        logger.warning("Could not poll mission %s for order %s: %s",
                        tracking.mission_id, order.id, e)
        return

    if mission is None:
        return

    raw_status = mission.get("status", tracking.mission_status)
    error = mission.get("error")

    distance_km = None
    target = mission.get("next_target")
    drone_pos = mission.get("drone_position")
    if target and drone_pos and "lat" in target:
        distance_km = round(
            _haversine_km(drone_pos["lat"], drone_pos["lng"], target["lat"], target["lng"]), 1
        )

    dropoffs = mission.get("dropoffs") or []
    stops_total = len(dropoffs) or None
    stops_done = mission.get("current_dropoff_index")
    if stops_done is not None and raw_status in ("Delivered", "Completed"):
        stops_done = len(dropoffs)

    crud.set_mission(
        db, order.id,
        mission_id=tracking.mission_id,
        mission_status=raw_status,
        drone_number=str(mission["drone_id"]) if mission.get("drone_id") is not None else None,
        queue_position=mission.get("queue_position"),
        error_message=error,
        distance_km=distance_km,
        stops_total=stops_total,
        stops_done=stops_done,
    )

    new_status = MISSION_TO_ORDER_STATUS.get(raw_status)
    if new_status is not None and new_status != order.status:
        crud.set_order_status(db, order.id, new_status)


async def poll_active_missions() -> None:
    db = SessionLocal()
    try:
        for order in crud.get_active_orders_with_missions(db):
            await _sync_one(db, order)
    finally:
        db.close()


async def poller_loop() -> None:
    """Runs for the lifetime of the app; started from FastAPI's startup event."""
    while True:
        try:
            await poll_active_missions()
        except Exception:
            logger.exception("drone_bridge poller iteration failed")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)

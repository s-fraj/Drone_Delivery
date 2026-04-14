"""
drone_simulator.py
------------------
Simulates a drone moving from pickup to drop-off.
Run alongside the FastAPI server:
    python drone_simulator.py --order-id 1

It polls the order status and updates DroneTracking every 3 seconds,
moving the drone step by step from pickup to dropoff coordinates.
"""

import asyncio
import argparse
import math
import httpx
import random
from datetime import datetime

API_BASE = "http://localhost:8000"

STATUS_SEQUENCE = [
    "confirmed",
    "dispatched",
    "in_transit",
    "delivered"
]

def haversine_distance(lat1, lng1, lat2, lng2) -> float:
    R = 6371000  # meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def interpolate(start, end, fraction):
    return start + (end - start) * fraction

async def simulate_delivery(order_id: int, steps: int = 30):
    async with httpx.AsyncClient() as client:
        # Fetch order
        res = await client.get(f"{API_BASE}/orders/{order_id}",
                               headers={"Authorization": "Bearer INTERNAL"})
        if res.status_code != 200:
            print(f"[Drone] Could not fetch order {order_id}")
            return

        order = res.json()
        pickup_lat  = order.get("pickup_lat",  36.8)
        pickup_lng  = order.get("pickup_lng",  10.18)
        dropoff_lat = order.get("dropoff_lat", 36.85)
        dropoff_lng = order.get("dropoff_lng", 10.22)

        print(f"[Drone] Starting delivery for Order #{order_id}")
        print(f"[Drone] {pickup_lat},{pickup_lng}  →  {dropoff_lat},{dropoff_lng}")

        for i, status in enumerate(STATUS_SEQUENCE):
            # Update order status
            await client.put(
                f"{API_BASE}/orders/{order_id}/status",
                json={"status": status}
            )
            print(f"[Drone] Status → {status.upper()}")

            if status == "in_transit":
                # Animate drone movement
                for step in range(steps + 1):
                    fraction = step / steps
                    lat = interpolate(pickup_lat, dropoff_lat, fraction)
                    lng = interpolate(pickup_lng, dropoff_lng, fraction)
                    battery = max(20, 100 - int(fraction * 60))
                    altitude = 50 if 0.1 < fraction < 0.9 else 10
                    speed = round(random.uniform(40, 60), 1) if 0 < fraction < 1 else 0

                    await client.post(
                        f"{API_BASE}/orders/{order_id}/track",
                        json={
                            "drone_id": f"DRV-{order_id:04d}",
                            "current_lat": round(lat, 6),
                            "current_lng": round(lng, 6),
                            "battery_pct": battery,
                            "altitude_m": altitude,
                            "speed_kmh": speed
                        }
                    )
                    print(f"[Drone] {fraction*100:.0f}% | lat={lat:.4f} lng={lng:.4f} "
                          f"| 🔋{battery}% | ↑{altitude}m | 💨{speed}km/h")
                    await asyncio.sleep(3)
            else:
                await asyncio.sleep(5)

        print(f"[Drone] ✅ Order #{order_id} DELIVERED!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--order-id", type=int, required=True)
    parser.add_argument("--steps", type=int, default=20)
    args = parser.parse_args()
    asyncio.run(simulate_delivery(args.order_id, args.steps))

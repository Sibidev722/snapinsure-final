"""
Route Risk Service — powered by Mapbox Directions API
Calculates real travel time between two coordinates and classifies risk.

GREEN  → Route exists, no significant delay
YELLOW → Route exists but has delay > 10 minutes vs free-flow baseline
RED    → No route found / API failure
"""

import httpx
from core.config import settings

# Mapbox Directions API endpoint (profile: driving-traffic uses live traffic data)
MAPBOX_BASE_URL = "https://api.mapbox.com/directions/v5/mapbox/driving-traffic"

# Delay threshold in seconds above which we escalate to YELLOW (10 minutes)
DELAY_THRESHOLD_SECONDS = 10 * 60


async def get_route_risk(
    src_lng: float, src_lat: float,
    dst_lng: float, dst_lat: float
) -> dict:
    """
    Calls Mapbox Directions API twice:
      1. `driving-traffic` — current real-world travel time
      2. `driving`         — free-flow baseline (no traffic)

    Then classifies the result:
      GREEN  → route ok, delay ≤ 10 min
      YELLOW → route ok, delay > 10 min
      RED    → no usable route
    """
    api_key = settings.MAPBOX_API_KEY
    if not api_key or api_key == "your_mapbox_token_here":
        return {
            "status": "RED",
            "duration": None,
            "time_loss": None,
            "reason": "Mapbox API key not configured — set MAPBOX_API_KEY in .env"
        }

    coords = f"{src_lng},{src_lat};{dst_lng},{dst_lat}"
    common_params = {
        "access_token": api_key,
        "overview": "false",
        "steps": "false",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        # --- (1) Traffic-aware duration ---
        try:
            traffic_url = f"{MAPBOX_BASE_URL}/{coords}"
            traffic_resp = await client.get(traffic_url, params=common_params)
            traffic_resp.raise_for_status()
            traffic_data = traffic_resp.json()
        except httpx.HTTPStatusError as e:
            return {
                "status": "RED",
                "duration": None,
                "time_loss": None,
                "reason": f"Mapbox API error: {e.response.status_code}"
            }
        except Exception as e:
            return {
                "status": "RED",
                "duration": None,
                "time_loss": None,
                "reason": f"Network error contacting Mapbox: {str(e)}"
            }

        routes = traffic_data.get("routes", [])
        if not routes:
            return {
                "status": "RED",
                "duration": None,
                "time_loss": None,
                "reason": "No route found between the given coordinates"
            }

        traffic_duration_sec = routes[0]["duration"]  # seconds with live traffic

        # --- (2) Free-flow baseline (driving without traffic) ---
        try:
            baseline_url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{coords}"
            baseline_resp = await client.get(baseline_url, params=common_params)
            baseline_resp.raise_for_status()
            baseline_data = baseline_resp.json()
            baseline_routes = baseline_data.get("routes", [])
            baseline_duration_sec = baseline_routes[0]["duration"] if baseline_routes else traffic_duration_sec
        except Exception:
            # Fall back: treat current duration as baseline if second call fails
            baseline_duration_sec = traffic_duration_sec

    delay_sec = max(0.0, traffic_duration_sec - baseline_duration_sec)
    duration_minutes = round(traffic_duration_sec / 60, 1)
    delay_minutes = round(delay_sec / 60, 1)

    # --- Classification ---
    if delay_sec > DELAY_THRESHOLD_SECONDS:
        return {
            "status": "YELLOW",
            "duration": duration_minutes,
            "time_loss": delay_minutes,
            "reason": f"Traffic congestion adding {delay_minutes} min delay"
        }
    else:
        return {
            "status": "GREEN",
            "duration": duration_minutes,
            "time_loss": delay_minutes,
            "reason": "Route clear, no significant delay"
        }

"""
Zone State REST API Router
--------------------------
Exposes real-time zone state data with full signal breakdown.

Endpoints:
  GET /zone-state/all      → All zones with current state + signal breakdown
  GET /zone-state/{id}     → Single zone with detailed signal scores
  GET /zone-state/signals  → Raw signal scores per zone (weather/traffic/demand/disruption)
  POST /zone-state/refresh → Force immediate re-fetch from all APIs (admin/demo)
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from core.logger import logger
from services.zone_state_engine import zone_state_engine
from services.city_graph_service import city_graph, ZONE_DEFINITIONS
from services.news_fetcher_service import news_fetcher_service

router = APIRouter(prefix="/zone-state", tags=["Zone State Engine"])


@router.get("/all")
async def get_all_zone_states():
    """
    Returns all 9 zones with their current state and the signals that drove it.
    This is the canonical real-world zone view.
    """
    zones = city_graph.get_all_zones()
    zone_map = {z["id"]: z for z in zones}

    result = []
    for z_def in ZONE_DEFINITIONS:
        zid   = z_def["id"]
        z_db  = zone_map.get(zid, {})
        decision = zone_state_engine.compute_zone_state(zid)

        result.append({
            "zone_id":    zid,
            "zone_name":  z_def["name"],
            "lat":        z_def["lat"],
            "lon":        z_def["lon"],
            "state":      z_db.get("state", decision["state"]),
            "risk_score": z_db.get("risk_score", decision["risk_score"]),
            "reason":     decision["reason"],
            "data_source": "real_world_apis",
            "signals": {
                "weather":    decision["signals"]["weather"],
                "traffic":    decision["signals"]["traffic"],
                "disruption": decision["signals"]["disruption"],
                "demand":     decision["signals"]["demand"],
            },
            "computed_at": decision["computed_at"],
        })

    return {
        "success":    True,
        "total_zones": len(result),
        "data_mode":  "REAL_WORLD",
        "zones":      result,
    }


@router.get("/signals")
async def get_all_zone_signals():
    """
    Raw signal breakdown per zone — shows exactly what real-world data
    drove each zone's current state.
    Perfect for debugging and transparency.
    """
    signals = zone_state_engine.get_all_signals()
    return {
        "success":   True,
        "data_mode": "REAL_WORLD",
        "signals":   signals,
    }


@router.get("/{zone_id}")
async def get_zone_state(zone_id: str):
    """
    Get detailed state + signal breakdown for a single zone.
    Shows exactly which real-world API drove the current color.
    """
    zone_id = zone_id.upper()
    valid_ids = {z["id"] for z in ZONE_DEFINITIONS}
    if zone_id not in valid_ids:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found")

    zone_def = next(z for z in ZONE_DEFINITIONS if z["id"] == zone_id)
    z_db     = city_graph.get_zone(zone_id) or {}
    decision = zone_state_engine.compute_zone_state(zone_id)

    return {
        "success":    True,
        "zone_id":    zone_id,
        "zone_name":  zone_def["name"],
        "lat":        zone_def["lat"],
        "lon":        zone_def["lon"],
        "state":      z_db.get("state", decision["state"]),
        "risk_score": z_db.get("risk_score", decision["risk_score"]),
        "reason":     decision["reason"],
        "data_source": "real_world_apis",
        "signals":    decision["signals"],
        "computed_at": decision["computed_at"],
        "zone_metadata": {
            "orders_per_minute":  z_db.get("orders_per_minute"),
            "baseline_orders":    z_db.get("baseline_orders"),
            "demand_score":       z_db.get("demand_score"),
            "delay_factor":       z_db.get("delay_factor"),
            "pool_balance":       z_db.get("pool_balance"),
            "active_restaurants": z_db.get("active_restaurants"),
        },
    }


@router.post("/refresh")
async def force_refresh(background_tasks: BackgroundTasks):
    """
    Force an immediate re-fetch from all real-world APIs.
    Used in demo mode to show live data on demand.
    """
    from services.weather_ingestion_service import fetch_all_zones_weather
    from services.traffic_ingestion_service import fetch_all_zones_traffic
    from services.demand_ingestion_service import compute_zone_demand_scores

    async def _refresh():
        logger.info("[ZSE-API] Forced refresh requested...")
        try:
            await fetch_all_zones_weather()
        except Exception as e:
            logger.warning(f"[ZSE-API] Weather refresh failed: {e}")
        try:
            await fetch_all_zones_traffic()
        except Exception as e:
            logger.warning(f"[ZSE-API] Traffic refresh failed: {e}")
        try:
            await compute_zone_demand_scores()
        except Exception as e:
            logger.warning(f"[ZSE-API] Demand refresh failed: {e}")
        await zone_state_engine.recompute_all(source="manual_refresh")
        logger.info("[ZSE-API] Forced refresh complete")

    background_tasks.add_task(_refresh)

    return {
        "success": True,
        "message": "Refresh queued — all real-world APIs will be re-fetched within seconds",
        "zones":   len(ZONE_DEFINITIONS),
    }

@router.get("/intelligence")
async def get_live_intelligence():
    """
    Returns the parsed GDELT news feed along with calculated Tone and Impact scores
    suitable for the Live Intelligence Feed UI.
    """
    gdelt_data = news_fetcher_service._gdelt_cache.get("Chennai", {})
    articles = gdelt_data.get("articles", [])
    
    feed = []
    
    # We slice to 30 items to not overwhelm the UI
    for art in articles[:30]:
        title = art.get("title", "")
        if not title: continue
        
        # Simple deterministic parser based on the implementation plan
        title_low = title.lower()
        score = 0.5
        tone = "NEUTRAL"
        icon = "📰"
        
        if any(w in title_low for w in ["strike", "protest", "riot", "clash", "violence", "bandh"]):
            score = 0.85
            tone = "NEGATIVE"
            icon = "⚠️"
        elif any(w in title_low for w in ["rain", "storm", "flood", "weather", "cyclone"]):
            score = 0.70
            tone = "NEGATIVE"
            icon = "🌧️"
        elif any(w in title_low for w in ["traffic", "crash", "block", "delay", "congestion"]):
            score = 0.65
            tone = "NEGATIVE"
            icon = "🚗"
        elif any(w in title_low for w in ["festival", "celebrate", "launch", "economic", "growth"]):
            score = 0.20
            tone = "POSITIVE"
            icon = "📈"
            
        feed.append({
            "id": art.get("url", "") or title, # pseudo-id
            "title": title,
            "timestamp": art.get("timestamp", ""),
            "tone": tone,
            "impact_score": score,
            "icon": icon,
            "source": art.get("source", "gdelt")
        })
        
    return {
        "success": True,
        "count": len(feed),
        "feed": feed
    }

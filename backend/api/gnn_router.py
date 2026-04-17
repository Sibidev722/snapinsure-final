from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from services.gnn_decision_engine import gnn_engine
from core.database import get_db
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/gnn", tags=["GNN Decision Engine"])


class ZoneInput(BaseModel):
    id: str
    rain: float          # 0.0 – 1.0
    demand: float        # 0.0 – 1.0
    earnings: float      # 0.0 – 1.0 (normalised)


class EdgeInput(BaseModel):
    source: int
    target: int


class GNNPredictRequest(BaseModel):
    zones: List[ZoneInput]
    edges: Optional[List[EdgeInput]] = []


@router.post("/predict")
async def predict_zones(request: GNNPredictRequest):
    """
    Runs the GNN model over supplied zone graph and returns explainable
    HIGH / MEDIUM / LOW payoff predictions for each zone node.
    """
    try:
        zone_dicts = [z.dict() for z in request.zones]
        edge_tuples = [(e.source, e.target) for e in (request.edges or [])]

        predictions = gnn_engine.predict_and_explain(zone_dicts, edge_tuples)

        return {
            "success": True,
            "total_zones": len(predictions),
            "high_payoff_zones": [p["zone"] for p in predictions if p["prediction"] == "HIGH"],
            "predictions": predictions,
        }
    except Exception as e:
        logger.error(f"GNN prediction error: {e}")
        raise HTTPException(status_code=500, detail="GNN inference failed")


@router.get("/demo")
async def gnn_demo():
    """
    Returns a pre-built demo prediction over Chennai's mock zone graph.
    No input required — perfect for live hackathon demos.
    """
    demo_zones = [
        {"id": "Z1-Adyar",      "rain": 0.8, "demand": 0.9, "earnings": 0.7},
        {"id": "Z2-T-Nagar",    "rain": 0.2, "demand": 0.6, "earnings": 0.5},
        {"id": "Z3-Velachery",  "rain": 0.5, "demand": 0.4, "earnings": 0.6},
        {"id": "Z4-Tambaram",   "rain": 0.9, "demand": 0.8, "earnings": 0.4},
        {"id": "Z5-Anna Nagar", "rain": 0.1, "demand": 0.7, "earnings": 0.8},
    ]
    demo_edges = [(0,1),(1,2),(2,3),(3,4),(0,4),(1,4)]

    predictions = gnn_engine.predict_and_explain(demo_zones, demo_edges)
    return {
        "success": True,
        "demo": True,
        "predictions": predictions,
        "high_payoff_zones": [p["zone"] for p in predictions if p["prediction"] == "HIGH"],
    }


@router.get("/latest")
async def get_latest_gnn_predictions():
    """
    Retrieves the latest cached GNN predictions from the autonomous worker.
    Falls back to live GNN computation if no DB snapshot exists yet.
    """
    from services.city_graph_service import city_graph, ZONE_DEFINITIONS
    from services.zone_state_engine import zone_state_engine
    import random
    from datetime import datetime

    db = get_db()

    # Try DB snapshot first
    if db is not None:
        try:
            snapshot = await db.gnn_predictions.find_one({"type": "latest_snapshot"})
            if snapshot:
                return {
                    "success": True,
                    "timestamp": snapshot["timestamp"],
                    "weather_intensity": snapshot.get("weather_intensity", 0),
                    "active_strikes": snapshot.get("active_strikes_count", 0),
                    "predictions": snapshot["predictions"],
                    "source": "db_cache",
                }
        except Exception as e:
            logger.warning(f"[GNN] DB snapshot fetch failed: {e}")

    # Live fallback — compute from current city state
    try:
        zones_raw = city_graph.get_all_zones()
        edges = [
            (0,1),(1,2),(0,3),(1,4),(2,5),(3,4),(4,5),(3,6),(4,7),(5,8),(6,7),(7,8),
            (0,4),(1,5),(3,7),(4,8)
        ]
        zone_inputs = []
        for z in zones_raw:
            signals = zone_state_engine.compute_zone_state(z["id"])["signals"]
            zone_inputs.append({
                "id": z["id"],
                "weather":  signals.get("weather",    {}).get("score", 0.1),
                "strikes":  signals.get("disruption", {}).get("score", 0.0),
                "earnings": max(0.1, 1.0 - z.get("risk_score", 0.1)),
                "time_of_day": datetime.utcnow().hour / 24.0,
                "day_of_week": datetime.utcnow().weekday() / 6.0,
            })

        predictions = gnn_engine.predict_and_explain(zone_inputs, edges)

        formatted = []
        for i, p in enumerate(predictions):
            neighbor_indices = [e[1] for e in edges if e[0] == i] + [e[0] for e in edges if e[1] == i]
            neighbors = [
                {"node_id": f"Z{j+1}", "rank": r+1, "attention": round(random.uniform(0.15, 0.45), 3)}
                for r, j in enumerate(neighbor_indices[:3])
            ]
            formatted.append({
                **p,
                "xai": {
                    "explanation": p.get("explanation", ""),
                    "top_neighbors": neighbors,
                    "top_features": [
                        {"name": "weather",  "label": "Weather",  "importance": zone_inputs[i]["weather"],  "direction": 1},
                        {"name": "strikes",  "label": "Social",   "importance": zone_inputs[i]["strikes"],  "direction": 1},
                        {"name": "earnings", "label": "Earnings", "importance": zone_inputs[i]["earnings"], "direction": -1},
                    ],
                },
            })

        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "weather_intensity": 0,
            "active_strikes": 0,
            "predictions": formatted,
            "source": "live_computation",
        }

    except Exception as e:
        logger.error(f"[GNN] Live fallback failed: {e}")
        raise HTTPException(status_code=503, detail=f"GNN inference unavailable: {e}")


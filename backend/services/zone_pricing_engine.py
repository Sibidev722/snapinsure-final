"""
Dynamic Zone Pricing Engine
---------------------------
Calculates the real-time price for gig worker engagements in a specific zone.
Factors in:
- Inherent Zone Demand
- Local Zone Risk
- Global Weather Impact
- Active NLP Disruption Events (like strikes)
"""

from core.database import get_db
from datetime import datetime
from services.city_graph_service import city_graph

class ZonePricingEngine:
    async def compute_price(self, zone_id: str) -> dict:
        db = get_db()
        base_price = 100.0
        
        # 1. Zone Demand & Risk
        zone = city_graph.get_zone(zone_id)
        if not zone:
            return {
                "base_price": base_price,
                "final_price": base_price,
                "surge": 1.0,
                "error": "Zone not found"
            }
        
        demand = zone.get("demand_score", 1.0)
        risk = zone.get("risk_score", 0.1)
        
        # 2. Weather Impact
        weather_multiplier = 1.0
        if db is not None:
            weather_doc = await db.weather_state.find_one({"city": "Chennai"})
            if weather_doc and "impact" in weather_doc:
                weather_multiplier = weather_doc["impact"]["demand_multiplier"]
        
        # 3. Active NLP Strike Disruption Events
        active_events = 0
        if db is not None:
             active_events = await db.real_events.count_documents({"zone_id": zone_id, "status": "active"})
             
        event_multiplier = 1.0 + (0.45 * active_events) # Heavy surge for active strikes
        
        # 4. Compute Dynamic Surge
        norm_demand = 0.5 + (demand * 0.5)
        norm_risk = 1.0 + (risk * 0.5)
        
        surge = norm_demand * norm_risk * weather_multiplier * event_multiplier
        surge = round(max(1.0, min(surge, 5.0)), 2) # Cap surge to 5.0x max for realism
        
        final_price = round(base_price * surge)
        
        doc = {
            "zone_id": zone_id,
            "base_price": base_price,
            "final_price": final_price,
            "surge": surge,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # 5. Automatically write dynamic prices back to MongoDB cache
        if db is not None:
             await db["zone_prices"].update_one(
                 {"zone_id": zone_id},
                 {"$set": doc},
                 upsert=True
             )
             
        return {
            "base_price": base_price,
            "final_price": final_price,
            "surge": surge
        }

zone_pricing_engine = ZonePricingEngine()

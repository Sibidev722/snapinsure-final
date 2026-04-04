from services.risk_service import risk_engine
from services.route_service import route_intel_engine
from models.models import ZoneState

class TriggerEngine:
    async def process_weather(self, zone_id: str, rain_intensity: float, db):
        risk_score = 0.0
        reason = "Normal weather"
        if rain_intensity > 50:
            risk_score = 1.0
            reason = f"Severe rain intensity ({rain_intensity})"
        elif rain_intensity > 30:
            risk_score = 0.5
            reason = f"Moderate rain intensity ({rain_intensity})"
        
        if risk_score > 0:
            result = await risk_engine.update_risk_and_propagate(zone_id, risk_score, db)
            return {"updated_zone_state": result, "reason": reason}
            
        return {"updated_zone_state": {"zone_id": zone_id, "state": ZoneState.GREEN}, "reason": reason}

    async def process_traffic(self, zone_id: str, delay_minutes: int, db):
        risk_score = 0.0
        reason = "Normal traffic"
        if delay_minutes > 60:
            risk_score = 1.0
            reason = f"Severe traffic delay ({delay_minutes} mins)"
        elif delay_minutes > 30:
            risk_score = 0.5
            reason = f"Moderate traffic delay ({delay_minutes} mins)"
            
        if risk_score > 0:
            result = await risk_engine.update_risk_and_propagate(zone_id, risk_score, db)
            return {"updated_zone_state": result, "reason": reason}
            
        return {"updated_zone_state": {"zone_id": zone_id, "state": ZoneState.GREEN}, "reason": reason}

    async def process_strike(self, zone_id: str, text_data: str, db):
        text_lower = text_data.lower()
        if "strike" in text_lower or "protest" in text_lower:
            risk_score = 1.0
            reason = "Strike/Protest detected from text"
            result = await risk_engine.update_risk_and_propagate(zone_id, risk_score, db)
            return {"updated_zone_state": result, "reason": reason}
            
        return {"updated_zone_state": {"zone_id": zone_id, "state": ZoneState.GREEN}, "reason": "No strike/protest detected"}

    async def process_route_block(self, source_zone: str, target_zone: str, db):
        path = route_intel_engine.get_shortest_path(source_zone, target_zone)
        if not path: # No route exists
            risk_score = 1.0
            reason = f"No route exists from {source_zone} to {target_zone}"
            result = await risk_engine.update_risk_and_propagate(source_zone, risk_score, db)
            return {"updated_zone_state": result, "reason": reason}
            
        return {"updated_zone_state": {"zone_id": source_zone, "state": ZoneState.GREEN}, "reason": f"Route exists (Length: {len(path)-1})"}

trigger_engine = TriggerEngine()

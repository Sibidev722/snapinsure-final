from models.models import ZoneState
from services.payout_service import payout_engine
from services.route_service import route_intel_engine
import logging

class RiskEngine:
    def determine_state(self, risk_score: float) -> ZoneState:
        if risk_score > 0.7:
            return ZoneState.RED
        elif risk_score >= 0.4:
            return ZoneState.YELLOW
        else:
            return ZoneState.GREEN

    async def evaluate_live_risk(self, zone_id: str, city: str, transit_origin: str, transit_dest: str, db):
        from services.weather_service import weather_service
        from services.traffic_service import traffic_service
        from services.nlp_service import nlp_service
        import logging
        
        # 1. Concurrently poll all autonomous external AI sources
        weather_data = await weather_service.get_weather_risk(city)
        traffic_data = traffic_service.get_traffic_delay(transit_origin, transit_dest)
        nlp_data = nlp_service.analyze_city_disruptions(city)
        
        w_risk = weather_data.get("risk_score", 0.1)
        t_loss = traffic_data.get("time_loss_minutes", 0)
        t_risk = 0.9 if t_loss > 30 else (0.5 if t_loss > 10 else 0.1)
        n_risk = nlp_data.get("risk_score", 0.1)
        
        # Highest risk overrides to ensure maximal safety coverage
        final_risk = max(w_risk, t_risk, n_risk)
        final_state = self.determine_state(final_risk)
        
        decision = {
            "zone_id": zone_id,
            "final_risk_score": final_risk,
            "system_state": final_state.value,
            "telemetry": {
                "weather": weather_data,
                "traffic": traffic_data,
                "nlp": nlp_data
            }
        }
        
        logging.info(f"Unified Risk computation completed for {zone_id}. Score: {final_risk}")
        await self.update_risk_and_propagate(zone_id, final_risk, db)
        return decision

    async def get_unified_risk_for_city(self, city: str):
        """
        Unified Risk Engine combining all APIs.
        risk_score = 0.4 * weather_risk + 0.4 * traffic_risk + 0.2 * strike_risk
        """
        from services.weather_service import weather_service
        from services.traffic_service import traffic_service
        from services.nlp_service import get_nlp_risk
        import asyncio
        from datetime import datetime

        # 1. Call all APIs concurrently for performance
        tasks = [
            weather_service.get_weather(city),
            traffic_service.get_traffic_delay(f"{city} City Center", f"{city} Airport"),
            get_nlp_risk(city)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 2. Extract results & handle errors
        weather_data = results[0] if not isinstance(results[0], Exception) else {"risk_score": 0.5, "confidence": 40}
        traffic_data = results[1] if not isinstance(results[1], Exception) else {"time_loss_minutes": 0, "confidence": 50}
        nlp_data     = results[2] if not isinstance(results[2], Exception) else {"zone": "YELLOW", "articles_scanned": 0}

        # 3. Compute Individual Risks
        weather_risk = weather_data.get("risk_score", 0.1)
        
        delay = traffic_data.get("time_loss_minutes", 0)
        traffic_risk = 0.9 if delay > 30 else (0.5 if delay > 10 else 0.1)
        
        nlp_zone = nlp_data.get("zone", "GREEN")
        strike_risk = 0.9 if nlp_zone == "RED" else (0.5 if nlp_zone == "YELLOW" else 0.1)

        # 4. Calculate weighted risk
        final_risk_score = round((0.4 * weather_risk) + (0.4 * traffic_risk) + (0.2 * strike_risk), 2)

        # 5. Compute Aggregate Confidence
        # Average of individual confidences
        w_conf = weather_data.get("confidence", 50)
        t_conf = traffic_data.get("confidence", 50)
        n_conf = 90 if nlp_data.get("articles_scanned", 0) > 5 else 60
        avg_confidence = (w_conf + t_conf + n_conf) // 3

        # 6. Final State & Factors
        if final_risk_score > 0.7:
            zone_color = "RED"
        elif final_risk_score >= 0.4:
            zone_color = "YELLOW"
        else:
            zone_color = "GREEN"

        factors = []
        if weather_risk > 0.5: factors.append("rain")
        if traffic_risk > 0.5: factors.append("traffic")
        if strike_risk > 0.5: factors.append("strike")

        now_iso = datetime.utcnow().isoformat()
        
        return {
            "zone": zone_color,
            "risk_score": final_risk_score,
            "factors": factors,
            "confidence": f"{avg_confidence}%",
            "timestamp": now_iso,
            "last_updated": now_iso
        }

    async def update_risk_and_propagate(self, zone_id: str, new_score: float, db):
        """
        Updates a core zone's risk score and propagates 50% of it to immediate neighbors.
        """
        updates = {}
        
        # 1. Update Core Node
        updates[zone_id] = new_score
        
        # 2. Propagate to neighbors (Simulating GNN Behavior)
        neighbors = route_intel_engine.get_adjacent_zones(zone_id)
        for neighbor in neighbors:
            if neighbor not in updates: # Prevent backwards looping in immediate graph
                # Neighbor gets half the risk
                propagated_score = new_score * 0.5
                updates[neighbor] = propagated_score

        results = []
        for z_id, score in updates.items():
            result = await self._apply_risk_update(z_id, score, db)
            if result:
                results.append(result)

        return {
            "origin_zone": zone_id,
            "propagated_zones": neighbors,
            "updated_states": results
        }

    async def _apply_risk_update(self, zone_id: str, risk_score: float, db):
        zone = await db["zones"].find_one({"_id": zone_id})
        if not zone:
            return None

        new_state = self.determine_state(risk_score)
        old_state = zone.get("state")
        old_score = zone.get("risk_score", 0.0)

        # Merge new risk score (could take max of existing vs new)
        final_score = max(old_score, risk_score)
        final_state = self.determine_state(final_score)

        if final_score == old_score and final_state == old_state:
            return {"zone_id": zone_id, "score": final_score, "state": final_state, "changed": False}

        await db["zones"].update_one(
            {"_id": zone_id},
            {"$set": {
                "risk_score": final_score,
                "state": final_state
            }}
        )

        # Automatically trigger Payout Engine if state worsened to YELLOW or RED
        if final_state in [ZoneState.YELLOW, ZoneState.RED] and final_state != old_state:
            logging.info(f"Triggering automated payouts for zone {zone_id} due to state {final_state}")
            await payout_engine.process_payouts_for_zone(zone_id, final_state, db)

        return {"zone_id": zone_id, "score": final_score, "state": final_state, "changed": True}

risk_engine = RiskEngine()

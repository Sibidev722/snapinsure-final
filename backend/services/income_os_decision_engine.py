from typing import Dict, Optional
from core.database import get_db
from services.city_graph_service import city_graph
from services.zone_pricing_engine import zone_pricing_engine
from datetime import datetime

class IncomeOSDecisionEngine:
    async def generate_decision(self, worker_id: str, zone_id: str) -> Dict:
        """
        Calculates a MOVE/STAY decision for a gig worker based on 
        real-time grid intelligence (demand, surge, and risk).
        """
        db = get_db()
        
        # 1. Fetch Zone Fundamentals
        zone = city_graph.get_zone(zone_id)
        if not zone:
            return {
                "decision": "WAIT",
                "reason": "Zone intelligence offline",
                "confidence": 0.5,
                "score": 0
            }
        
        demand = zone.get("demand_score", 0.5)
        risk = zone.get("risk_score", 0.1)
        
        # 2. Fetch Real-time Surge (Factors in Weather + Strikes)
        pricing = await zone_pricing_engine.compute_price(zone_id)
        surge = pricing.get("surge", 1.0)
        
        # 3. Decision Formula: score = demand + surge - risk
        # Scaling: demand (0-1), surge (1-5), risk (0-1).
        # Typical Score Range: ~0.5 to ~5.9
        score = round(demand + surge - risk, 2)
        
        # 4. Intelligence-Based Reasoning
        reason = "Market conditions are stable."
        confidence = 0.85
        
        # Fetch contextual data for high-fidelity reasoning
        weather_desc = "Clear"
        if db is not None:
             weather_doc = await db.weather_state.find_one({"city": "Chennai"})
             if weather_doc:
                 weather_desc = weather_doc.get("description", "Clear")
                 
             active_strikes = await db.real_events.count_documents({
                 "zone_id": zone_id, 
                 "status": "active",
                 "type": {"$in": ["strike", "protest"]}
             })
        else:
            active_strikes = 0

        # Build Reasoning String
        reasons = []
        if surge > 1.2:
            reasons.append(f"High surge ({surge}x)")
        if "rain" in weather_desc.lower() or "storm" in weather_desc.lower():
            reasons.append(f"Weather ({weather_desc})")
        if active_strikes > 0:
            reasons.append(f"Local Strikes")
        
        if reasons:
            reason = f"High opportunity due to {' + '.join(reasons)}"
        elif score < 1.5:
            reason = "Low demand and potential risks detected."
            
        # 5. Final Decision Logic
        # Threshold: > 2.2 is usually a strong STAY (e.g., Demand 0.7 + Surge 1.6 - Risk 0.1)
        decision = "STAY" if score >= 2.2 else "MOVE"
        
        # Refine confidence based on score extremities
        if score > 3.0 or score < 1.0:
            confidence = 0.95
            
        return {
            "worker_id": worker_id,
            "zone_id": zone_id,
            "decision": decision,
            "reason": reason,
            "confidence": confidence,
            "score": score,
            "timestamp": datetime.utcnow().isoformat()
        }

income_os_decision_engine = IncomeOSDecisionEngine()

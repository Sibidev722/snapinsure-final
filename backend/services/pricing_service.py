from models.models import PricingRequest, PricingResponse, ZoneState
import random

class DynamicPricingEngine:
    async def calculate_premium(self, request: PricingRequest, db) -> PricingResponse:
        # Base values
        base_rate = 0.5  # $0.5 per minute
        risk_multiplier = 1.0
        
        # Calculate risk factor based on requested route zones
        zones_cursor = db["zones"].find({"_id": {"$in": request.route_zones}})
        zones = await zones_cursor.to_list(length=100)
        
        for zone in zones:
            state = zone.get("state", ZoneState.GREEN)
            if state == ZoneState.YELLOW:
                risk_multiplier += 0.2
            elif state == ZoneState.RED:
                risk_multiplier += 0.5
                
        # Simulated AI/ML demand surge factor
        surge_factor = random.uniform(1.0, 1.5)
        
        total_premium = base_rate * request.duration_minutes * risk_multiplier * surge_factor
        coverage_amount = total_premium * 20  # Arbitrary coverage multiplier
        
        return PricingResponse(
            premium=round(total_premium, 2),
            coverage=round(coverage_amount, 2),
            risk_factor=round(risk_multiplier * surge_factor, 2),
            explanation=f"Base premium adapted by {risk_multiplier}x zone risk factor and {round(surge_factor, 2)}x surge factor."
        )

pricing_engine = DynamicPricingEngine()

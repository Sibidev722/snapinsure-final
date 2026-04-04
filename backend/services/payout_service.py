from models.models import PayoutReason, Payout, ZoneState
from datetime import datetime
import uuid

class PayoutEngine:
    HOURLY_INCOME = 20.0
    AVG_PEAK_INCOME = 35.0
    AVG_NORMAL_INCOME = 15.0
    PEAK_HOURS_LOST = 4.0
    NORMAL_HOURS_LOST = 6.0

    async def calculate_automated_payout(self, user_id: str, zone_state: str, time_loss: float, db) -> dict:
        """
        Calculates and credits a zero-claim payout for a user based on disruption severity.
        RED: Full payout based on peak/normal income and hours
        YELLOW: Partial payout based on hourly income and time loss
        GREEN: No payout
        """
        if zone_state == ZoneState.GREEN:
            payout_amount = 0.0
            reason = "No disruption, optimal route."
        elif zone_state == ZoneState.YELLOW:
            payout_amount = self.HOURLY_INCOME * time_loss
            reason = "Moderate disruption: delay compensation"
        elif zone_state == ZoneState.RED:
            payout_amount = (self.AVG_PEAK_INCOME * self.PEAK_HOURS_LOST) + (self.AVG_NORMAL_INCOME * self.NORMAL_HOURS_LOST)
            reason = "Heavy disruption: zero-claim payout triggered"
        else:
            payout_amount = 0.0
            reason = "Unknown zone state"

        if payout_amount > 0:
            payout = Payout(
                _id=str(uuid.uuid4()),
                user_id=user_id,
                policy_id="AUTO_GENERATED", 
                amount=payout_amount,
                reason=PayoutReason.DELAY if zone_state == ZoneState.YELLOW else PayoutReason.NO_WORK,
                zone_id="AUTO_TRIGGERED"
            )
            # Insert payout record into database
            await db["payouts"].insert_one(payout.dict(by_alias=True))

        return {
            "payout": payout_amount,
            "status": "AUTO-CREDITED",
            "reason": reason
        }

    async def process_payouts_for_zone(self, zone_id: str, state: str, db):
        """
        Triggered when a zone changes state to YELLOW or RED.
        Automatically finds all active policies intersecting this zone and processes payouts.
        """
        if state == ZoneState.GREEN:
            return [] # No payout for returning to normal
            
        reason = PayoutReason.NO_WORK if state == ZoneState.RED else PayoutReason.DELAY
        
        # Find active policies containing the zone_id
        now = datetime.utcnow()
        cursor = db["policies"].find({
            "is_active": True,
            "route_zones": zone_id,
            "end_time": {"$gte": now}
        })
        
        policies = await cursor.to_list(length=1000)
        processed_payouts = []
        
        for policy in policies:
            # Calculate amount (RED = full, YELLOW = partial)
            coverage = policy["coverage_amount"]
            payout_amount = coverage if state == ZoneState.RED else coverage * 0.3
            
            payout = Payout(
                _id=str(uuid.uuid4()),
                user_id=policy["user_id"],
                policy_id=policy["_id"],
                amount=payout_amount,
                reason=reason,
                zone_id=zone_id
            )
            
            # Save payout to DB
            await db["payouts"].insert_one(payout.dict(by_alias=True))
            processed_payouts.append(payout.dict(by_alias=True))
            
            # Optionally mark policy as inactive if fully claimed (RED)
            if state == ZoneState.RED:
                await db["policies"].update_one(
                    {"_id": policy["_id"]},
                    {"$set": {"is_active": False}}
                )
                
        return processed_payouts

payout_engine = PayoutEngine()

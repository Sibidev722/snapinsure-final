"""
Gig Worker Service
------------------
Core business logic for the 6-module Gig Worker Insurance Flow:

  Module 1 – Authentication    : validate_login()
  Module 2 – Verification      : verify_worker()
  Module 3 – Risk Validation   : get_zone_status_for_user()
  Module 4 – Eligibility       : check_eligibility()
  Module 5 – Zero-Claim Payout : trigger_auto_payout()
  Module 6 – Dashboard         : get_dashboard()

All external API calls (weather, NLP) are reused from existing services.
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any

from core.logger import logger
from core.mock_workers import (
    SUPPORTED_CITIES,
    SUPPORTED_COMPANIES,
    get_worker_by_credentials,
    get_worker_by_id,
)


# ─────────────────────────────────────────────────────────────────────────────
# Payout constants (can be overridden per-worker using avg_income)
# ─────────────────────────────────────────────────────────────────────────────
RED_PAYOUT_MULTIPLIER    = 0.20   # 20 % of avg daily income for full RED disruption
YELLOW_PAYOUT_MULTIPLIER = 0.10   # 10 % of avg daily income for partial disruption
FLAT_RED_PAYOUT          = 150.0  # Minimum guaranteed payout on RED
FLAT_YELLOW_PAYOUT       = 75.0   # Minimum guaranteed payout on YELLOW


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 1 – GIG WORKER LOGIN
# ─────────────────────────────────────────────────────────────────────────────
async def validate_login(worker_id: str, phone: str, company: str) -> Dict[str, Any]:
    """
    Simulated platform OAuth login.
    Matches credentials against the mock worker registry.

    Returns a structured login response.
    """
    if company not in SUPPORTED_COMPANIES:
        return {
            "success": False,
            "verified": False,
            "message": f"Platform '{company}' is not supported. "
                       f"Supported platforms: {', '.join(sorted(SUPPORTED_COMPANIES))}",
        }

    worker = get_worker_by_credentials(worker_id, phone, company)

    if not worker:
        return {
            "success": False,
            "verified": False,
            "message": "Invalid credentials. Worker ID, phone, or company mismatch.",
        }

    logger.info(f"[LOGIN] Worker {worker_id} authenticated via {company}")

    return {
        "success": True,
        "user_id": worker["worker_id"],
        "company": worker["company"],
        "verified": True,
        "name": worker["name"],
        "city": worker["city"],
        "message": f"Welcome back, {worker['name']}! You are now protected by SnapInsure.",
        "session_token": f"snp_{uuid.uuid4().hex[:24]}",
        "expires_at": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 2 – WORKER VERIFICATION ENGINE
# ─────────────────────────────────────────────────────────────────────────────
async def verify_worker(worker_id: str) -> Dict[str, Any]:
    """
    Post-login verification pipeline.
    Checks:
      1. Worker exists in the registry
      2. Worker account is active
      3. Worker belongs to a supported platform
      4. Worker's city is covered by SnapInsure
    """
    worker = get_worker_by_id(worker_id)

    if not worker:
        return {
            "success": False,
            "status": "NOT_FOUND",
            "message": f"Worker '{worker_id}' not found in the SnapInsure registry.",
        }

    checks = {
        "worker_exists": True,
        "is_active": worker["is_active"],
        "platform_supported": worker["company"] in SUPPORTED_COMPANIES,
        "city_covered": worker["city"] in SUPPORTED_CITIES,
    }

    if not worker["is_active"]:
        return {
            "success": False,
            "status": "INACTIVE",
            "worker_id": worker_id,
            "company": worker["company"],
            "city": worker["city"],
            "checks": checks,
            "message": "Worker account is currently inactive on the platform.",
        }

    if not checks["city_covered"]:
        return {
            "success": False,
            "status": "CITY_NOT_COVERED",
            "worker_id": worker_id,
            "company": worker["company"],
            "city": worker["city"],
            "checks": checks,
            "message": f"SnapInsure does not yet cover {worker['city']}.",
        }

    logger.info(f"[VERIFY] Worker {worker_id} fully verified — {worker['company']}, {worker['city']}")

    return {
        "success": True,
        "status": "VERIFIED",
        "worker_id": worker_id,
        "company": worker["company"],
        "city": worker["city"],
        "name": worker["name"],
        "checks": checks,
        "message": "Worker fully verified and eligible for SnapInsure protection.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 3 – LOCATION + RISK VALIDATION (per user)
# ─────────────────────────────────────────────────────────────────────────────
async def get_zone_status_for_user(worker_id: str) -> Dict[str, Any]:
    """
    Fetches real-time risk data for the worker's city.
    Combines:
      - OpenWeather API (live rainfall/wind data)
      - NLP disruption analysis (news headlines)
      - Traffic estimate (Google Maps / Mapbox / fallback)

    Returns a risk score, zone colour, and reasons list.
    """
    worker = get_worker_by_id(worker_id)
    if not worker:
        return {
            "success": False,
            "message": f"Worker '{worker_id}' not found.",
        }

    city = worker["city"]

    # ── Import real services (lazy to avoid circular imports) ─────────────────
    from services.weather_service import weather_service
    from services.nlp_service import get_nlp_risk
    import asyncio

    # Concurrent fetch – weather + NLP disruptions
    lat = worker.get("lat")
    lon = worker.get("lon")
    weather_task = weather_service.get_weather_risk(city, lat, lon)
    nlp_task     = get_nlp_risk(city)
    results      = await asyncio.gather(weather_task, nlp_task, return_exceptions=True)

    weather_data = results[0] if not isinstance(results[0], Exception) else {
        "risk_score": 0.5, "reason": "Weather API unavailable", "zone": "YELLOW"
    }
    nlp_data = results[1] if not isinstance(results[1], Exception) else {
        "risk_score": 0.3, "zone": "GREEN", "articles_scanned": 0
    }

    # ── Risk score calculation ─────────────────────────────────────────────────
    weather_risk = weather_data.get("risk_score", 0.1)

    nlp_zone     = nlp_data.get("zone", "GREEN")
    strike_risk  = 0.9 if nlp_zone == "RED" else (0.5 if nlp_zone == "YELLOW" else 0.1)

    # Weighted: weather 60 %, nlp/strikes 40 %
    final_risk = round(0.60 * weather_risk + 0.40 * strike_risk, 2)

    if final_risk > 0.7:
        zone = "RED"
    elif final_risk >= 0.4:
        zone = "YELLOW"
    else:
        zone = "GREEN"

    # ── Collect human-readable reasons ────────────────────────────────────────
    reasons = []
    if weather_risk > 0.7:
        reasons.append(weather_data.get("reason", "heavy rain"))
    elif weather_risk > 0.4:
        reasons.append(weather_data.get("reason", "moderate rain"))

    if strike_risk > 0.5:
        reasons.append(nlp_data.get("reason", "strike/disruption reported in city"))

    if not reasons:
        reasons.append("No major disruption detected")

    logger.info(f"[ZONE] {worker_id} @ {city} → {zone} (score={final_risk})")

    return {
        "success": True,
        "user_id": worker_id,
        "city": city,
        "zone": zone,
        "risk_score": final_risk,
        "reason": reasons,
        "weather": weather_data,
        "nlp": nlp_data,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 4 – ELIGIBILITY ENGINE
# ─────────────────────────────────────────────────────────────────────────────
async def check_eligibility(worker_id: str) -> Dict[str, Any]:
    """
    Automatic eligibility decision.
    A worker is eligible for insurance activation if:
      1. They are verified (active, supported platform, covered city)
      2. Their current zone is YELLOW or RED (risk-prone)

    Returns eligible=True and activates insurance automatically.
    """
    # Step 1 – Verification
    verify_result = await verify_worker(worker_id)
    if not verify_result.get("success"):
        return {
            "success": False,
            "eligible": False,
            "reason": verify_result.get("message", "Worker failed verification."),
            "worker_id": worker_id,
        }

    # Step 2 – Zone check
    zone_result = await get_zone_status_for_user(worker_id)
    if not zone_result.get("success"):
        return {
            "success": False,
            "eligible": False,
            "reason": "Unable to determine zone status.",
            "worker_id": worker_id,
        }

    zone       = zone_result["zone"]
    risk_score = zone_result["risk_score"]

    if zone in ("YELLOW", "RED"):
        eligible = True
        reason   = (
            f"User is in a {zone} risk area (score={risk_score}). "
            "Insurance automatically activated."
        )
        policy_status = "AUTO_ACTIVATED"
    else:
        eligible      = False
        reason        = "User is in a GREEN safe zone. No insurance activation required."
        policy_status = "STANDBY"

    logger.info(f"[ELIGIBILITY] {worker_id} → eligible={eligible}, zone={zone}")

    return {
        "success": True,
        "eligible": eligible,
        "worker_id": worker_id,
        "zone": zone,
        "risk_score": risk_score,
        "reason": reason,
        "policy_status": policy_status,
        "company": verify_result["company"],
        "city": verify_result["city"],
        "timestamp": datetime.utcnow().isoformat(),
    }


from services.web3_service import send_payout_tx

# ─────────────────────────────────────────────────────────────────────────────
# MODULE 5 – ZERO-CLAIM AUTOMATIC PAYOUT ENGINE
# ─────────────────────────────────────────────────────────────────────────────
async def trigger_auto_payout(worker_id: str, wallet_address: str = None, db=None) -> Dict[str, Any]:
    """
    Fully automated, zero-claim payout.
    No manual claim allowed — system detects disruption and credits automatically.

    Payout logic:
      RED    → Full income compensation (avg_income × RED_PAYOUT_MULTIPLIER)
      YELLOW → Time-loss compensation   (avg_income × YELLOW_PAYOUT_MULTIPLIER)
      GREEN  → No payout

    Payout is persisted to MongoDB if db is supplied.
    """
    worker = get_worker_by_id(worker_id)
    if not worker:
        return {
            "success": False,
            "status": "FAILED",
            "message": f"Worker '{worker_id}' not found.",
        }

    # ── Live zone check ───────────────────────────────────────────────────────
    zone_result = await get_zone_status_for_user(worker_id)
    zone        = zone_result.get("zone", "GREEN")
    risk_score  = zone_result.get("risk_score", 0.0)
    reasons     = zone_result.get("reason", [])

    avg_income  = worker["avg_income"]

    if zone == "RED":
        amount = max(FLAT_RED_PAYOUT, avg_income * RED_PAYOUT_MULTIPLIER)
        payout_reason = "Heavy disruption — full income compensation"
    elif zone == "YELLOW":
        amount = max(FLAT_YELLOW_PAYOUT, avg_income * YELLOW_PAYOUT_MULTIPLIER)
        payout_reason = "Moderate disruption — time-loss compensation"
    else:
        amount = 0.0
        payout_reason = "No disruption — system in GREEN state"

    amount = round(amount, 2)

    # ── Persist payout to MongoDB ─────────────────────────────────────────────
    if db is not None and amount > 0:
        from models.models import PayoutReason
        payout_doc = {
            "_id": str(uuid.uuid4()),
            "user_id": worker_id,
            "policy_id": "GIG_AUTO",
            "amount": amount,
            "reason": "NO_WORK" if zone == "RED" else "DELAY",
            "zone_id": worker["city"],
            "timestamp": datetime.utcnow(),
        }
        await db["payouts"].insert_one(payout_doc)

        # Update worker protection total in-memory tracking (best-effort)
        worker["last_payout"]       = amount
        worker["total_protection"] += amount

    logger.info(f"[PAYOUT] {worker_id} → ₹{amount} ({zone} zone)")

    tx_hash = None
    if amount > 0 and wallet_address:
        web3_res = await send_payout_tx(wallet_address, amount)
        tx_hash = web3_res.get("tx_hash")

    return {
        "success": True,
        "status": "SUCCESS" if amount > 0 else "NO_PAYOUT",
        "tx_hash": tx_hash,
        "user_id": worker_id,
        "amount": amount,
        "zone": zone,
        "risk_score": risk_score,
        "reason": payout_reason,
        "disruption_factors": reasons,
        "company": worker["company"],
        "city": worker["city"],
        "timestamp": datetime.utcnow().isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 6 – PROTECTION TRACKING DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
async def get_dashboard(worker_id: str, db=None) -> Dict[str, Any]:
    """
    Returns a real-time protection dashboard for the gig worker:
      - current zone
      - verification status
      - company
      - total protection amount
      - last payout
      - payout history (from MongoDB if available)
    """
    worker = get_worker_by_id(worker_id)
    if not worker:
        return {
            "success": False,
            "message": f"Worker '{worker_id}' not found.",
        }

    # Live zone from real APIs
    zone_result = await get_zone_status_for_user(worker_id)
    zone        = zone_result.get("zone", "GREEN")
    risk_score  = zone_result.get("risk_score", 0.0)

    # Verification status
    verify_result = await verify_worker(worker_id)
    verified      = verify_result.get("status") == "VERIFIED"

    # Pull payout history from MongoDB
    total_protection = worker["total_protection"]
    last_payout      = worker["last_payout"]
    payout_history   = []

    if db is not None:
        cursor         = db["payouts"].find({"user_id": worker_id}).sort("timestamp", -1).limit(10)
        payout_history = await cursor.to_list(length=10)

        if payout_history:
            # Recalculate total from DB for accuracy
            all_cursor = db["payouts"].find({"user_id": worker_id})
            all_payouts      = await all_cursor.to_list(length=1000)
            total_protection = sum(p.get("amount", 0) for p in all_payouts) + worker["total_protection"]
            last_payout      = payout_history[0].get("amount", worker["last_payout"])

        # Strip Mongo _id ObjectId for clean serialisation
        for p in payout_history:
            p["_id"] = str(p["_id"])

    logger.info(f"[DASHBOARD] {worker_id} fetched — zone={zone}, protection=₹{total_protection}")

    return {
        "success": True,
        "user_id": worker_id,
        "name": worker["name"],
        "company": worker["company"],
        "city": worker["city"],
        "zone": zone,
        "risk_score": risk_score,
        "verified": verified,
        "total_protection": round(total_protection, 2),
        "last_payout": round(last_payout, 2),
        "recent_payouts": payout_history,
        "timestamp": datetime.utcnow().isoformat(),
        "lat": worker.get("lat"),
        "lon": worker.get("lon"),
    }

# ─────────────────────────────────────────────────────────────────────────────
# MODULE 2.5 – UPDATE WORKER LOCATION
# ─────────────────────────────────────────────────────────────────────────────
async def update_worker_location(worker_id: str, lat: float, lon: float) -> Dict[str, Any]:
    """
    Updates the gig worker's active GPS coordinates in the registry.
    """
    worker = get_worker_by_id(worker_id)
    if not worker:
        return {
            "success": False,
            "message": f"Worker '{worker_id}' not found. Cannot update location."
        }
        
    worker["lat"] = lat
    worker["lon"] = lon
    
    logger.info(f"[LOCATION] Updated worker {worker_id} location to {lat}, {lon}")
    
    return {
        "success": True,
        "worker_id": worker_id,
        "lat": lat,
        "lon": lon,
        "message": "Live location updated."
    }

"""
Gig Worker API Router
---------------------
Implements the 6-module insurance flow for gig workers:

  POST  /login                   → Module 1: Platform-based login
  GET   /verify-worker/{user_id} → Module 2: Worker verification
  GET   /zone-status/{user_id}   → Module 3: Location + risk validation
  GET   /eligibility/{user_id}   → Module 4: Auto eligibility engine
  POST  /auto-payout             → Module 5: Zero-claim payout trigger
  GET   /dashboard/{user_id}     → Module 6: Protection tracking dashboard
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional

from core.database import get_db
from services.gig_worker_service import (
    validate_login,
    verify_worker,
    get_zone_status_for_user,
    check_eligibility,
    trigger_auto_payout,
    get_dashboard,
    update_worker_location,
)
from services.simulation_service import set_worker_shift
from api.auth import get_current_user

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response Schemas
# ─────────────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    """Credentials submitted by the gig worker to log in via their platform."""
    worker_id: str = Field(..., example="ZOM-1001", description="Platform-issued worker ID")
    phone:     str = Field(..., example="9876543001", description="Registered mobile number")
    company:   str = Field(..., example="Zomato",    description="Platform: Zomato / Swiggy / Uber / Blinkit")


class AutoPayoutRequest(BaseModel):
    """Request body for the zero-claim payout trigger endpoint."""
    user_id: str = Field(..., example="SWG-2001", description="Worker ID to trigger payout for")
    wallet_address: Optional[str] = Field(None, example="0x123...", description="Ethereum wallet for Web3 payout")


class UpdateLocationRequest(BaseModel):
    user_id: str = Field(..., example="SWG-2001", description="Worker ID")
    lat: float = Field(..., example=13.0827, description="Latitude")
    lon: float = Field(..., example=80.2707, description="Longitude")

class ShiftRequest(BaseModel):
    user_id: str = Field(..., example="ZOM-1001", description="Worker ID")
    shift_id: str = Field(..., example="evening", description="Shift ID: morning, lunch, evening, night")


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 1 – POST /login
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    summary="Gig Worker Login",
    description=(
        "Authenticates a gig worker using their platform credentials "
        "(Worker ID + Phone + Company). Simulates OAuth login for "
        "Zomato, Swiggy, Uber, and Blinkit."
    ),
    tags=["Gig Worker Flow"],
)
async def login(request: LoginRequest):
    """
    **Module 1 — Gig Worker Authentication**

    Submit your platform Worker ID, registered phone number, and company name.
    Returns a session token and verification status on success.

    **Demo credentials:**
    - `ZOM-1001` / `9876543001` / `Zomato`
    - `SWG-2001` / `9876543101` / `Swiggy`
    - `UBR-3001` / `9876543201` / `Uber`
    - `BLK-4001` / `9876543301` / `Blinkit`
    """
    result = await validate_login(
        worker_id=request.worker_id.strip(),
        phone=request.phone.strip(),
        company=request.company.strip(),
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result.get("message", "Authentication failed."),
        )

    return result


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 2.5 – POST /update-location
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/update-location",
    summary="Update Worker Live Location",
    description="Updates the worker's GPS coordinates and validates against the covered city bounds.",
    tags=["Gig Worker Flow"],
)
async def update_location(request: UpdateLocationRequest, current_user: dict = Depends(get_current_user)):
    """
    **Module 2.5 — Location Tracking**
    
    Receives continuous lat/lon updates from the frontend Mapbox UI.
    Updates the worker's current zone inside the persistence layer.
    """
    result = await update_worker_location(
        worker_id=request.user_id.strip(), 
        lat=request.lat, 
        lon=request.lon
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("message", "Location update failed."),
        )

    return result

# ─────────────────────────────────────────────────────────────────────────────
# MODULE 2.6 – POST /shift
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/shift",
    summary="Set Active Worker Shift",
    description="Sets the current active shift for the worker to guarantee income.",
    tags=["Gig Worker Flow"],
)
async def activate_shift(request: ShiftRequest, current_user: dict = Depends(get_current_user)):
    """
    **Module 2.6 — Shift-Based Insurance**
    
    Allow worker to select a shift block to track and guarantee income.
    Available shifts: morning, lunch, evening, night.
    """
    result = set_worker_shift(worker_id=request.user_id.strip(), shift_id=request.shift_id.strip())
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("message", "Invalid shift selection."),
        )

    return result


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 2 – GET /verify-worker/{user_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/verify-worker/{user_id}",
    summary="Worker Verification Engine",
    description=(
        "Verifies that the worker is active, belongs to a supported platform, "
        "and is located in an SnapInsure-covered city."
    ),
    tags=["Gig Worker Flow"],
)
async def verify_worker_endpoint(user_id: str, current_user: dict = Depends(get_current_user)):
    """
    **Module 2 — Worker Verification**

    Runs four sequential checks:
    1. Worker exists in the SnapInsure registry
    2. Worker account is active on their platform
    3. Platform is supported (Zomato / Swiggy / Uber / Blinkit)
    4. Worker's city has active insurance coverage
    """
    result = await verify_worker(user_id.strip())

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("message", "Worker verification failed."),
        )

    return result


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 3 – GET /zone-status/{user_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/zone-status/{user_id}",
    summary="Location + Risk Validation",
    description=(
        "Fetches live weather (OpenWeather), disruption news (NLP), "
        "and calculates a real-time risk score and zone colour for the worker's city."
    ),
    tags=["Gig Worker Flow"],
)
async def zone_status(user_id: str, current_user: dict = Depends(get_current_user)):
    """
    **Module 3 — Location-based Risk Validation**

    Calls live external APIs concurrently:
    - **OpenWeather** — rainfall, wind, and weather severity
    - **NLP Engine** — news-headline disruption analysis (strikes, floods, protests)

    Returns:
    - `zone`: GREEN / YELLOW / RED
    - `risk_score`: 0.0 – 1.0
    - `reason`: list of contributing risk factors
    """
    result = await get_zone_status_for_user(user_id.strip())

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("message", "Zone status lookup failed."),
        )

    return result


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 4 – GET /eligibility/{user_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/eligibility/{user_id}",
    summary="Auto Eligibility Engine",
    description=(
        "Automatically determines if the worker is eligible for insurance activation "
        "based on their verification status and current zone risk level."
    ),
    tags=["Gig Worker Flow"],
)
async def eligibility(user_id: str, current_user: dict = Depends(get_current_user)):
    """
    **Module 4 — Eligibility Engine**

    Activation criteria (both must pass):
    - ✅ Worker is verified (active, supported platform, covered city)
    - ✅ Worker is in a YELLOW or RED risk zone

    If eligible, policy is auto-activated — no manual purchase required.
    """
    result = await check_eligibility(user_id.strip())

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.get("reason", "Eligibility check failed."),
        )

    return result


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 5 – POST /auto-payout
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/auto-payout",
    summary="Zero-Claim Automatic Payout",
    description=(
        "Triggers an automatic, zero-claim payout for a gig worker. "
        "No manual claim is required. The system reads the live zone "
        "and calculates compensation instantly."
    ),
    tags=["Gig Worker Flow"],
)
async def auto_payout(request: AutoPayoutRequest, db=Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    **Module 5 — Zero-Claim Payout Engine**

    Payout rules:
    - 🔴 **RED zone**: Full income compensation (minimum ₹150)
    - 🟡 **YELLOW zone**: Time-loss compensation (minimum ₹75)
    - 🟢 **GREEN zone**: No payout (system is stable)

    Payout is persisted to MongoDB and credited instantly.
    There is **no claim form** — completely automated.
    """
    result = await trigger_auto_payout(
        worker_id=request.user_id.strip(),
        wallet_address=request.wallet_address,
        db=db,
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("message", "Payout trigger failed."),
        )

    return result


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 6 – GET /dashboard/{user_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/dashboard/{user_id}",
    summary="Protection Tracking Dashboard",
    description=(
        "Returns a real-time dashboard of the worker's insurance status: "
        "zone, verification, company, total protection earned, and payout history."
    ),
    tags=["Gig Worker Flow"],
)
async def dashboard(user_id: str, db=Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    **Module 6 — Protection Dashboard**

    Aggregates all worker data into a single dashboard view:
    - Current risk zone (live)
    - Verification status
    - Platform / company
    - Total lifetime protection (₹)
    - Last payout amount (₹)
    - Last 10 payout records from MongoDB
    """
    result = await get_dashboard(user_id.strip(), db=db)

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("message", "Dashboard fetch failed."),
        )

    return result

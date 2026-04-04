import asyncio
import os
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from dotenv import load_dotenv

from core.config import settings
from core.database import connect_to_mongo, close_mongo_connection, get_db
from models.models import Zone, ZoneState
from api import users, policies, zones, payouts, triggers, routes, pricing, live_risk, weather, route_risk, nlp_risk, protection, gig_worker, auth
from api.websocket_router import router as ws_router
from api.income_os_router import router as income_os_router
from core.logger import logger

# Load environment variables (IMPORTANT for deployment)
load_dotenv()

# --- INITIALISE DECOUPLED ENGINES ---
import services.orchestrator_service
import services.pow_fraud_engine
import services.unified_payout_engine
# -----------------------------------

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Automated Zero-Claim Insurance Engine + AI-Powered Income OS for Disruption-Economy Workers.",
    version="1.2.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS (IMPORTANT for frontend connection)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For hackathon demo
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ HEALTH CHECK (VERY IMPORTANT FOR RENDER)
@app.get("/", tags=["System Information"])
async def root():
    return {
        "status": "UP",
        "system": settings.PROJECT_NAME,
        "version": "1.2.0",
        "timestamp": time.time(),
        "env_check": {
            "mongo_uri": "SET" if os.getenv("MONGO_URI") else "NOT SET"
        },
        "services": {
            "risk_engine": "ACTIVE",
            "payout_engine": "ACTIVE",
            "trigger_engine": "ACTIVE",
            "income_os": "ACTIVE"
        },
        "docs": "/docs"
    }

# GLOBAL ERROR HANDLER
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"GLOBAL_UNCAUGHT_ERROR: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal Server Error",
            "detail": str(exc)  # Show actual error (important for debugging)
        }
    )

# HTTP ERROR HANDLER
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": str(exc.detail),
            "error_code": exc.status_code
        }
    )

# 🚀 STARTUP EVENT
@app.on_event("startup")
async def startup_event():
    try:
        # Connect DB
        await connect_to_mongo()
        logger.info("[STARTUP] MongoDB connected successfully")

        db = get_db()

        # Seed zones if empty
        zone_count = await db["zones"].count_documents({})
        if zone_count == 0:
            demo_zones = [
                Zone(name=f"Z{i}", risk_score=0.0, state=ZoneState.GREEN).dict(by_alias=True)
                for i in range(1, 10)
            ]
            for i, z in enumerate(demo_zones):
                z["_id"] = f"Z{i+1}"

            await db["zones"].insert_many(demo_zones)
            logger.info("[STARTUP] Demo zones seeded")

        # Seed verified workers
        from services.auth_service import seed_verified_workers
        await seed_verified_workers(db)
        logger.info("[STARTUP] Workers seeded")

        # Start simulation loop
        from services.simulation_service import simulation_loop
        asyncio.create_task(simulation_loop())
        logger.info("[STARTUP] Simulation loop started")

    except Exception as e:
        logger.error(f"[ERROR] STARTUP FAILED: {str(e)}")

# 🔴 SHUTDOWN EVENT
@app.on_event("shutdown")
async def shutdown_event():
    await close_mongo_connection()
    logger.info("[SHUTDOWN] Backend shutdown complete")

# ROUTERS
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(policies.router, prefix="/policies", tags=["Policies"])
app.include_router(zones.router, prefix="/zones", tags=["Zones"])
app.include_router(payouts.router, prefix="/payouts", tags=["Payouts"])
app.include_router(triggers.router, prefix="/trigger", tags=["Triggers"])
app.include_router(routes.router, tags=["Routes"])
app.include_router(pricing.router, prefix="/premium", tags=["Pricing"])
app.include_router(live_risk.router, tags=["Risk Engine"])
app.include_router(weather.router, tags=["Weather"])
app.include_router(route_risk.router, tags=["Route Risk"])
app.include_router(nlp_risk.router, tags=["NLP Risk"])
app.include_router(protection.router, prefix="/protection", tags=["Protection"])
app.include_router(gig_worker.router, prefix="/gig", tags=["Gig Worker"])
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(ws_router, tags=["WebSocket"])

# AI + Income OS
from api.ai_advisor_router import router as ai_router
app.include_router(ai_router, tags=["AI Advisor"])
app.include_router(income_os_router, tags=["Income OS"])
import jwt
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from core.config import settings
from fastapi import HTTPException
from core.logger import logger

SECRET_KEY = getattr(settings, "SECRET_KEY", "SUPER_SECRET_SNAPINSURE_KEY_2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

MOCK_WORKERS = [
    {
        "name": "Ravi",
        "phone": "9876543210",
        "platform": "Swiggy",
        "city": "Chennai",
        "worker_id": "SWG123",
        "avg_hourly_income": 120,
        "risk_score": 0.2,
        "is_active": True
    },
    {
        "name": "Arjun",
        "phone": "9876543211",
        "platform": "Zomato",
        "city": "Bangalore",
        "worker_id": "ZOM123",
        "avg_hourly_income": 140,
        "risk_score": 0.1,
        "is_active": True
    }
]

# Simple in-memory rate limiting dictionary {phone: (attempts, last_attempt_time)}
rate_limit_db = {}

async def seed_verified_workers(db):
    """Seed the database with pre-verified mock workers."""
    col = db["users"]
    count = await col.count_documents({})
    if count == 0:
        await col.insert_many(MOCK_WORKERS)
        logger.info(f"Seeded {len(MOCK_WORKERS)} mock verified users into MongoDB.")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def check_rate_limit(phone: str):
    now = time.time()
    record = rate_limit_db.get(phone)
    if record:
        attempts, last_time = record
        if now - last_time < 900: # 15 minutes window
            if attempts >= 5:
                raise HTTPException(status_code=429, detail="Too many rapid login attempts. Blocked for 15 minutes.")
            rate_limit_db[phone] = (attempts + 1, now)
        else:
            rate_limit_db[phone] = (1, now)
    else:
        rate_limit_db[phone] = (1, now)

async def check_multiple_logins(phone: str, city: str, db):
    """Check if the user is already logged in from a different city (simulated behavior)."""
    active_session_col = db["active_sessions"]
    active_sessions = await active_session_col.find({"phone": phone}).to_list(length=10)
    for session in active_sessions:
        if session.get("city") and session.get("city").lower() != city.lower():
            # Flag as multiple login / location jump
            fraud_col = db["fraud_logs"]
            await fraud_col.insert_one({
                "phone": phone,
                "reason": f"Multiple login location jump. Previous: {session.get('city')}, New: {city}",
                "timestamp": datetime.utcnow()
            })
            raise HTTPException(status_code=403, detail="Unusual activity detected: Logging in from multiple distinct locations.")

async def login_worker(phone: str, platform: str, city: str, worker_id: Optional[str], db, ip_address: str):
    check_rate_limit(phone)
    
    col = db["users"]
    # Exact query as requested: phone, platform, city (ignoring case for platform and city if needed, but exact matches first)
    query = {
        "phone": phone,
        "platform": {"$regex": f"^{platform}$", "$options": "i"},
        "city": {"$regex": f"^{city}$", "$options": "i"}
    }
    worker = await col.find_one(query)
    
    logger.info(f"User lookup result for {phone}: {'Found' if worker else 'Not Found'}")
    
    if not worker:
        logger.warning(f"Login failed: User not found in database for phone={phone}, platform={platform}, city={city}")
        raise HTTPException(status_code=401, detail="User not verified by platform. Access denied.")
        
    logger.info(f"Login successful for user: {worker.get('name')} ({phone})")
        
    # 2 & 5. MULTIPLE LOGIN / BEHAVIOR CHECK
    await check_multiple_logins(phone, city, db)

    # Success: Generate JWT
    token = create_access_token({
        "phone": phone,
        "platform": platform,
        "worker_id": worker.get("worker_id"),
        "name": worker.get("name")
    })
    
    # Store session
    session_data = {
        "phone": phone,
        "token": token,
        "login_time": datetime.utcnow(),
        "ip_address": ip_address,
        "city": city
    }
    await db["active_sessions"].insert_one(session_data)
    
    return {
        "success": True,
        "token": token,
        "user": {
            "name": worker.get("name"),
            "phone": phone,
            "platform": platform,
            "city": city,
            "worker_id": worker.get("worker_id"),
            "risk_score": worker.get("risk_score", 0.1),
            "verified": True
        }
    }

async def verify_jwt(token: str, db):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        phone = payload.get("phone")
        if phone is None:
            raise HTTPException(status_code=401, detail="Invalid session token.")
            
        session = await db["active_sessions"].find_one({"token": token})
        if not session:
            raise HTTPException(status_code=401, detail="Session expired or logged out.")
            
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid session token.")

async def logout_worker(token: str, db):
    result = await db["active_sessions"].delete_one({"token": token})
    return result.deleted_count > 0

async def get_fraud_logs(db):
    logs = await db["fraud_logs"].find({}).sort("timestamp", -1).to_list(length=100)
    # clean up objectId for JSON
    for l in logs:
        l["_id"] = str(l["_id"])
        l["timestamp"] = l["timestamp"].isoformat()
    return logs

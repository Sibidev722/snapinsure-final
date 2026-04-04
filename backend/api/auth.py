from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
from core.database import get_db
from services import auth_service

router = APIRouter()
security = HTTPBearer()

class LoginRequest(BaseModel):
    phone: str
    platform: str
    city: str
    worker_id: Optional[str] = None

class LogoutRequest(BaseModel):
    token: str

@router.post("/login", summary="Secure Login")
async def login(request: Request, data: LoginRequest, db=Depends(get_db)):
    ip_address = request.client.host if request.client else "unknown"
    result = await auth_service.login_worker(
        phone=data.phone.strip(),
        platform=data.platform.strip(),
        city=data.city.strip(),
        worker_id=data.worker_id.strip() if data.worker_id else None,
        db=db,
        ip_address=ip_address
    )
    return result

@router.get("/verify", summary="Verify Session")
async def verify(credentials: HTTPAuthorizationCredentials = Security(security), db=Depends(get_db)):
    token = credentials.credentials
    payload = await auth_service.verify_jwt(token, db)
    return {"success": True, "user": payload}

@router.post("/logout", summary="Logout Session")
async def logout(credentials: HTTPAuthorizationCredentials = Security(security), db=Depends(get_db)):
    token = credentials.credentials
    success = await auth_service.logout_worker(token, db)
    return {"success": success}

@router.get("/fraud-check", summary="Internal Fraud Check")
async def fraud_check(db=Depends(get_db)):
    logs = await auth_service.get_fraud_logs(db)
    return {"success": True, "fraud_logs": logs}

async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security), db=Depends(get_db)):
    token = credentials.credentials
    payload = await auth_service.verify_jwt(token, db)
    return payload

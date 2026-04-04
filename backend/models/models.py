import enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class ZoneState(str, enum.Enum):
    GREEN = "GREEN"    # Normal
    YELLOW = "YELLOW"  # Partial disruption
    RED = "RED"        # Fully blocked

class PayoutReason(str, enum.Enum):
    NO_WORK = "NO_WORK"
    DELAY = "DELAY"

# -----------
# User Models
# -----------
class UserBase(BaseModel):
    name: str
    city: str
    type: str  # rider, driver, delivery
    peak_hours: int
    avg_income: float

class UserCreate(UserBase):
    pass

class User(UserBase):
    id: str = Field(default_factory=generate_uuid, alias="_id")

# -----------
# Zone Models
# -----------
class ZoneBase(BaseModel):
    name: str
    risk_score: float = 0.0
    state: ZoneState = ZoneState.GREEN
    metadata: Dict[str, Any] = {}

class ZoneCreate(ZoneBase):
    pass

class Zone(ZoneBase):
    id: str = Field(default_factory=generate_uuid, alias="_id")

# -------------
# Policy Models
# -------------
class PolicyBase(BaseModel):
    user_id: str
    route_zones: List[str]  # List of zone IDs
    premium_paid: float
    coverage_amount: float
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: datetime
    avg_peak_income: float = 0.0
    avg_normal_income: float = 0.0
    working_hours: int = 0

class PolicyCreate(PolicyBase):
    pass

class Policy(PolicyBase):
    id: str = Field(default_factory=generate_uuid, alias="_id")
    is_active: bool = True

# -------------
# Payout Models
# -------------
class PayoutBase(BaseModel):
    user_id: str
    policy_id: str
    amount: float
    reason: PayoutReason
    zone_id: str

class PayoutCreate(PayoutBase):
    pass

class Payout(PayoutBase):
    id: str = Field(default_factory=generate_uuid, alias="_id")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# -------------
# Pricing Models
# -------------
class PricingRequest(BaseModel):
    user_id: str
    route_zones: List[str]
    duration_minutes: int

class PricingResponse(BaseModel):
    premium: float
    coverage: float
    risk_factor: float
    explanation: str

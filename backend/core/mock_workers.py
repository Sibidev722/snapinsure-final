"""
Mock Worker Database
--------------------
Simulates the verified worker registry for Zomato, Swiggy, Uber, and Blinkit.
In a production system, this would be replaced by each platform's OAuth2 / Partner API.

Each worker has:
- worker_id   : Platform-issued unique ID
- phone       : Registered mobile number
- company     : Platform name (Zomato / Swiggy / Uber / Blinkit)
- name        : Full name
- city        : Home city
- is_active   : Whether the account is currently active
- avg_income  : Average daily income in ₹
- peak_hours  : Peak working hours per day
- total_protection : Cumulative insurance protection received (₹)
- vehicle_type     : "petrol" | "ev" | "bicycle"
- total_carbon_saved: kg of CO2 saved vs petrol baseline
- esg_discount    : current premium discount (0.00 to 0.10)
"""

MOCK_WORKERS = [
    # ─── ZOMATO ────────────────────────────────────────────────────────────────
    {
        "worker_id": "ZOM-1001",
        "phone": "9876543001",
        "company": "Zomato",
        "name": "Rajesh Kumar",
        "city": "Chennai",
        "is_active": True,
        "avg_income": 750.0,
        "peak_hours": 6,
        "total_protection": 3200.0,
        "last_payout": 150.0,
        "vehicle_type": "petrol",
        "total_carbon_saved": 0.0,
        "esg_discount": 0.0,
    },
    {
        "worker_id": "ZOM-1002",
        "phone": "9876543002",
        "company": "Zomato",
        "name": "Priya Sharma",
        "city": "Mumbai",
        "is_active": True,
        "avg_income": 900.0,
        "peak_hours": 7,
        "total_protection": 4100.0,
        "last_payout": 280.0,
        "vehicle_type": "ev",
        "total_carbon_saved": 8.5,
        "esg_discount": 0.10,
    },
    {
        "worker_id": "ZOM-1003",
        "phone": "9876543003",
        "company": "Zomato",
        "name": "Arun Mehta",
        "city": "Delhi",
        "is_active": False,   # Inactive worker — should fail verification
        "avg_income": 600.0,
        "peak_hours": 5,
        "total_protection": 0.0,
        "last_payout": 0.0,
        "vehicle_type": "petrol",
        "total_carbon_saved": 0.0,
        "esg_discount": 0.0,
    },
    # ─── SWIGGY ────────────────────────────────────────────────────────────────
    {
        "worker_id": "SWG-2001",
        "phone": "9876543101",
        "company": "Swiggy",
        "name": "Karthik Rajan",
        "city": "Bangalore",
        "is_active": True,
        "avg_income": 820.0,
        "peak_hours": 6,
        "total_protection": 2800.0,
        "last_payout": 200.0,
        "vehicle_type": "bicycle",
        "total_carbon_saved": 12.4,
        "esg_discount": 0.10,
    },
    {
        "worker_id": "SWG-2002",
        "phone": "9876543102",
        "company": "Swiggy",
        "name": "Meena Iyer",
        "city": "Chennai",
        "is_active": True,
        "avg_income": 780.0,
        "peak_hours": 5,
        "total_protection": 1900.0,
        "last_payout": 100.0,
        "vehicle_type": "ev",
        "total_carbon_saved": 4.2,
        "esg_discount": 0.0,
    },
    {
        "worker_id": "SWG-2003",
        "phone": "9876543103",
        "company": "Swiggy",
        "name": "Vijay Bose",
        "city": "Hyderabad",
        "is_active": True,
        "avg_income": 870.0,
        "peak_hours": 7,
        "total_protection": 5300.0,
        "last_payout": 350.0,
        "vehicle_type": "petrol",
        "total_carbon_saved": 0.0,
        "esg_discount": 0.0,
    },
    # ─── UBER ──────────────────────────────────────────────────────────────────
    {
        "worker_id": "UBR-3001",
        "phone": "9876543201",
        "company": "Uber",
        "name": "Suresh Pillai",
        "city": "Kochi",
        "is_active": True,
        "avg_income": 1100.0,
        "peak_hours": 8,
        "total_protection": 6800.0,
        "last_payout": 450.0,
        "vehicle_type": "petrol",
        "total_carbon_saved": 0.0,
        "esg_discount": 0.0,
    },
    {
        "worker_id": "UBR-3002",
        "phone": "9876543202",
        "company": "Uber",
        "name": "Ananya Dey",
        "city": "Kolkata",
        "is_active": True,
        "avg_income": 950.0,
        "peak_hours": 8,
        "total_protection": 5200.0,
        "last_payout": 320.0,
        "vehicle_type": "ev",
        "total_carbon_saved": 15.6,
        "esg_discount": 0.10,
    },
    {
        "worker_id": "UBR-3003",
        "phone": "9876543203",
        "company": "Uber",
        "name": "Naresh Nair",
        "city": "Pune",
        "is_active": True,
        "avg_income": 1050.0,
        "peak_hours": 9,
        "total_protection": 7100.0,
        "last_payout": 500.0,
        "vehicle_type": "petrol",
        "total_carbon_saved": 0.0,
        "esg_discount": 0.0,
    },
    # ─── BLINKIT ───────────────────────────────────────────────────────────────
    {
        "worker_id": "BLK-4001",
        "phone": "9876543301",
        "company": "Blinkit",
        "name": "Divya Krishnan",
        "city": "Chennai",
        "is_active": True,
        "avg_income": 680.0,
        "peak_hours": 5,
        "total_protection": 1500.0,
        "last_payout": 80.0,
        "vehicle_type": "ev",
        "total_carbon_saved": 6.8,
        "esg_discount": 0.10,
    },
    {
        "worker_id": "BLK-4002",
        "phone": "9876543302",
        "company": "Blinkit",
        "name": "Ravi Varma",
        "city": "Delhi",
        "is_active": True,
        "avg_income": 720.0,
        "peak_hours": 6,
        "total_protection": 2300.0,
        "last_payout": 130.0,
        "vehicle_type": "ev",
        "total_carbon_saved": 2.1,
        "esg_discount": 0.0,
    },
    {
        "worker_id": "BLK-4003",
        "phone": "9876543303",
        "company": "Blinkit",
        "name": "Sneha Kulkarni",
        "city": "Pune",
        "is_active": True,
        "avg_income": 700.0,
        "peak_hours": 5,
        "total_protection": 1800.0,
        "last_payout": 95.0,
        "vehicle_type": "petrol",
        "total_carbon_saved": 0.0,
        "esg_discount": 0.0,
    },
]

# Supported platforms
SUPPORTED_COMPANIES = {"Zomato", "Swiggy", "Uber", "Blinkit"}

# Cities with active insurance coverage
SUPPORTED_CITIES = {
    "Chennai", "Mumbai", "Delhi", "Bangalore",
    "Hyderabad", "Kochi", "Kolkata", "Pune",
}

def get_worker_by_credentials(worker_id: str, phone: str, company: str):
    """
    Simulated OAuth verification:
    Matches worker_id + phone + company against the mock registry.
    Returns the worker dict if found, else None.
    """
    for worker in MOCK_WORKERS:
        if (
            worker["worker_id"] == worker_id
            and worker["phone"] == phone
            and worker["company"].lower() == company.lower()
        ):
            return worker
    return None


def get_worker_by_id(worker_id: str):
    """Fetch a worker by worker_id alone (for post-login lookups)."""
    for worker in MOCK_WORKERS:
        if worker["worker_id"] == worker_id:
            return worker
    return None

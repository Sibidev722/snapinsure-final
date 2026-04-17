import os
import random
import uuid
from datetime import datetime, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv

# Load env variables (Ensure MONGO_URI is set)
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DATABASE_NAME", "snapinsure")

# Seed Data Configurations
START_DATE = datetime.utcnow() - timedelta(days=14)
END_DATE = datetime.utcnow()

# Mock Data Arrays for Realistic Generation
FIRST_NAMES = ["Ravi", "Suresh", "Ramesh", "Priya", "Anita", "Sunil", "Karthik", "Arun", "Deepa", "Divya", "Sanjay", "Vikram", "Ajay", "Rajesh", "Naveen", "Gokul", "Vignesh", "Manoj", "Sibi", "Aditya"]
LAST_NAMES = ["Kumar", "Sharma", "Singh", "Reddy", "Patel", "Nair", "Menon", "Iyer", "Rao", "Das", "Gupta", "Jain", "Bose", "Varma", "Pillai", "Krishnan", "Rajan"]
VEHICLE_TYPES = ["bike", "ev", "bicycle"]
CITIES = ["Chennai"]

# Chennai Geographic Zones mapped to realistic areas
CHENNAI_ZONES = [
    {"zone_id": "Z1", "name": "Adyar", "lat": 13.0033, "lon": 80.2550},
    {"zone_id": "Z2", "name": "T-Nagar", "lat": 13.0382, "lon": 80.2365},
    {"zone_id": "Z3", "name": "Velachery", "lat": 12.9754, "lon": 80.2206},
    {"zone_id": "Z4", "name": "Anna Nagar", "lat": 13.0850, "lon": 80.2101},
    {"zone_id": "Z5", "name": "Tambaram", "lat": 12.9230, "lon": 80.1260},
    {"zone_id": "Z6", "name": "OMR (IT Corridor)", "lat": 12.95, "lon": 80.24},
    {"zone_id": "Z7", "name": "Guindy", "lat": 13.0067, "lon": 80.2206},
    {"zone_id": "Z8", "name": "Porur", "lat": 13.0385, "lon": 80.1517},
]

DISRUPTION_TYPES = ["rain", "traffic", "accident", "protest"]
SEVERITY = ["low", "medium", "high"]

def generate_db_data():
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return

    # Clean SLATE: drop existing collections to allow safe re-runs
    print("Clearing old collections for safe re-run...")
    collections = ["workers", "earnings", "claims", "audit_logs", "zones", "disruptions", "esg_activity", "transactions"]
    for coll in collections:
        db[coll].drop()

    # 1. ZONES
    print("Generating Zones...")
    zones_data = []
    for z in CHENNAI_ZONES:
        demand = random.choice(["low", "medium", "high"])
        risk = "high" if demand == "high" else "low"
        surge = round(random.uniform(1.0, 2.5), 1)
        z_doc = {
            "_id": z["zone_id"],
            "zone_id": z["zone_id"],
            "city": "Chennai",
            "name": z["name"],
            "coordinates": {"lat": z["lat"], "lon": z["lon"]},
            "demand_level": demand,
            "risk_level": risk,
            "surge_multiplier": surge,
            "created_at": datetime.utcnow()
        }
        zones_data.append(z_doc)
    
    if zones_data:
        db.zones.insert_many(zones_data)

    # 2. WORKERS
    print("Generating 800 Workers...")
    workers_data = []
    
    # Pre-define 5 high-risk and 5 high-reward scenario workers to ensure they exist for demo purposes
    special_workers = [f"W_FRAUD_{i}" for i in range(1, 6)] + [f"W_REWARD_{i}" for i in range(1, 6)]
    
    for _ in range(800):
        w_id = special_workers.pop() if special_workers else f"W{random.randint(10000, 99999)}"
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        vehicle = random.choice(VEHICLE_TYPES)
        w_doc = {
            "_id": w_id,
            "worker_id": w_id,
            "name": name,
            "vehicle_type": vehicle,
            "rating": round(random.uniform(3.5, 5.0), 1),
            "city": "Chennai",
            "created_at": START_DATE - timedelta(days=random.randint(10, 100))
        }
        workers_data.append(w_doc)
    
    # Deduplicate worker ids
    workers_data = list({w["worker_id"]: w for w in workers_data}.values())
    db.workers.insert_many(workers_data)

    # 3. HISTORICAL DATA (EARNINGS, DISRUPTIONS, CLAIMS, ESG, TRANSACTIONS)
    print("Generating 14 days of interconnected History...")
    earnings_data = []
    disruptions_data = []
    esg_data = []
    claims_data = []
    audit_data = []
    tx_data = []

    current_date = START_DATE
    while current_date <= END_DATE:
        # A. Daily Disruptions
        num_disruptions = random.randint(3, 8)
        daily_disruption_zones = []
        for _ in range(num_disruptions):
            d_zone = random.choice(CHENNAI_ZONES)["zone_id"]
            d_type = random.choice(DISRUPTION_TYPES)
            d_sev = random.choice(SEVERITY)
            d_doc = {
                "_id": str(uuid.uuid4()),
                "zone_id": d_zone,
                "type": d_type,
                "severity": d_sev,
                "timestamp": current_date + timedelta(hours=random.randint(8, 20))
            }
            disruptions_data.append(d_doc)
            daily_disruption_zones.append((d_zone, d_type, d_sev))

        # B. Daily Worker Earnings and Connected Actions
        daily_workers = random.sample(workers_data, 250)  # ~30% of workers active per day
        for w in daily_workers:
            w_zone = random.choice(CHENNAI_ZONES)["zone_id"]
            
            # Causal Logic: Did they face a disruption?
            disruption_modifier = 1.0
            faced_disruption = False
            faced_rain = False
            for dz, dtype, dsev in daily_disruption_zones:
                if dz == w_zone:
                    faced_disruption = True
                    if dtype == "rain":
                        faced_rain = True
                        disruption_modifier = 1.6 if dsev == "high" else 1.2
                    elif dtype == "traffic" or dtype == "protest":
                        disruption_modifier = 0.7  # Traffic/protests hurt orders
            
            # Special Worker Overrides
            if w["worker_id"].startswith("W_REWARD_"):
                # High Reward workers hustle in the rain
                if faced_rain:
                    disruption_modifier = 2.0 
                # Evs and bicycles benefit from high ESG distance
                w["vehicle_type"] = random.choice(["ev", "bicycle"]) 

            # Earnings Generation
            orders = int(random.randint(8, 25) * disruption_modifier)
            base_earn = orders * 45
            surge = round(random.uniform(1.0, 1.8), 1) if faced_rain else 1.0
            earnings = int(base_earn * surge)
            hours = round(random.uniform(4.0, 9.0), 1)
            
            e_id = str(uuid.uuid4())
            e_doc = {
                "_id": e_id,
                "worker_id": w["worker_id"],
                "timestamp": current_date + timedelta(hours=random.randint(9, 23)),
                "zone_id": w_zone,
                "orders_completed": orders,
                "earnings": earnings,
                "hours_worked": hours,
                "surge_multiplier": surge
            }
            earnings_data.append(e_doc)

            # ESG Generation 
            dist = orders * random.uniform(2.5, 5.0)
            carbon_saved = 0.0
            if w["vehicle_type"] == "ev":
                carbon_saved = dist * 0.12 # kg saved per km vs ICE
            elif w["vehicle_type"] == "bicycle":
                carbon_saved = dist * 0.25
            
            if carbon_saved > 0:
                esg_doc = {
                    "_id": str(uuid.uuid4()),
                    "worker_id": w["worker_id"],
                    "distance_km": round(dist, 1),
                    "vehicle_type": w["vehicle_type"],
                    "carbon_saved": round(carbon_saved, 2),
                    "timestamp": e_doc["timestamp"]
                }
                esg_data.append(esg_doc)

            # Causal Logic: Claim Generation
            # Worker files a claim if earnings are very low OR they are a fraudulent worker
            makes_claim = False
            is_fraudulent = w["worker_id"].startswith("W_FRAUD_")
            req_amt = 0

            if is_fraudulent:
                makes_claim = True
                req_amt = random.randint(1500, 5000) # Unusually high amounts
            elif earnings < 400 and faced_disruption:
                makes_claim = random.random() < 0.3 # 30% chance if genuinely disrupted and earned low
                req_amt = random.randint(200, 800)
            elif random.random() < 0.02: # 2% random probability for normal flow
                makes_claim = random.random() < 0.02
                req_amt = random.randint(100, 500)

            if makes_claim:
                c_id = f"CLM-{uuid.uuid4().hex[:8].upper()}"
                
                # Multi-Agent Evaluation Logic
                status = "approved"
                tel_status, eco_status = "PASS", "PASS"
                conf = round(random.uniform(0.85, 0.98), 2)
                
                # Fraud Detection Gates
                if is_fraudulent or req_amt > (earnings * 3 + 1000): # Economist Reject
                    status = "rejected"
                    eco_status = "FAIL"
                    conf = round(random.uniform(0.1, 0.4), 2)
                    eco_reason = f"Anomaly: Payout {req_amt} exceeds 200% of average earnings."
                else:
                    eco_reason = f"Payout {req_amt} matches historical baseline."

                if is_fraudulent and random.random() < 0.5: # Telemetrist Reject
                    status = "rejected"
                    tel_status = "FAIL"
                    conf = round(random.uniform(0.1, 0.3), 2)
                    tel_reason = "GPS Mismatch: Worker location > 5km from disruption epicenter."
                else:
                    tel_reason = "Valid Location: Worker within 1.2km radius."

                claim_doc = {
                    "_id": c_id,
                    "claim_id": c_id,
                    "worker_id": w["worker_id"],
                    "requested_amount": req_amt,
                    "status": status,
                    "timestamp": e_doc["timestamp"] + timedelta(minutes=random.randint(10, 60))
                }
                claims_data.append(claim_doc)

                audit_log = {
                    "_id": str(uuid.uuid4()),
                    "worker_id": w["worker_id"],
                    "claim_id": c_id,
                    "decision": status.upper(),
                    "agents": [
                        {
                            "agent": "TelemetristAgent",
                            "status": tel_status,
                            "reason": tel_reason,
                            "confidence": 0.95 if tel_status == "PASS" else 0.12
                        },
                        {
                            "agent": "EconomistAgent",
                            "status": eco_status,
                            "reason": eco_reason,
                            "confidence": 0.9 if eco_status == "PASS" else 0.15
                        }
                    ],
                    "final_confidence": conf,
                    "timestamp": claim_doc["timestamp"]
                }
                audit_data.append(audit_log)

                # Transactions only flow if Approved
                if status == "approved":
                    tx_doc = {
                        "_id": str(uuid.uuid4()),
                        "transaction_id": f"TXN-{uuid.uuid4().hex[:8].upper()}",
                        "worker_id": w["worker_id"],
                        "claim_id": c_id,
                        "amount": req_amt,
                        "status": "completed",
                        "type": "payout",
                        "timestamp": claim_doc["timestamp"] + timedelta(minutes=random.randint(1, 5))
                    }
                    tx_data.append(tx_doc)

        current_date += timedelta(days=1)

    # Bulk Insert
    print(f"Executing bulk inserts...")
    if earnings_data:
        db.earnings.insert_many(earnings_data)
        print(f"[SUCCESS] {len(earnings_data)} Earnings events populated")
    if disruptions_data:
        db.disruptions.insert_many(disruptions_data)
        print(f"[SUCCESS] {len(disruptions_data)} Disruption events populated")
    if esg_data:
        db.esg_activity.insert_many(esg_data)
        print(f"[SUCCESS] {len(esg_data)} ESG activities populated")
    if claims_data:
        db.claims.insert_many(claims_data)
        db.audit_logs.insert_many(audit_data)
        print(f"[SUCCESS] {len(claims_data)} Claims along with XAI Audit Logs populated")
    if tx_data:
        db.transactions.insert_many(tx_data)
        print(f"[SUCCESS] {len(tx_data)} Realized Wallet Transactions populated")

    print(f"\n[DONE] DATABASE PRODUCTION SEEDING COMPLETE FOR '{DB_NAME}'")

if __name__ == "__main__":
    generate_db_data()

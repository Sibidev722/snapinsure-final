import os
import uuid
import pymongo
from pymongo import MongoClient, IndexModel, ASCENDING, DESCENDING
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load env variables (Ensure MONGO_URI is set)
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DATABASE_NAME", "snapinsure")

def run_migration():
    print("[START] Starting Database Migration and Hardening")
    
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return

    # ---------------------------------------------------------
    # 1. ORPHAN CLEANUP & REFERENTIAL INTEGRITY
    # ---------------------------------------------------------
    print("\n--- Running Referential Integrity Cleanup ---")
    
    # Get all valid IDs
    valid_workers = set(doc["worker_id"] for doc in db.workers.find({}, {"worker_id": 1}))
    valid_zones = set(doc["zone_id"] for doc in db.zones.find({}, {"zone_id": 1}))

    print(f"Total valid workers: {len(valid_workers)}")
    print(f"Total valid zones: {len(valid_zones)}")

    if not valid_workers or not valid_zones:
        print("No valid workers or zones found. Are you sure you ran seed_db.py?")
    else:
        # Delete orphans
        res1 = db.earnings.delete_many({"worker_id": {"$nin": list(valid_workers)}})
        res2 = db.claims.delete_many({"worker_id": {"$nin": list(valid_workers)}})
        res3 = db.audit_logs.delete_many({"worker_id": {"$nin": list(valid_workers)}})
        res4 = db.esg_activity.delete_many({"worker_id": {"$nin": list(valid_workers)}})
        res5 = db.transactions.delete_many({"worker_id": {"$nin": list(valid_workers)}})
        res6 = db.earnings.delete_many({"zone_id": {"$nin": list(valid_zones)}})
        res7 = db.disruptions.delete_many({"zone_id": {"$nin": list(valid_zones)}})

        print(f"Orphan Cleanup Results:")
        print(f"  - earnings removed: {res1.deleted_count + res6.deleted_count}")
        print(f"  - claims removed: {res2.deleted_count}")
        print(f"  - audit_logs removed: {res3.deleted_count}")
        print(f"  - esg_activity removed: {res4.deleted_count}")
        print(f"  - transactions removed: {res5.deleted_count}")
        print(f"  - disruptions removed: {res7.deleted_count}")

    # ---------------------------------------------------------
    # 2. MISSING DATA BACKFILL (TRANSACTIONS)
    # ---------------------------------------------------------
    print("\n--- Running Data Backfill ---")
    approved_claims = list(db.claims.find({"status": "approved"}))
    backfill_count = 0
    
    for claim in approved_claims:
        tx_exists = db.transactions.find_one({"claim_id": claim["claim_id"]})
        if not tx_exists:
            db.transactions.insert_one({
                "_id": str(uuid.uuid4()),
                "transaction_id": f"TXN-BACKFILL-{uuid.uuid4().hex[:6].upper()}",
                "worker_id": claim["worker_id"],
                "claim_id": claim["claim_id"],
                "amount": claim.get("requested_amount", 500),
                "status": "completed",
                "type": "payout",
                "timestamp": claim.get("timestamp", datetime.utcnow()) + timedelta(minutes=5)
            })
            backfill_count += 1
            
    print(f"Backfilled {backfill_count} missing transactions for approved claims.")

    # ---------------------------------------------------------
    # 3. APPLY $JSONSCHEMA VALIDATION
    # ---------------------------------------------------------
    print("\n--- Applying Strict JSON Schema Validations ---")
    
    schemas = {
        "earnings": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["worker_id", "zone_id", "timestamp", "orders_completed"],
                "properties": {
                    "worker_id": {"bsonType": "string"},
                    "zone_id": {"bsonType": "string"},
                    "timestamp": {"bsonType": "date"},
                    "orders_completed": {"bsonType": ["int", "double"]},
                    "earnings": {"bsonType": ["int", "double"]},
                }
            }
        },
        "claims": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["claim_id", "worker_id", "requested_amount", "status"],
                "properties": {
                    "claim_id": {"bsonType": "string"},
                    "worker_id": {"bsonType": "string"},
                    "requested_amount": {"bsonType": ["int", "double"]},
                    "status": {"bsonType": "string", "enum": ["pending", "approved", "rejected", "APPROVED", "REJECTED"]}
                }
            }
        },
        "audit_logs": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["claim_id", "worker_id", "decision", "agents"],
                "properties": {
                    "claim_id": {"bsonType": "string"},
                    "worker_id": {"bsonType": "string"},
                    "decision": {"bsonType": "string"},
                    "agents": {
                        "bsonType": "array",
                        "items": {
                            "bsonType": "object",
                            "required": ["agent", "status", "confidence"],
                            "properties": {
                                "agent": {"bsonType": "string"},
                                "status": {"bsonType": "string", "enum": ["PASS", "FAIL"]},
                                "reason": {"bsonType": "string"},
                                "confidence": {"bsonType": ["double", "int"]}
                            }
                        }
                    }
                }
            }
        }
    }

    for collection_name, schema in schemas.items():
        try:
            # If collection doesn't exist, create it (shouldn't happen here, but safe)
            if collection_name not in db.list_collection_names():
                db.create_collection(collection_name)
            
            db.command("collMod", collection_name, validator=schema, validationLevel="strict")
            print(f"Validation applied to '{collection_name}' collection")
        except Exception as e:
            print(f"Failed to apply validation to '{collection_name}': {e}")


    # ---------------------------------------------------------
    # 4. CREATE INDEXES
    # ---------------------------------------------------------
    print("\n--- Creating Indexes ---")
    
    # Workers
    db.workers.create_index([("worker_id", ASCENDING)], unique=True)
    
    # Zones
    db.zones.create_index([("zone_id", ASCENDING)], unique=True)

    # Earnings (Compound for UI maps)
    db.earnings.create_index([("zone_id", ASCENDING), ("timestamp", DESCENDING)])
    db.earnings.create_index([("worker_id", ASCENDING), ("timestamp", DESCENDING)])

    # Claims
    db.claims.create_index([("worker_id", ASCENDING), ("status", ASCENDING)])
    db.claims.create_index([("claim_id", ASCENDING)], unique=True)

    # Transactions
    db.transactions.create_index([("worker_id", ASCENDING), ("timestamp", DESCENDING)])

    # Disruptions
    db.disruptions.create_index([("zone_id", ASCENDING), ("type", ASCENDING)])

    print("Index creation completed.")
    
    # Print sample to verify
    print("\n[VERIFICATION]")
    print("Testing schema validation on 'claims'...")
    try:
        db.claims.insert_one({"worker_id": "WILL_FAIL", "status": "approved"})
        print("[FAILED] Validation did not stop invalid document.")
    except pymongo.errors.WriteError as e:
        print("[SUCCESS] Schema validation blocked an invalid document (missing claim_id).")

    print("\n[DONE] Migration Complete!")

if __name__ == "__main__":
    run_migration()

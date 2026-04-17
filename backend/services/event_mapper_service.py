"""
NLP Event Mapper Service
------------------------
Maps raw NLP extracted events to physical City Graph zones.
Handles exact zone name matching and fallbacks for generic city-wide events.
"""
from core.database import get_db
from datetime import datetime
import random

from services.city_graph_service import ZONE_DEFINITIONS
from core.logger import logger

class EventMapperService:
    def __init__(self):
        # Create a mapping for efficient lookup
        self.zone_map = {z["name"].lower(): z["id"] for z in ZONE_DEFINITIONS}
        # Fallback to the central zone (T. Nagar) if the location doesn't map cleanly
        self.fallback_zone = "Z5"

    async def map_and_store_event(self, nlp_event: dict):
        """
        Takes an NLP event from the spaCy pipeline and maps it to a physical zone.
        Stores the mapped event in the `real_events` collection.
        
        Expected input shape:
        {
            "event_type": "strike",
            "location": "Chennai",
            "severity": "high",
            "confidence": 0.85
        }
        """
        location = nlp_event.get("location", "Unknown").lower()
        
        # 1. ── Try Exact/Partial Match to a specific zone ─────────────────────
        zone_id = None
        for z_name, z_id in self.zone_map.items():
            if z_name in location:
                zone_id = z_id
                break
                
        # 2. ── Fallback Logic ────────────────────────────────────────────────
        # If the location is generic (e.g., "Chennai") or "Unknown", assign it
        # to the central zone (Z5) or a random cluster.
        if not zone_id:
            zone_id = self.fallback_zone
            
        doc = {
            "zone_id": zone_id,
            "type": nlp_event.get("event_type", "unknown"),
            "severity": nlp_event.get("severity", "low"),
            "confidence": nlp_event.get("confidence", 0.0),
            "status": "active",
            "timestamp": datetime.utcnow().isoformat(),
            "original_location_text": nlp_event.get("location")
        }
        
        db = get_db()
        if db is not None:
            # 3. ── Deduplication before inserting ────────────────────────────────
            duplicate = await db["real_events"].find_one({
                "zone_id": doc["zone_id"],
                "type": doc["type"],
                "status": "active"
            })
            
            if duplicate:
                logger.info(f"[EventMapper] Duplicate {doc['type']} dropped for zone {zone_id} (already active)")
                return {"is_new": False, "doc": duplicate}
            
            await db["real_events"].insert_one(doc)
            logger.info(f"[EventMapper] Mapped NEW {doc['type']} event (conf: {doc['confidence']}) to zone {doc['zone_id']}")
            
        return {"is_new": True, "doc": doc}

event_mapper = EventMapperService()

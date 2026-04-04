"""
City Graph Service
------------------
Models the city as a NetworkX directed graph.

  Nodes = Zones (Z1–Z9 in a 3×3 grid)
  Edges = Roads between adjacent zones

Zone states:
  GREEN  → normal conditions
  YELLOW → partial disruption (longer path exists)
  RED    → fully blocked (no path)

Risk score: 0.0 (safe) → 1.0 (critical)
"""

import random
import math
import networkx as nx
from datetime import datetime
from typing import Dict, List, Any, Optional

# ─── Chennai zone layout (3×3 grid) ─────────────────────────────────────────
# Real-ish coordinates centred on Chennai

ZONE_DEFINITIONS = [
    # Row 0 (north)
    {"id": "Z1", "name": "Aminjikarai",    "lat": 13.0850, "lon": 80.2185, "row": 0, "col": 0},
    {"id": "Z2", "name": "Kilpauk",        "lat": 13.0827, "lon": 80.2389, "row": 0, "col": 1},
    {"id": "Z3", "name": "Perambur",       "lat": 13.1131, "lon": 80.2528, "row": 0, "col": 2},
    # Row 1 (central)
    {"id": "Z4", "name": "Anna Nagar",     "lat": 13.0800, "lon": 80.2099, "row": 1, "col": 0},
    {"id": "Z5", "name": "T. Nagar",       "lat": 13.0418, "lon": 80.2341, "row": 1, "col": 1},
    {"id": "Z6", "name": "Royapettah",     "lat": 13.0523, "lon": 80.2650, "row": 1, "col": 2},
    # Row 2 (south)
    {"id": "Z7", "name": "Adyar",          "lat": 13.0012, "lon": 80.2565, "row": 2, "col": 0},
    {"id": "Z8", "name": "Velachery",      "lat": 12.9882, "lon": 80.2180, "row": 2, "col": 1},
    {"id": "Z9", "name": "Tambaram",       "lat": 12.9249, "lon": 80.1000, "row": 2, "col": 2},
]

# Road connections (bidirectional edges in grid + some diagonals)
ROAD_EDGES = [
    # Horizontal
    ("Z1", "Z2"), ("Z2", "Z3"),
    ("Z4", "Z5"), ("Z5", "Z6"),
    ("Z7", "Z8"), ("Z8", "Z9"),
    # Vertical
    ("Z1", "Z4"), ("Z4", "Z7"),
    ("Z2", "Z5"), ("Z5", "Z8"),
    ("Z3", "Z6"), ("Z6", "Z9"),
    # Diagonal shortcuts
    ("Z1", "Z5"), ("Z2", "Z6"),
    ("Z4", "Z8"), ("Z5", "Z9"),
]

# Base travel time in minutes per edge (affects delays)
BASE_TRAVEL_TIMES: Dict[tuple, int] = {
    ("Z1","Z2"): 8,  ("Z2","Z3"): 10, ("Z4","Z5"): 7,  ("Z5","Z6"): 9,
    ("Z7","Z8"): 12, ("Z8","Z9"): 15, ("Z1","Z4"): 11, ("Z4","Z7"): 14,
    ("Z2","Z5"): 9,  ("Z5","Z8"): 13, ("Z3","Z6"): 8,  ("Z6","Z9"): 16,
    ("Z1","Z5"): 13, ("Z2","Z6"): 11, ("Z4","Z8"): 14, ("Z5","Z9"): 15,
}


class CityGraph:
    """
    Manages the real-time state of all city zones and road network.
    Thread-safe for use with asyncio (single-threaded event loop).
    """

    def __init__(self):
        self.G = nx.DiGraph()
        self._zones: Dict[str, Dict] = {}
        self._build_graph()
        self._disruption: Optional[str] = None   # current active disruption type
        self._tick_count = 0

    def _build_graph(self):
        """Initialise nodes and edges, all zones start GREEN."""
        for z in ZONE_DEFINITIONS:
            baseline_orders = random.randint(150, 400)
            node_data = {
                **z,
                "state": "GREEN",
                "risk_score": round(random.uniform(0.05, 0.18), 2),
                "blocked": False,
                "delay_factor": 1.0,
                "baseline_orders": baseline_orders,
                "orders_per_minute": baseline_orders + random.randint(-15, 15),
                "active_restaurants": random.randint(25, 50),
                "demand_score": round(random.uniform(0.8, 1.0), 2),
                "collapse_reason": None,
                "pool_balance": round(random.uniform(15000, 50000), 2),
                "pool_contributors": random.randint(10, 45),
            }
            self.G.add_node(z["id"], **node_data)
            self._zones[z["id"]] = node_data

        for src, dst in ROAD_EDGES:
            t = BASE_TRAVEL_TIMES.get((src, dst), BASE_TRAVEL_TIMES.get((dst, src), 10))
            self.G.add_edge(src, dst, travel_time=t, blocked=False)
            self.G.add_edge(dst, src, travel_time=t, blocked=False)

    # ── Public zone accessors ─────────────────────────────────────────────────

    def get_all_zones(self) -> List[Dict]:
        """Return list of all zone dicts with current state."""
        return list(self._zones.values())

    def get_zone(self, zone_id: str) -> Optional[Dict]:
        return self._zones.get(zone_id)

    def get_analytics(self) -> Dict:
        states = [z["state"] for z in self._zones.values()]
        return {
            "total_zones": len(states),
            "green_zones":  states.count("GREEN"),
            "yellow_zones": states.count("YELLOW"),
            "red_zones":    states.count("RED"),
            "avg_risk": round(sum(z["risk_score"] for z in self._zones.values()) / len(self._zones), 3),
            "active_disruption": self._disruption,
            "tick": self._tick_count,
        }

    # ── Disruption application ────────────────────────────────────────────────

    def apply_rain(self, intensity: float = 0.9) -> List[str]:
        """
        Heavy rain: affect all zones, block most roads, mark high-risk zones RED.
        Returns list of affected zone IDs.
        """
        self._disruption = "RAIN"
        affected = []

        for zone_id, z in self._zones.items():
            r = random.uniform(intensity * 0.7, intensity)
            z["risk_score"] = round(min(r, 1.0), 2)
            if r > 0.75:
                z["state"] = "RED"
                z["blocked"] = True
            elif r > 0.45:
                z["state"] = "YELLOW"
                z["delay_factor"] = round(random.uniform(1.4, 2.0), 1)
            affected.append(zone_id)
            self.G.nodes[zone_id].update(z)

        # Block about half the edges
        for src, dst in self.G.edges():
            if random.random() < 0.4:
                self.G[src][dst]["blocked"] = True

        return affected

    def apply_traffic(self, delay_minutes: int = 30) -> List[str]:
        """Traffic jam: some zones delayed (YELLOW), high-congestion nodes RED."""
        self._disruption = "TRAFFIC"
        affected = []
        severity = min(delay_minutes / 60.0, 1.0)

        for zone_id, z in self._zones.items():
            # Increase base severity for demo impact
            r = random.uniform(severity * 0.6, severity * 1.0)
            z["risk_score"] = round(max(z["risk_score"], r), 2)
            # DEMO FIX: Guarantee RED zones for many, YELLOW for the rest
            if r > 0.4:
                z["state"] = "RED"
                z["delay_factor"] = round(random.uniform(3.0, 5.5), 1)
            else:
                z["state"] = "YELLOW"
                z["delay_factor"] = round(random.uniform(1.8, 3.0), 1)
            affected.append(zone_id)
            self.G.nodes[zone_id].update(z)

        return affected

    def apply_strike(self) -> List[str]:
        """Strike/protest: 2–4 zones fully blocked (RED), surrounding areas YELLOW."""
        self._disruption = "STRIKE"
        zone_ids = list(self._zones.keys())
        strike_zones = random.sample(zone_ids, k=random.randint(2, 4))
        affected = []

        for zone_id, z in self._zones.items():
            if zone_id in strike_zones:
                z["state"] = "RED"
                z["risk_score"] = round(random.uniform(0.85, 0.99), 2)
                z["blocked"] = True
                # Block all edges from this zone
                for _, dst in list(self.G.out_edges(zone_id)):
                    self.G[zone_id][dst]["blocked"] = True
            elif any(nx.has_path(self.G, s, zone_id) and
                     nx.shortest_path_length(self.G, s, zone_id, weight="travel_time") < 15
                     for s in strike_zones if self.G.has_node(s)):
                z["state"] = "YELLOW"
                z["risk_score"] = round(random.uniform(0.45, 0.75), 2)
            self.G.nodes[zone_id].update(z)
            affected.append(zone_id)

        return affected

    def apply_demand_collapse(self) -> List[str]:
        """Demand collapse: Orders plunge, restaurants go offline."""
        self._disruption = "DEMAND_COLLAPSE"
        zone_ids = list(self._zones.keys())
        collapse_zones = random.sample(zone_ids, k=random.randint(1, 4))
        affected = []

        for zone_id, z in self._zones.items():
            if zone_id in collapse_zones:
                z["orders_per_minute"] = int(z["baseline_orders"] * random.uniform(0.3, 0.5))
                z["active_restaurants"] = random.randint(5, 12)
                z["demand_score"] = round(random.uniform(0.1, 0.3), 2)
                
                z["state"] = "RED"
                z["risk_score"] = round(random.uniform(0.85, 0.99), 2)
                z["collapse_reason"] = "DEMAND"
                affected.append(zone_id)
            self.G.nodes[zone_id].update(z)
            
        return affected

    def clear_disruption(self) -> None:
        """Gradually restore all zones to GREEN."""
        self._disruption = None
        for zone_id, z in self._zones.items():
            z["state"] = "GREEN"
            z["risk_score"] = round(random.uniform(0.05, 0.18), 2)
            z["blocked"] = False
            z["delay_factor"] = 1.0
            z["collapse_reason"] = None
            z["orders_per_minute"] = z["baseline_orders"] + random.randint(-10, 10)
            z["active_restaurants"] = max(25, z.get("active_restaurants", 10) + 10)
            z["demand_score"] = round(random.uniform(0.8, 1.0), 2)
            self.G.nodes[zone_id].update(z)
        for src, dst in self.G.edges():
            self.G[src][dst]["blocked"] = False

    # ── Route intelligence ───────────────────────────────────────────────────

    def get_route_status(self, source: str, target: str) -> Dict:
        """
        Dijkstra shortest path analysis on live graph.
        Returns: GREEN (optimal), YELLOW (long detour), RED (no path).
        """
        # Remove blocked edges for pathfinding
        available = nx.DiGraph()
        for s, d, data in self.G.edges(data=True):
            if not data.get("blocked"):
                available.add_edge(s, d, travel_time=data["travel_time"])

        try:
            path = nx.dijkstra_path(available, source, target, weight="travel_time")
            length = nx.dijkstra_path_length(available, source, target, weight="travel_time")
            base_len = BASE_TRAVEL_TIMES.get((source, target), BASE_TRAVEL_TIMES.get((target, source), 10))

            if length > base_len * 1.8:
                status = "YELLOW"
            else:
                status = "GREEN"

            return {"status": status, "path": path, "travel_time": length,
                    "delay_minutes": max(0, round(length - base_len))}
        except nx.NetworkXNoPath:
            return {"status": "RED", "path": [], "travel_time": None, "delay_minutes": None}
        except Exception:
            return {"status": "RED", "path": [], "travel_time": None, "delay_minutes": None}

    # ── Natural decay tick ───────────────────────────────────────────────────

    def tick(self) -> List[str]:
        """
        Simulate natural, stochastic state evolution.
        Called every ~4 seconds by the simulation loop.
        Returns list of zone IDs whose state changed.
        """
        self._tick_count += 1
        changed = []

        for zone_id, z in self._zones.items():
            old_state = z["state"]

            # Demand fluctuation (simulate realistic order flow)
            if self._disruption != "DEMAND_COLLAPSE" or z.get("collapse_reason") != "DEMAND":
                z["orders_per_minute"] = max(10, int(z["orders_per_minute"] + random.uniform(-10, 10)))
                # Mean reversion
                if z["orders_per_minute"] > z["baseline_orders"] * 1.1:
                    z["orders_per_minute"] = int(z["orders_per_minute"] * 0.95)
                elif z["orders_per_minute"] < z["baseline_orders"] * 0.9:
                    z["orders_per_minute"] = int(z["orders_per_minute"] * 1.05)
                
                z["active_restaurants"] = max(10, min(60, z["active_restaurants"] + random.randint(-1, 1)))
                z["demand_score"] = round(max(0.1, min(1.0, z["demand_score"] + random.uniform(-0.02, 0.02))), 2)

            # Simulated weekly premium drip funding the zone's collective pool
            z["pool_balance"] = round(z["pool_balance"] + (z.get("pool_contributors", 0) * random.uniform(0.1, 0.5)), 2)

            if self._disruption:
                # Under active disruption: small random fluctuations
                delta = random.uniform(-0.04, 0.06)
                z["risk_score"] = round(max(0.0, min(1.0, z["risk_score"] + delta)), 2)
            else:
                # Natural recovery: drift back toward GREEN
                z["risk_score"] = round(max(0.05, z["risk_score"] * 0.88 + random.uniform(-0.02, 0.03)), 2)
                z["blocked"] = False
                z["delay_factor"] = 1.0
                if z.get("collapse_reason") == "DEMAND" and z["orders_per_minute"] > z["baseline_orders"] * 0.7:
                    z["collapse_reason"] = None

            # Re-classify zone
            r = z["risk_score"]
            
            # Demand Collapse overriding condition
            is_demand_collapse = (
                z["orders_per_minute"] < z["baseline_orders"] * 0.6 or 
                z["active_restaurants"] < 15 or 
                z["demand_score"] < 0.4
            )
            
            if is_demand_collapse:
                z["state"] = "RED"
                z["collapse_reason"] = "DEMAND"
                z["risk_score"] = max(r, 0.80)
            elif r > 0.7:
                z["state"] = "RED"
            elif r > 0.4:
                z["state"] = "YELLOW"
            else:
                z["state"] = "GREEN"

            self.G.nodes[zone_id].update(z)

            if z["state"] != old_state:
                changed.append(zone_id)

        return changed


# Singleton instance shared across the app
city_graph = CityGraph()

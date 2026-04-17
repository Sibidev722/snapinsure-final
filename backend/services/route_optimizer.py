import logging
import networkx as nx
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

class RouteOptimizer:
    """
    Optimizes gig worker routes by balancing delivery time, risk factors (weather/outages),
    and surge pricing using a NetworkX simulation graph.
    """
    def __init__(self):
        self.graph = nx.Graph()
        self._initialize_base_graph()

    def _initialize_base_graph(self):
        """
        Builds a baseline mocked city grid graph to test the routing logic.
        In production, this would be updated dynamically via real-time DB syncs.
        """
        # Node format: id, and features are attached to edges
        edges_data = [
            ("A", "B", {"time": 10.0, "risk": 0.2, "surge": 1.5, "base_earnings": 5.0}),
            ("A", "C", {"time": 15.0, "risk": 0.8, "surge": 5.0, "base_earnings": 10.0}),
            ("B", "D", {"time": 12.0, "risk": 0.1, "surge": 1.0, "base_earnings": 4.0}),
            ("C", "D", {"time": 8.0,  "risk": 0.9, "surge": 6.0, "base_earnings": 8.0}),
            ("D", "E", {"time": 20.0, "risk": 0.3, "surge": 2.0, "base_earnings": 6.0}),
            ("B", "E", {"time": 25.0, "risk": 0.0, "surge": 0.5, "base_earnings": 4.5}),
        ]
        
        for u, v, attrs in edges_data:
            # Apply the specific formula: weight = time + (risk * 0.5) - (surge * 0.8)
            time = attrs["time"]
            risk = attrs["risk"]
            surge = attrs["surge"]
            
            raw_weight = time + (risk * 0.5) - (surge * 0.8)
            
            # Ensure weight never drops below zero to prevent shortest_path infinite loops (Dijkstra)
            safe_weight = max(0.1, raw_weight)
            
            self.graph.add_edge(u, v, weight=safe_weight, time=time, risk=risk, surge=surge, base_earnings=attrs["base_earnings"])

    def update_edge_metrics(self, u: str, v: str, time: float, risk: float, surge: float):
        """
        Dynamically update path weights based on live incoming data.
        """
        if self.graph.has_edge(u, v):
            raw_weight = time + (risk * 0.5) - (surge * 0.8)
            safe_weight = max(0.1, raw_weight)
            self.graph[u][v].update({"time": time, "risk": risk, "surge": surge, "weight": safe_weight})

    def apply_live_weather(self, weather_data: dict):
        """
        Adjusts all edge risk weights in the routing graph based on live weather.
        Called by the Live Simulator Worker every 10s after fetching Open-Meteo.
        - RED zone (heavy rain)  → risk × 1.8, time × 1.3  (roads flooded)
        - YELLOW zone (rain)     → risk × 1.3, time × 1.1
        - GREEN zone (clear)     → restore to baseline weights
        """
        zone = weather_data.get("zone", "GREEN")
        risk_multiplier = 1.0
        time_multiplier = 1.0

        if zone == "RED":
            risk_multiplier = 1.8
            time_multiplier = 1.3
        elif zone == "YELLOW":
            risk_multiplier = 1.3
            time_multiplier = 1.1

        for u, v, data in self.graph.edges(data=True):
            base_risk = data.get("risk", 0.3)
            base_time = data.get("time", 10.0)
            base_surge = data.get("surge", 1.0)

            new_risk = min(1.0, base_risk * risk_multiplier)
            new_time = base_time * time_multiplier
            raw_weight = new_time + (new_risk * 0.5) - (base_surge * 0.8)
            self.graph[u][v]["weight"] = max(0.1, raw_weight)
            self.graph[u][v]["risk"] = new_risk

        logger.info(f"[RouteOptimizer] Edge weights updated for weather zone={zone} (risk×{risk_multiplier}, time×{time_multiplier})")

    def get_optimal_route(self, start: str, destination: str) -> Dict[str, Any]:
        """
        Calculates the safest and highest paying route.
        Returns the optimized path and cumulatively calculates expected earnings + risk.
        """
        try:
            if start not in self.graph or destination not in self.graph:
                return {
                    "route": [],
                    "expected_earnings": 0.0,
                    "risk_score": 0.0,
                    "message": "Start or Destination not found in active graph."
                }

            # Find the path that minimizes the calculated safe weight
            optimal_path = nx.shortest_path(self.graph, source=start, target=destination, weight="weight")
            
            # Tally up the cumulative metrics for the exact path taken
            total_earnings = 0.0
            total_risk = 0.0
            total_time = 0.0
            
            for i in range(len(optimal_path) - 1):
                u = optimal_path[i]
                v = optimal_path[i+1]
                edge_data = self.graph[u][v]
                
                # Earnings = base + surge multiplier effect
                total_earnings += edge_data["base_earnings"] * (1.0 + edge_data["surge"])
                total_risk += edge_data["risk"]
                total_time += edge_data["time"]

            # Average the risk over the segments
            avg_risk = total_risk / max(1, (len(optimal_path) - 1))

            return {
                "route": optimal_path,
                "expected_earnings": round(total_earnings, 2),
                "risk_score": round(avg_risk, 2),
                "estimated_time": round(total_time, 1)
            }
            
        except nx.NetworkXNoPath:
            logger.warning(f"No path found between {start} and {destination}")
            return {
                "route": [],
                "expected_earnings": 0.0,
                "risk_score": 0.0,
                "message": "No viable path exists due to network disconnection."
            }
        except Exception as e:
            logger.error(f"Routing optimization error: {e}")
            return {
                "route": [],
                "expected_earnings": 0.0,
                "risk_score": 0.0,
                "message": str(e)
            }

# Singleton instance
route_optimizer = RouteOptimizer()

import networkx as nx
from typing import List

class RouteIntelligence:
    def __init__(self):
        self.graph = nx.Graph()
        self._initialize_city_grid()
        
    def _initialize_city_grid(self):
        # Create a simplified 3x3 city grid for Demo purposes
        # Zones: Z1 to Z9
        zones = [f"Z{i}" for i in range(1, 10)]
        self.graph.add_nodes_from(zones)
        
        # Add edges (simplified connectivity)
        edges = [
            ("Z1", "Z2"), ("Z2", "Z3"),
            ("Z4", "Z5"), ("Z5", "Z6"),
            ("Z7", "Z8"), ("Z8", "Z9"),
            ("Z1", "Z4"), ("Z4", "Z7"),
            ("Z2", "Z5"), ("Z5", "Z8"),
            ("Z3", "Z6"), ("Z6", "Z9")
        ]
        self.graph.add_edges_from(edges)
        
    def get_shortest_path(self, source: str, target: str) -> List[str]:
        try:
            return nx.shortest_path(self.graph, source=source, target=target)
        except nx.NetworkXNoPath:
            return []
            
    def get_adjacent_zones(self, zone_id: str) -> List[str]:
        if self.graph.has_node(zone_id):
            return list(self.graph.neighbors(zone_id))
        return []

    def get_city_graph_data(self):
        return nx.node_link_data(self.graph)

    async def check_delivery_route(self, source_zone: str, target_zone: str, db) -> dict:
        from models.models import ZoneState

        # 1. Fetch current RED zones
        cursor = db["zones"].find({"state": ZoneState.RED})
        red_docs = await cursor.to_list(length=100)
        red_zones = [doc["_id"] for doc in red_docs]

        # 2. Get optimal path
        optimal_path = self.get_shortest_path(source_zone, target_zone)
        if not optimal_path:
            return {"status": "RED", "time_loss": None}

        # 3. Create subgraph that excludes RED nodes
        safe_nodes = [node for node in self.graph.nodes if node not in red_zones]
        safe_subgraph = self.graph.subgraph(safe_nodes)

        # 4. Find path in safe subgraph
        try:
            actual_path = nx.shortest_path(safe_subgraph, source=source_zone, target=target_zone)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return {"status": "RED", "time_loss": None}

        # 5. Evaluate difference
        if len(actual_path) == len(optimal_path):
            return {"status": "GREEN", "time_loss": 0}
        else:
            time_loss = (len(actual_path) - len(optimal_path)) * 5
            return {"status": "YELLOW", "time_loss": time_loss}

route_intel_engine = RouteIntelligence()

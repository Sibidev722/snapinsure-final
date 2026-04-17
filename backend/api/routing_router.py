from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.route_optimizer import route_optimizer
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/routing", tags=["Route Optimizer"])


class RouteRequest(BaseModel):
    start: str
    destination: str


class UpdateEdgeRequest(BaseModel):
    u: str
    v: str
    time: float
    risk: float
    surge: float


@router.post("/optimal")
async def get_optimal_route(request: RouteRequest):
    """
    Returns the optimal route between two city nodes.
    Balances earnings (surge) against time and risk using NetworkX Dijkstra.
    Formula: weight = time + (risk * 0.5) - (surge * 0.8)
    """
    result = route_optimizer.get_optimal_route(request.start, request.destination)
    if not result["route"]:
        raise HTTPException(status_code=404, detail=result.get("message", "No route found"))
    return {"success": True, **result}


@router.post("/update-edge")
async def update_edge(request: UpdateEdgeRequest):
    """
    Dynamically updates an edge's live metrics (time/risk/surge).
    Call this from the simulation engine when city conditions change.
    """
    route_optimizer.update_edge_metrics(request.u, request.v, request.time, request.risk, request.surge)
    return {"success": True, "message": f"Edge {request.u}→{request.v} updated"}


@router.get("/graph-nodes")
async def list_graph_nodes():
    """Returns all currently active nodes in the route graph."""
    nodes = list(route_optimizer.graph.nodes)
    return {"success": True, "nodes": nodes, "count": len(nodes)}

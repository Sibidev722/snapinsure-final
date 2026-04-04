from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from services.nlp_service import get_nlp_risk

router = APIRouter()


class NLPRiskResponse(BaseModel):
    detected: bool
    zone: str
    reason: str
    keywords_found: list[str]
    articles_scanned: int


@router.get(
    "/nlp-risk",
    response_model=NLPRiskResponse,
    tags=["NLP Disruption Detection"],
    summary="Detect city disruptions from latest news",
    description=(
        "Fetches the latest news for a given city via NewsAPI (or GNews as fallback) "
        "and scans headlines/descriptions for disruption keywords.\n\n"
        "**Keyword tiers:**\n"
        "- 🔴 **RED** — curfew, shutdown, riot, violence, explosion, lockdown, emergency\n"
        "- 🟡 **YELLOW** — strike, protest, blockade, flood, clashes, bandh, hartal\n"
        "- 🟢 **GREEN** — no disruption keywords found\n\n"
        "Set `NEWS_API_KEY` in `.env` for live data. Falls back to simulation if no key."
    )
)
async def nlp_risk(
    city: str = Query(..., example="Chennai", description="City name to scan news for")
) -> NLPRiskResponse:
    """
    GET /nlp-risk?city=Chennai

    Returns disruption detection results with severity zone.
    """
    if not city.strip():
        raise HTTPException(status_code=400, detail="city parameter cannot be empty")
    try:
        result = await get_nlp_risk(city.strip())
        return NLPRiskResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"NLP risk analysis failed: {str(e)}")

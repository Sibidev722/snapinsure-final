"""
NLP Disruption Detection Service — powered by NewsAPI
Fetches latest news for a city and scans headlines/descriptions for
disruption keywords, returning a GREEN / YELLOW / RED classification.

Severity tiers
--------------
RED    → high-severity keywords: curfew, shutdown, riot, violence, explosion
YELLOW → medium-severity keywords: strike, protest, blockade, flood, clashes
GREEN  → no matching keywords found

If multiple keywords are found, the highest tier wins.
"""

import httpx
from core.logger import logger
from core.config import settings
from typing import cast

# ---------------------------------------------------------------------------
# Keyword severity map — order matters: RED > YELLOW
# ---------------------------------------------------------------------------
RED_KEYWORDS = [
    "curfew", "shutdown", "riot", "violence", "explosion",
    "lockdown", "emergency", "bomb", "attack", "arrest mass"
]

YELLOW_KEYWORDS = [
    "strike", "protest", "blockade", "flood", "clashes",
    "demonstration", "agitation", "disruption", "bandh", "hartal",
    "roadblock", "closed roads"
]

NEWSAPI_URL = "https://newsapi.org/v2/everything"
GNEWS_URL   = "https://gnews.io/api/v4/search"


def _classify_text(text: str) -> tuple[str | None, list[str]]:
    """
    Scan text for disruption keywords.
    Returns (severity_tier | None, list_of_matched_keywords).
    """
    lower = text.lower()
    matched_red    = [kw for kw in RED_KEYWORDS    if kw in lower]
    matched_yellow = [kw for kw in YELLOW_KEYWORDS if kw in lower]

    if matched_red:
        return "RED", matched_red
    if matched_yellow:
        return "YELLOW", matched_yellow
    return None, []


async def get_nlp_risk(city: str) -> dict:
    """
    Main entry point.  Tries NewsAPI first, falls back to GNews.
    Returns:
        {
            "detected": bool,
            "zone": "GREEN" | "YELLOW" | "RED",
            "reason": str,
            "keywords_found": [...],
            "articles_scanned": int
        }
    """
    news_key  = settings.NEWS_API_KEY
    gnews_key = settings.GNEWS_API_KEY if hasattr(settings, "GNEWS_API_KEY") else None

    # ── Try NewsAPI ──────────────────────────────────────────────────────────
    if news_key and not news_key.startswith("http") and not news_key.startswith("your_"):
        result = await _fetch_newsapi(city, news_key)
        if result is not None:
            return result

    # ── Try GNews ────────────────────────────────────────────────────────────
    if gnews_key and not gnews_key.startswith("your_"):
        result = await _fetch_gnews(city, gnews_key)
        if result is not None:
            return result

    # ── No valid keys — return simulation fallback ───────────────────────────
    logger.warning("No valid NEWS_API_KEY or GNEWS_API_KEY. Returning simulation fallback.")
    return {
        "detected": True,
        "zone": "YELLOW",
        "reason": f"[Demo] Strike activity simulated for {city} — set NEWS_API_KEY in .env for live data",
        "keywords_found": ["strike"],
        "articles_scanned": 0
    }


async def _fetch_newsapi(city: str, api_key: str) -> dict | None:
    """Call NewsAPI /everything and run keyword scan on returned articles."""
    query = f"{city} strike OR protest OR curfew OR shutdown OR riot OR flood OR blockade"
    params = {
        "q": query,
        "sortBy": "publishedAt",
        "apiKey": api_key,
        "language": "en",
        "pageSize": 20,
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(NEWSAPI_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"NewsAPI HTTP {e.response.status_code}: {e.response.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"NewsAPI request failed: {e}")
        return None

    articles = data.get("articles", [])
    return _analyse_articles(articles, city, source="NewsAPI")


async def _fetch_gnews(city: str, api_key: str) -> dict | None:
    """Call GNews /search and run keyword scan on returned articles."""
    query = f"{city} strike OR protest OR curfew OR shutdown OR riot"
    params = {
        "q": query,
        "token": api_key,
        "lang": "en",
        "max": 20,
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(GNEWS_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"GNews HTTP {e.response.status_code}: {e.response.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"GNews request failed: {e}")
        return None

    articles = data.get("articles", [])
    return _analyse_articles(articles, city, source="GNews")


def _analyse_articles(articles: list, city: str, source: str) -> dict:
    """
    Iterate articles, scan title + description for keywords.
    Return the highest severity found across all articles.
    """
    overall_tier   = None
    all_keywords: list[str] = []

    for article in articles:
        blob = " ".join(filter(None, [
            article.get("title", ""),
            article.get("description", ""),
            article.get("content", ""),
        ]))
        tier, kws = _classify_text(blob)
        all_keywords.extend(kws)

        if tier == "RED":
            overall_tier = "RED"
        elif tier == "YELLOW" and overall_tier != "RED":
            overall_tier = "YELLOW"

    unique_kws = list(dict.fromkeys(all_keywords))  # deduplicate, preserve order

    if overall_tier is None:
        return {
            "detected": False,
            "zone": "GREEN",
            "reason": f"No disruption keywords found in {city} news ({source}, {len(articles)} articles scanned)",
            "keywords_found": [],
            "articles_scanned": len(articles)
        }

    # At this point overall_tier is guaranteed to be "RED" or "YELLOW"
    primary_kw = unique_kws[0] if unique_kws else "disruption"
    tier_str: str = cast(str, overall_tier)  # Pyre2: cast narrows Optional[str] → str
    reason_map: dict[str, str] = {
        "RED":    f"{primary_kw} detected in {city} — HIGH severity disruption risk",
        "YELLOW": f"{primary_kw} detected in {city} — moderate disruption risk",
    }

    return {
        "detected": True,
        "zone": tier_str,
        "reason": reason_map.get(tier_str, f"{primary_kw} detected in {city}"),
        "keywords_found": unique_kws[:5],
        "articles_scanned": len(articles)
    }

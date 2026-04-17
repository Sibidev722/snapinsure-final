"""
Raw News Fetcher Service
------------------------
Fetches news articles from NewsAPI using specific disruption keywords.
Stores them in the `news_raw` MongoDB collection.
Features: Deduplication, Rate limit handling.
"""

import httpx
import asyncio
from datetime import datetime
from core.database import get_db
from core.config import settings
from core.logger import logger

NEWSAPI_URL = "https://newsapi.org/v2/everything"
GDELT_URL   = "https://api.gdeltproject.org/api/v2/doc/doc"
KEYWORDS = ["strike", "protest", "shutdown", "union", "block", "bandh", "riot", "curfew"]

class NewsFetcherService:
    def __init__(self):
        # We process deduplication by caching the latest title seen
        # A more robust DB approach relies on unique indexing
        self._last_call_time = 0
        self._rate_limit_delay = 15.0 # seconds minimum between calls to avoid HTTP 429
        
        # ── In-Memory Cache for Background Worker ────────────────────────────
        self._gdelt_cache: dict[str, dict] = {}
        self._is_worker_running = False
        self._worker_task: asyncio.Task | None = None

    async def fetch_and_store_news(self, city: str):
        """
        Fetches news for a specific city and stores deduplicated results in `news_raw`.
        """
        api_key = settings.NEWS_API_KEY
        if not api_key or api_key.startswith("your_") or api_key.startswith("http"):
            logger.warning("[NewsFetcher] No valid NEWS_API_KEY found. Skipping fetch.")
            return {"success": False, "reason": "No API key"}

        db = get_db()
        if db is None:
            logger.warning("[NewsFetcher] Database not available.")
            return {"success": False, "reason": "No Database"}

        # Rate Limiting Handling
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_call_time
        if elapsed < self._rate_limit_delay:
            wait_time = self._rate_limit_delay - elapsed
            logger.debug(f"[NewsFetcher] Rate limiting: waiting {wait_time:.2f}s before next API call.")
            await asyncio.sleep(wait_time)

        self._last_call_time = asyncio.get_event_loop().time()

        # Build query from keywords
        query_str = " OR ".join(KEYWORDS)
        query = f"{city} AND ({query_str})"
        
        params = {
            "q": query,
            "sortBy": "publishedAt",
            "apiKey": api_key,
            "language": "en",
            "pageSize": 20,
        }

        logger.info(f"[NewsFetcher] Fetching raw news for {city}...")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(NEWSAPI_URL, params=params)
                
                # Check rate limits explicitly from NewsAPI
                if resp.status_code == 429:
                    logger.warning("[NewsFetcher] Rate limited (HTTP 429). Backing off for 60 seconds.")
                    self._rate_limit_delay = 60.0 # Increase delay if we hit
                    return {"success": False, "reason": "Rate limited"}
                
                resp.raise_for_status()
                data = resp.json()
                
                # Reset rate limit delay back to normal on success
                self._rate_limit_delay = 15.0 

        except httpx.HTTPError as e:
            logger.error(f"[NewsFetcher] HTTP Request failed: {e}")
            return {"success": False, "reason": str(e)}
        except Exception as e:
            logger.error(f"[NewsFetcher] Unexpected error: {e}")
            return {"success": False, "reason": str(e)}

        articles = data.get("articles", [])
        if not articles:
            logger.debug(f"[NewsFetcher] No new articles found for {city}.")
            return {"success": True, "inserted": 0}

        # Deduplication and Storage
        inserted_count = 0
        new_articles_data = []
        for article in articles:
            title = article.get("title")
            description = article.get("description")
            published_at = article.get("publishedAt")

            if not title:
                continue

            # Deduplication: Check if an article with exact same title exists
            existing = await db["news_raw"].find_one({"title": title})
            
            if not existing:
                doc = {
                    "city": city,
                    "title": title,
                    "description": description,
                    "timestamp": published_at or datetime.utcnow().isoformat(),
                    "ingested_at": datetime.utcnow().isoformat()
                }
                await db["news_raw"].insert_one(doc)
                inserted_count += 1
                new_articles_data.append(doc)

        logger.info(f"[NewsFetcher] Processed {len(articles)} articles. Inserted {inserted_count} new into `news_raw`.")
        return {"success": True, "inserted": inserted_count, "articles": new_articles_data}

    async def fetch_gdelt_news(self, city: str, use_cache: bool = False) -> dict:
        """
        Fetch real-time disruption news from GDELT API.
        GDELT is free, no API key required, updates every 15 minutes.
        Returns the same schema as fetch_and_store_news for compatibility.
        """
        # Return cached results if available and requested
        if use_cache and city in self._gdelt_cache:
            cache_entry = self._gdelt_cache[city]
            # Simple freshness check: background worker updates every 5 min
            logger.debug(f"[NewsFetcher] Returning cached GDELT news for {city}")
            return cache_entry

        db = get_db()
        keyword_query = " OR ".join(KEYWORDS)
        query = f"{city} ({keyword_query})"

        params = {
            "query":      query,
            "mode":       "artlist",
            "maxrecords": "20",
            "format":     "json",
            "timespan":   "6h",    # Last 6 hours
            "sort":       "DateDesc",
        }

        logger.info(f"[NewsFetcher] Fetching GDELT real-time news for {city}...")
        
        # ── Robust Async Fetch with Retry ─────────────────────────────────────
        max_retries = 3
        data = None
        
        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(GDELT_URL, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                    break  # Success
            except (httpx.RequestError, httpx.HTTPError) as e:
                logger.warning(f"[NewsFetcher] GDELT fetch failed (attempt {attempt}/{max_retries}): {e}")
                if attempt < max_retries:
                    await asyncio.sleep(2.0 ** attempt)  # Exponential backoff
                else:
                    return {"success": False, "reason": f"Failed after {max_retries} attempts: {str(e)}", "articles": []}
            except Exception as e:
                logger.warning(f"[NewsFetcher] Unexpected GDELT fetch error: {e}")
                return {"success": False, "reason": str(e), "articles": []}

        if data is None:
            return {"success": False, "reason": "No data fetched", "articles": []}

        articles_raw = data.get("articles", [])
        if not articles_raw:
            logger.debug(f"[NewsFetcher] GDELT: no articles for {city}")
            return {"success": True, "inserted": 0, "articles": []}

        inserted_count = 0
        new_articles = []
        for art in articles_raw:
            title   = art.get("title", "").strip()
            url     = art.get("url", "")
            seendate = art.get("seendate", "")

            if not title:
                continue

            if db is not None:
                existing = await db["news_raw"].find_one({"title": title})
                if existing:
                    continue

                doc = {
                    "city":        city,
                    "title":       title,
                    "description": art.get("socialimage", ""),
                    "url":         url,
                    "source":      "gdelt",
                    "timestamp":   seendate or datetime.utcnow().isoformat(),
                    "ingested_at": datetime.utcnow().isoformat(),
                }
                await db["news_raw"].insert_one(doc)
                inserted_count += 1
                new_articles.append(doc)

        logger.info(f"[NewsFetcher] GDELT: processed {len(articles_raw)} articles, "
                    f"inserted {inserted_count} new into `news_raw`.")
        
        result_payload = {"success": True, "inserted": inserted_count, "articles": new_articles}
        
        # Update cache on successful fetch
        self._gdelt_cache[city] = result_payload
        
        return result_payload

    # ── Background Worker ────────────────────────────────────────────────────

    def start_worker(self, city: str = "Chennai"):
        """Start the background autonomous news fetcher loop."""
        if self._is_worker_running:
            logger.info("[NewsFetcher] Background worker already running.")
            return

        self._is_worker_running = True
        self._worker_task = asyncio.create_task(self._gdelt_worker_loop(city))
        logger.info(f"[NewsFetcher] Background worker started for {city}.")

    def stop_worker(self):
        """Stop the background worker."""
        if self._is_worker_running:
            self._is_worker_running = False
            if self._worker_task:
                self._worker_task.cancel()
            logger.info("[NewsFetcher] Background worker stopped.")

    async def _gdelt_worker_loop(self, city: str):
        """Polls GDELT every 5 minutes in the background."""
        while self._is_worker_running:
            try:
                # We do NOT use cache here to force a fresh API fetch.
                # fetch_gdelt_news automatically updates self._gdelt_cache
                result = await self.fetch_gdelt_news(city, use_cache=False)
                if not result.get("success"):
                    logger.warning(f"[NewsFetcher] Worker fetch failed: {result.get('reason')}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[NewsFetcher] Worker loop crashed: {e}", exc_info=True)
            
            # Poll every 5 minutes
            await asyncio.sleep(300)

    async def fetch_all_sources(self, city: str) -> dict:
        """
        Fetch from both NewsAPI and GDELT, merge results.
        Runs both in parallel for efficiency.
        """
        newsapi_result, gdelt_result = await asyncio.gather(
            self.fetch_and_store_news(city),
            self.fetch_gdelt_news(city, use_cache=True),
            return_exceptions=True,
        )

        all_articles = []
        if isinstance(newsapi_result, dict) and newsapi_result.get("articles"):
            all_articles.extend(newsapi_result["articles"])
        if isinstance(gdelt_result, dict) and gdelt_result.get("articles"):
            all_articles.extend(gdelt_result["articles"])

        total = len(all_articles)
        logger.info(f"[NewsFetcher] Combined fetch for {city}: {total} new articles total")
        return {"success": True, "articles": all_articles, "total": total}


news_fetcher_service = NewsFetcherService()

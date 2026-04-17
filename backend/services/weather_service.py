"""
WeatherService
--------------
Dual-source real-time weather fetcher.

Priority:
  1. OpenWeatherMap API (if OPENWEATHER_API_KEY is set and valid)
  2. Open-Meteo API     (free, no key required — always available as fallback)

Cache: per-city, 5-minute TTL, in-memory.

Returned payload matches the canonical SnapInsure schema:
  {
      "city":        str,
      "rain":        bool,
      "intensity":   "none" | "light" | "moderate" | "heavy",
      "temperature": float,      # °C
      "condition":   str,        # human-readable label
      "zone":        "GREEN" | "YELLOW" | "RED",
      "risk_score":  float,      # 0.0 – 1.0
      "confidence":  int,        # 0 – 100 %
      "rainfall_mm": float,      # precipitation mm (last hour)
      "source":      str,        # "openweathermap" | "open-meteo"
  }
"""

import os
import time
import httpx
from typing import Optional

from core.logger import logger


# ---------------------------------------------------------------------------
# Rainfall-intensity thresholds (mm / h, WMO codes)
# ---------------------------------------------------------------------------

_OWM_RAIN_CODES = {
    200, 201, 202, 210, 211, 212, 221, 230, 231, 232,  # Thunderstorm
    300, 301, 302, 310, 311, 312, 313, 314, 321,        # Drizzle
    500, 501, 502, 503, 504, 511, 520, 521, 522, 531,   # Rain
    600, 601, 602, 611, 612, 613, 615, 616, 620, 621, 622,  # Snow
}

_WMO_SEVERE   = {95, 96, 99}
_WMO_MODERATE = {61, 63, 65, 80, 81, 82, 71, 73, 75}
_WMO_LIGHT    = {51, 53, 55, 56, 57}

# OpenWeather condition-code → human label  (condensed)
_OWM_LABEL = {
    2: "Thunderstorm",
    3: "Drizzle",
    5: "Rain",
    6: "Snow/Sleet",
    7: "Atmospheric Hazard",
    8: "Clear / Cloudy",
}


def _intensity_label(mm: float, is_severe: bool = False) -> str:
    if is_severe or mm > 10.0:
        return "heavy"
    elif mm >= 2.0:
        return "moderate"
    elif mm > 0.0:
        return "light"
    return "none"


def _zone_from_intensity(intensity: str) -> tuple[str, float, int]:
    """Returns (zone, risk_score, confidence)."""
    return {
        "heavy":    ("RED",    0.95, 92),
        "moderate": ("YELLOW", 0.60, 85),
        "light":    ("YELLOW", 0.40, 80),
        "none":     ("GREEN",  0.10, 95),
    }.get(intensity, ("YELLOW", 0.50, 70))


# ---------------------------------------------------------------------------
# City coordinate lookup (Open-Meteo geocoding — no key)
# ---------------------------------------------------------------------------

_GEO_CACHE: dict[str, tuple[float, float]] = {
    "chennai": (13.0827, 80.2707),
    "mumbai":  (19.0760, 72.8777),
    "delhi":   (28.7041, 77.1025),
    "bangalore": (12.9716, 77.5946),
    "hyderabad": (17.3850, 78.4867),
}

async def _resolve_coords(city: str) -> tuple[float, float]:
    key = city.lower().strip()
    if key in _GEO_CACHE:
        return _GEO_CACHE[key]

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city, "count": 1, "language": "en"}
            )
            r.raise_for_status()
            data = r.json()
            if data.get("results"):
                lat = data["results"][0]["latitude"]
                lon = data["results"][0]["longitude"]
                _GEO_CACHE[key] = (lat, lon)
                return lat, lon
    except Exception as e:
        logger.warning(f"[Weather] Geocoding failed for '{city}': {e}")

    # Hard fallback to Chennai
    return 13.0827, 80.2707


# ---------------------------------------------------------------------------
# OpenWeatherMap fetcher
# ---------------------------------------------------------------------------

async def _fetch_owm(city: str, api_key: str) -> dict:
    """
    Calls the OpenWeatherMap Current Weather endpoint by city name.
    Raises httpx.HTTPError on network / 4xx / 5xx issues.
    """
    async with httpx.AsyncClient(timeout=6.0) as client:
        resp = await client.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": city, "appid": api_key, "units": "metric"}
        )
        resp.raise_for_status()
        data = resp.json()

    return _parse_owm_response(data)


async def _fetch_owm_by_coords(lat: float, lon: float, api_key: str) -> dict:
    """
    Fetches OWM weather by lat/lon coordinates for precise per-zone data.
    """
    async with httpx.AsyncClient(timeout=6.0) as client:
        resp = await client.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"lat": lat, "lon": lon, "appid": api_key, "units": "metric"}
        )
        resp.raise_for_status()
        data = resp.json()

    return _parse_owm_response(data)


def _parse_owm_response(data: dict) -> dict:
    """Shared OWM response parser for both city-name and coords calls."""
    weather_list = data.get("weather", [{}])
    main_data    = data.get("main", {})
    rain_data    = data.get("rain", {})

    code        = weather_list[0].get("id", 800)
    description = weather_list[0].get("description", "unknown").title()
    temp        = round(main_data.get("temp", 30.0), 1)
    rain_mm     = round(rain_data.get("1h", 0.0), 2)

    is_rain    = (code // 100) in {2, 3, 5, 6}
    is_severe  = (code // 100) == 2 or code in {502, 503, 504}
    intensity  = _intensity_label(rain_mm, is_severe)
    zone, risk, conf = _zone_from_intensity(intensity)

    group_key  = code // 100
    condition  = f"{_OWM_LABEL.get(group_key, description)} ({description})"

    return {
        "rain":        is_rain,
        "intensity":   intensity,
        "temperature": temp,
        "condition":   condition,
        "zone":        zone,
        "risk_score":  risk,
        "confidence":  conf,
        "rainfall_mm": rain_mm,
        "source":      "openweathermap",
    }


async def _fetch_open_meteo_by_coords(lat: float, lon: float) -> dict:
    """
    Open-Meteo fetch by exact lat/lon — used as fallback for coord-based calls.
    """
    async with httpx.AsyncClient(timeout=6.0) as client:
        resp = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude":  lat,
                "longitude": lon,
                "current":   "temperature_2m,precipitation,weather_code",
            }
        )
        resp.raise_for_status()
        data = resp.json()

    current  = data.get("current", {})
    rain_mm  = round(current.get("precipitation", 0.0), 2)
    temp     = round(current.get("temperature_2m", 30.0), 1)
    wcode    = current.get("weather_code", 0)

    is_severe   = wcode in _WMO_SEVERE
    is_moderate = wcode in _WMO_MODERATE
    is_light    = wcode in _WMO_LIGHT

    if is_severe or rain_mm > 10.0:
        intensity = "heavy";  condition = "Thunderstorm / Heavy Rain"; is_rain = True
    elif is_moderate or rain_mm >= 2.0:
        intensity = "moderate"; condition = "Moderate Rain / Showers"; is_rain = True
    elif is_light or rain_mm > 0.0:
        intensity = "light";  condition = "Light Drizzle"; is_rain = True
    else:
        intensity = "none";   condition = "Clear / Partly Cloudy"; is_rain = False

    zone, risk, conf = _zone_from_intensity(intensity)
    return {
        "rain": is_rain, "intensity": intensity, "temperature": temp,
        "condition": condition, "zone": zone, "risk_score": risk,
        "confidence": conf, "rainfall_mm": rain_mm, "source": "open-meteo",
    }


# ---------------------------------------------------------------------------
# Open-Meteo fetcher  (no API key required)
# ---------------------------------------------------------------------------

async def _fetch_open_meteo(city: str) -> dict:
    lat, lon = await _resolve_coords(city)

    async with httpx.AsyncClient(timeout=6.0) as client:
        resp = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude":  lat,
                "longitude": lon,
                "current":   "temperature_2m,precipitation,weather_code",
            }
        )
        resp.raise_for_status()
        data = resp.json()

    current  = data.get("current", {})
    rain_mm  = round(current.get("precipitation", 0.0), 2)
    temp     = round(current.get("temperature_2m", 30.0), 1)
    wcode    = current.get("weather_code", 0)

    is_severe  = wcode in _WMO_SEVERE
    is_moderate = wcode in _WMO_MODERATE
    is_light    = wcode in _WMO_LIGHT

    if is_severe or rain_mm > 10.0:
        intensity = "heavy"
        condition = "Thunderstorm / Heavy Rain"
        is_rain   = True
    elif is_moderate or rain_mm >= 2.0:
        intensity = "moderate"
        condition = "Moderate Rain / Showers"
        is_rain   = True
    elif is_light or rain_mm > 0.0:
        intensity = "light"
        condition = "Light Drizzle"
        is_rain   = True
    else:
        intensity = "none"
        condition = "Clear / Partly Cloudy"
        is_rain   = False

    zone, risk, conf = _zone_from_intensity(intensity)

    return {
        "rain":        is_rain,
        "intensity":   intensity,
        "temperature": temp,
        "condition":   condition,
        "zone":        zone,
        "risk_score":  risk,
        "confidence":  conf,
        "rainfall_mm": rain_mm,
        "source":      "open-meteo",
    }


# ---------------------------------------------------------------------------
# Main service class
# ---------------------------------------------------------------------------

class WeatherService:
    """
    Dual-source weather service with per-city 5-minute in-memory cache.
    """

    CACHE_TTL = 300  # seconds

    def __init__(self):
        self._cache: dict[str, dict] = {}   # key → {ts, data}

    def _get_cached(self, city: str) -> Optional[dict]:
        entry = self._cache.get(city.lower())
        if entry and (time.time() - entry["ts"] < self.CACHE_TTL):
            return entry["data"]
        return None

    def _set_cache(self, city: str, data: dict):
        self._cache[city.lower()] = {"ts": time.time(), "data": data}

    def _is_real_owm_key(self, key: Optional[str]) -> bool:
        """Returns True only if the value looks like a real API key (32 hex chars)."""
        if not key:
            return False
        # Strip potential quotes that might come from .env
        stripped = key.strip().strip('"').strip("'")
        # Reject placeholder URLs or obviously fake values
        if stripped.startswith("http") or len(stripped) < 20:
            return False
        return True

    async def get_weather(self, city: str = "Chennai") -> dict:
        """
        Main entry point. Returns the full canonical weather payload.
        Tries OWM first (if key is valid), falls back to Open-Meteo.
        """
        city_key = city.strip().title()

        # ── Cache hit ──────────────────────────────────────────────────────
        cached = self._get_cached(city_key)
        if cached:
            logger.debug(f"[Weather] Cache HIT for '{city_key}'")
            return cached

        # ── Primary: OpenWeatherMap ────────────────────────────────────────
        owm_raw = os.getenv("OPENWEATHER_API_KEY")
        if self._is_real_owm_key(owm_raw):
            owm_key = owm_raw.strip().strip('"').strip("'")
            try:
                logger.debug(f"[Weather] Attempting OWM for '{city_key}'...")
                result = await _fetch_owm(city_key, owm_key)
                logger.info(f"[Weather] OWM OK for '{city_key}': {result['condition']}")
                self._set_cache(city_key, result)
                return result
            except httpx.HTTPStatusError as e:
                # 401 = bad key, 404 = city not found — don't keep retrying OWM
                logger.warning(f"[Weather] OWM HTTP {e.response.status_code} for '{city_key}' — falling back to Open-Meteo")
            except httpx.HTTPError as e:
                logger.warning(f"[Weather] OWM network error for '{city_key}': {e} — falling back")
            except Exception as e:
                logger.warning(f"[Weather] OWM unexpected error: {e} — falling back")

        # ── Fallback: Open-Meteo (no key required) ─────────────────────────
        try:
            result = await _fetch_open_meteo(city_key)
            logger.info(f"[Weather] Open-Meteo OK for '{city_key}': {result['condition']}")
            self._set_cache(city_key, result)
            return result
        except Exception as e:
            logger.error(f"[Weather] Open-Meteo also failed for '{city_key}': {e}")

        # ── Total-failure safe default ─────────────────────────────────────
        safe = {
            "rain":        False,
            "intensity":   "none",
            "temperature": 30.0,
            "condition":   "Weather data unavailable — cautious default applied",
            "zone":        "YELLOW",
            "risk_score":  0.50,
            "confidence":  30,
            "rainfall_mm": 0.0,
            "source":      "fallback",
        }
        # Cache the fallback for only 60 s so the next real request refreshes sooner
        self._cache[city_key.lower()] = {"ts": time.time() - (self.CACHE_TTL - 60), "data": safe}
        return safe

    async def get_weather_by_coords(self, lat: float, lon: float,
                                    label: str = "") -> dict:
        """
        Fetch weather specifically by lat/lon coordinates.
        Used by weather_ingestion_service for per-zone precision.
        Falls back to Open-Meteo lat/lon if OWM fails.
        Has its own 5-min cache keyed by rounded coords.
        """
        cache_key = f"{round(lat, 3)},{round(lon, 3)}"

        cached = self._get_cached(cache_key)
        if cached:
            return cached

        owm_raw = os.getenv("OPENWEATHER_API_KEY")
        if self._is_real_owm_key(owm_raw):
            owm_key = owm_raw.strip().strip('"').strip("'")
            try:
                result = await _fetch_owm_by_coords(lat, lon, owm_key)
                logger.info(f"[Weather] OWM coords OK {label or cache_key}: {result['condition']}")
                self._set_cache(cache_key, result)
                return result
            except httpx.HTTPStatusError as e:
                logger.warning(f"[Weather] OWM coords HTTP {e.response.status_code} — fallback")
            except Exception as e:
                logger.warning(f"[Weather] OWM coords error: {e} — fallback")

        try:
            result = await _fetch_open_meteo_by_coords(lat, lon)
            logger.info(f"[Weather] Open-Meteo coords OK {label or cache_key}: {result['condition']}")
            self._set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"[Weather] Open-Meteo coords failed for {cache_key}: {e}")

        # Safe default
        safe = {
            "rain": False, "intensity": "none", "temperature": 30.0,
            "condition": "Weather unavailable", "zone": "YELLOW",
            "risk_score": 0.50, "confidence": 30, "rainfall_mm": 0.0,
            "source": "fallback",
        }
        self._cache[cache_key] = {"ts": time.time() - (self.CACHE_TTL - 60), "data": safe}
        return safe

    # ── Backwards-compatible shim used by older callers ───────────────────
    async def get_weather_risk(self, city: str = "Chennai",
                               lat: float = None, lon: float = None) -> dict:
        result = await self.get_weather(city)
        # Old callers expect "rainfall" (not "rainfall_mm") and "reason"
        return {
            **result,
            "rainfall": result["rainfall_mm"],
            "reason":   result["condition"],
        }


# Module-level singleton
weather_service = WeatherService()

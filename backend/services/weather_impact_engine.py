"""
Weather Impact Engine
---------------------
Translates raw weather data into actionable business multipliers for
SnapInsure's demand model, surge pricing, and risk classification.

Input  : canonical weather dict from WeatherService.get_weather()
Output :
  {
      "demand_multiplier": float,   # How much demand increases (1.0 = baseline)
      "surge_multiplier":  float,   # Pricing surge factor
      "risk_level":        str,     # "low" | "medium" | "high" | "critical"
      "risk_score":        float,   # 0.0 – 1.0
      "payout_eligible":  bool,     # Should insurance auto-trigger?
      "recommended_action": str,    # Human-readable advisory
      "factors":           list     # Active factors that influenced the output
  }

Configuration is fully externalizable — pass a custom WeatherImpactConfig
to override any threshold or multiplier.
"""

from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Configuration dataclass — fully overridable
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class WeatherImpactConfig:
    """
    All thresholds and multipliers are configurable here.
    Override any value when instantiating WeatherImpactEngine.
    """

    # ── Demand multipliers by intensity ─────────────────────────────────────
    demand_none:     float = 1.0    # No rain     → baseline demand
    demand_light:    float = 1.2    # Light rain  → slightly more orders (people stay home)
    demand_moderate: float = 1.4    # Moderate    → clear demand surge
    demand_heavy:    float = 1.6    # Heavy rain  → peak demand (delivery rush)

    # ── Surge (pricing) multipliers by intensity ─────────────────────────────
    surge_none:      float = 1.0
    surge_light:     float = 1.1
    surge_moderate:  float = 1.35
    surge_heavy:     float = 1.7

    # ── Risk thresholds (risk_score boundaries) ──────────────────────────────
    risk_low_max:      float = 0.30   # 0.00 – 0.30  → "low"
    risk_medium_max:   float = 0.60   # 0.30 – 0.60  → "medium"
    risk_high_max:     float = 0.85   # 0.60 – 0.85  → "high"
    # anything above risk_high_max                   → "critical"

    # ── Payout auto-trigger threshold ────────────────────────────────────────
    payout_threshold_risk_score: float = 0.60   # Trigger auto-payout if risk ≥ this
    payout_eligible_intensities: tuple = ("moderate", "heavy")

    # ── Risk score contribution weights ──────────────────────────────────────
    weight_intensity:    float = 0.50   # Weather intensity contribution
    weight_temperature:  float = 0.20   # Extreme temperature contribution
    weight_zone:         float = 0.30   # Backend zone (GREEN/YELLOW/RED) contribution

    # ── Temperature extremes (adjust risk if temp is very high or very low) ──
    temp_extreme_heat_threshold: float = 38.0   # °C — heat stress
    temp_extreme_cold_threshold: float = 10.0   # °C — cold hazard
    temp_risk_boost:             float = 0.10   # Added to risk_score on extreme temp


# ─────────────────────────────────────────────────────────────────────────────
# Internal scoring helpers
# ─────────────────────────────────────────────────────────────────────────────

_INTENSITY_ORDER = {"none": 0, "light": 1, "moderate": 2, "heavy": 3}

_ZONE_RISK = {"GREEN": 0.10, "YELLOW": 0.55, "RED": 0.90}

_INTENSITY_BASE_RISK = {"none": 0.05, "light": 0.30, "moderate": 0.60, "heavy": 0.90}


def _risk_level_label(score: float, cfg: WeatherImpactConfig) -> str:
    if score <= cfg.risk_low_max:
        return "low"
    elif score <= cfg.risk_medium_max:
        return "medium"
    elif score <= cfg.risk_high_max:
        return "high"
    return "critical"


def _advisory(intensity: str, risk_level: str, temp: float, cfg: WeatherImpactConfig) -> str:
    if risk_level == "critical":
        return "⛔ Extreme weather — consider suspending deliveries. Auto-payout activated."
    elif risk_level == "high":
        return "🚨 High risk conditions detected — workers should exercise caution. Payout eligible."
    elif risk_level == "medium":
        if intensity == "moderate":
            return "⚠️ Moderate rain surge — increased demand, monitor worker safety."
        if temp >= cfg.temp_extreme_heat_threshold:
            return "🌡️ Heat advisory — high temperature may affect worker performance."
        return "⚠️ Elevated conditions — stay alert to changing weather."
    else:
        if intensity == "light":
            return "🌦️ Light rain — slight demand increase expected. Normal operations."
        return "✅ Conditions normal — baseline operations in effect."


# ─────────────────────────────────────────────────────────────────────────────
# Main Engine
# ─────────────────────────────────────────────────────────────────────────────

class WeatherImpactEngine:
    """
    Converts raw weather data into business-level multipliers and risk signals.

    Usage:
        engine = WeatherImpactEngine()                          # default config
        engine = WeatherImpactEngine(WeatherImpactConfig(...))  # custom config

        impact = engine.compute(weather_data)
    """

    def __init__(self, config: Optional[WeatherImpactConfig] = None):
        self.config = config or WeatherImpactConfig()

    def compute(self, weather: dict) -> dict:
        """
        Core calculation method.

        Args:
            weather: Dict from WeatherService.get_weather(). Expected keys:
                     rain, intensity, temperature, zone, risk_score, condition, source

        Returns:
            Full impact payload.
        """
        cfg = self.config

        # ── Read inputs (safe defaults) ──────────────────────────────────────
        intensity   = weather.get("intensity",    "none").lower()
        is_rain     = weather.get("rain",          False)
        temperature = float(weather.get("temperature", 30.0))
        zone        = weather.get("zone",          "GREEN").upper()
        raw_risk    = float(weather.get("risk_score", 0.1))
        condition   = weather.get("condition",    "Unknown")

        # Normalise intensity to known values
        if intensity not in _INTENSITY_ORDER:
            intensity = "none"

        # ── Demand & surge multipliers ───────────────────────────────────────
        demand_map = {
            "none":     cfg.demand_none,
            "light":    cfg.demand_light,
            "moderate": cfg.demand_moderate,
            "heavy":    cfg.demand_heavy,
        }
        surge_map = {
            "none":     cfg.surge_none,
            "light":    cfg.surge_light,
            "moderate": cfg.surge_moderate,
            "heavy":    cfg.surge_heavy,
        }

        demand_multiplier = demand_map[intensity]
        surge_multiplier  = surge_map[intensity]

        # ── Composite risk score ─────────────────────────────────────────────
        intensity_risk = _INTENSITY_BASE_RISK[intensity]
        zone_risk      = _ZONE_RISK.get(zone, 0.50)

        # Weighted blend
        composite_risk = (
            cfg.weight_intensity   * intensity_risk +
            cfg.weight_zone        * zone_risk +
            cfg.weight_temperature * raw_risk   # raw_risk carries temp/humidity signal
        )

        # Temperature extreme boost
        temp_boost = 0.0
        if temperature >= cfg.temp_extreme_heat_threshold:
            temp_boost = cfg.temp_risk_boost
        elif temperature <= cfg.temp_extreme_cold_threshold:
            temp_boost = cfg.temp_risk_boost

        composite_risk = min(1.0, round(composite_risk + temp_boost, 3))

        # ── Risk level label ─────────────────────────────────────────────────
        risk_level = _risk_level_label(composite_risk, cfg)

        # ── Payout eligibility ───────────────────────────────────────────────
        payout_eligible = (
            composite_risk >= cfg.payout_threshold_risk_score or
            intensity in cfg.payout_eligible_intensities
        )

        # ── Active factors list ──────────────────────────────────────────────
        factors = []
        if is_rain:
            factors.append(f"Rain detected ({intensity} intensity)")
        if intensity == "heavy":
            factors.append("Heavy rain → demand surge + risk spike")
        elif intensity == "moderate":
            factors.append("Moderate rain → elevated demand")
        elif intensity == "light":
            factors.append("Light drizzle → mild demand increase")
        if temperature >= cfg.temp_extreme_heat_threshold:
            factors.append(f"Extreme heat ({temperature}°C) → worker stress risk")
        elif temperature <= cfg.temp_extreme_cold_threshold:
            factors.append(f"Cold temperature ({temperature}°C) → road hazard risk")
        if zone == "RED":
            factors.append("City zone RED → maximum risk multiplier applied")
        elif zone == "YELLOW":
            factors.append("City zone YELLOW → moderate risk elevated")
        if not factors:
            factors.append("No disruptive factors — baseline conditions")

        # ── Advisory message ─────────────────────────────────────────────────
        advisory = _advisory(intensity, risk_level, temperature, cfg)

        return {
            "demand_multiplier":   round(demand_multiplier, 3),
            "surge_multiplier":    round(surge_multiplier, 3),
            "risk_level":          risk_level,
            "risk_score":          composite_risk,
            "payout_eligible":     payout_eligible,
            "recommended_action":  advisory,
            "factors":             factors,
            # ── Pass-through for traceability ──────────────────────────────
            "input_summary": {
                "intensity":   intensity,
                "rain":        is_rain,
                "temperature": temperature,
                "zone":        zone,
                "condition":   condition,
                "source":      weather.get("source", "unknown"),
            },
        }


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton (default config)
# ─────────────────────────────────────────────────────────────────────────────

weather_impact_engine = WeatherImpactEngine()

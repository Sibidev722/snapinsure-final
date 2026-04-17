"""
GDELT Event Parser — Social Disruption Signal Extractor
========================================================
Converts raw GDELT event fields into a normalised social_disruption_score
for ingestion by the GNN feature pipeline.

GDELT data model used
----------------------
  Tone      : float, range [-100, +100]
              Negative = adverse/conflict/crisis language.
              Positive = stable/celebratory language.
              Source: GDELT GKG Tone field (column V2Tone, first sub-field).

  EventCode : str, CAMEO event code  (e.g. "145", "193", "051")
              A two-to-four digit code from the CAMEO taxonomy that
              classifies the type of geopolitical action described.
              Reference: https://gdeltproject.org/data/documentation/
                         CAMEO.Manual.1.1b3.pdf

Design decisions
----------------
• Zero hardcoded score values — all weights live in _EVENT_CATEGORY_WEIGHTS
  so the taxonomy can be extended without touching parser logic.
• Confidence degrades gracefully when inputs are missing or invalid,
  rather than raising exceptions — ensures the GNN never gets a dead signal.
• The EventCode prefix lookup is O(1) via a pre-built trie-style prefix dict.
• Tone normalisation uses a sigmoid-family transform so extreme values
  don't dominate (avoids cliff effects at ±100).
"""

from __future__ import annotations

import math
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# CAMEO EventCode taxonomy → risk weight mapping
# ─────────────────────────────────────────────────────────────────────────────
# Structure:
#   key   : CAMEO root code prefix (1-3 digits as string)
#   value : (event_type_label: str, risk_weight: float [0, 1])
#
# CAMEO codes are hierarchical:
#   "01"  = Make Public Statement          (low risk)
#   "02"  = Appeal                         (low risk)
#   "04"  = Consult                        (low risk)
#   "05"  = Engage in Diplomatic Cooperation
#   "06"  = Material Cooperation
#   "07"  = Provide Aid
#   "10"  = Demand                         (moderate disruption signal)
#   "11"  = Disapprove
#   "12"  = Reject
#   "13"  = Threaten                       (escalation)
#   "14"  = Protest                        (HIGH — primary disruption)
#   "15"  = Force - Non-military           (HIGH)
#   "16"  = Reduce Relations               (economic stress)
#   "17"  = Coercion (non-lethal)          (HIGH)
#   "18"  = Assault                        (HIGH)
#   "19"  = Fight                          (CRITICAL)
#   "20"  = Mass Violence                  (CRITICAL)
#   Longer codes are more specific sub-events; prefix match is used.
#
# Economic stress signal codes (sourced from CAMEO supplemental taxonomy):
#   "ECS" prefix in GDELT-GKG Themes column → mapped via keyword match.
# ─────────────────────────────────────────────────────────────────────────────

_EVENT_CATEGORY_WEIGHTS: Dict[str, Tuple[str, float]] = {
    # ── Cooperative / low-risk events ─────────────────────────────────────────
    "01":  ("public_statement",           0.05),
    "02":  ("appeal",                     0.05),
    "03":  ("express_intent_to_cooperate",0.05),
    "04":  ("consult",                    0.05),
    "05":  ("diplomatic_cooperation",     0.05),
    "06":  ("material_cooperation",       0.05),
    "07":  ("provide_aid",                0.05),
    "08":  ("yield",                      0.10),
    "09":  ("investigate",                0.10),

    # ── Moderate disruption ───────────────────────────────────────────────────
    "10":  ("demand",                     0.30),
    "11":  ("disapprove",                 0.25),
    "12":  ("reject",                     0.30),
    "13":  ("threaten",                   0.45),

    # ── High disruption — Protests & Civil Unrest ─────────────────────────────
    "14":  ("protest",                    0.70),
    "140": ("protest_general",            0.70),
    "141": ("demonstrate_or_rally",       0.65),
    "142": ("conducts_hunger_strike",     0.60),
    "143": ("conducts_strike_or_boycott", 0.80),
    "144": ("obstruct_passage",           0.75),
    "145": ("protests_violently",         0.85),

    # ── High disruption — Non-military force ──────────────────────────────────
    "15":  ("force_non_military",         0.75),
    "150": ("impose_embargo",             0.70),
    "151": ("conduct_blockade",           0.80),
    "152": ("occupy_territory",           0.80),
    "153": ("conduct_siege",              0.85),
    "154": ("execute_political_dissidents",0.90),

    # ── Economic pressure ─────────────────────────────────────────────────────
    "16":  ("reduce_relations",           0.50),
    "160": ("reduce_relations_general",   0.50),
    "163": ("reduce_economic_cooperation",0.60),
    "164": ("reduce_military_cooperation",0.55),

    # ── Coercion ──────────────────────────────────────────────────────────────
    "17":  ("coerce",                     0.70),
    "171": ("seize_possession",           0.75),
    "172": ("conduct_suicide_attack",     0.90),
    "173": ("conduct_bombing",            0.90),
    "174": ("abduct_or_kidnap",           0.85),

    # ── Assault ───────────────────────────────────────────────────────────────
    "18":  ("assault",                    0.80),
    "180": ("assault_general",            0.80),
    "181": ("physically_assault",         0.82),
    "182": ("torture",                    0.85),
    "183": ("conduct_coup_de_tat",        0.95),
    "186": ("attempt_assassination",      0.90),

    # ── Armed conflict ────────────────────────────────────────────────────────
    "19":  ("fight",                      0.90),
    "190": ("use_unconventional_violence",0.92),
    "191": ("conduct_military_operation", 0.90),
    "193": ("conduct_missile_attack",     0.92),
    "194": ("conduct_WMD_attack",         1.00),
    "195": ("conduct_cyberattack",        0.85),

    # ── Mass violence ─────────────────────────────────────────────────────────
    "20":  ("mass_violence",              0.95),
    "200": ("human_rights_abuse",         0.90),
    "201": ("engage_in_ethnic_cleansing", 1.00),
    "203": ("engage_in_genocide",         1.00),

    # ── Economic stress (GDELT GKG supplemental) ──────────────────────────────
    "ECS": ("economic_stress",            0.60),
    "ENV": ("environmental_disruption",   0.45),
    "UNREST": ("unrest_event",            0.70),
}

# Events not in the taxonomy → fallback weight (assumed background noise)
_DEFAULT_EVENT_TYPE:   str   = "unknown_event"
_DEFAULT_EVENT_WEIGHT: float = 0.20

# Tone normalisation parameters
_TONE_SHARPNESS: float = 0.05   # controls sigmoid steepness; tunable
_TONE_MIN: float = -100.0
_TONE_MAX: float = +100.0


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalise_tone(tone: float) -> float:
    """
    Convert GDELT Tone [-100, +100] → risk contribution [0.0, 1.0].

    The transform inverts and applies a soft sigmoid so extreme values
    don't cliff to exactly 0 or 1 — preserving gradient for downstream ML.

    Formula:
        tone_risk = sigmoid(-tone * sharpness)   # negative tone → high risk
        sigmoid(x) = 1 / (1 + exp(-x))

    Calibration checkpoints (sharpness=0.05):
        tone = -100  → risk ≈ 0.993  (very negative → very high risk)
        tone =   -50 → risk ≈ 0.924
        tone =     0 → risk = 0.500  (neutral)
        tone =   +50 → risk ≈ 0.076
        tone = +100  → risk ≈ 0.007  (very positive → near-zero risk)
    """
    tone_clipped = max(_TONE_MIN, min(float(tone), _TONE_MAX))
    return round(1.0 / (1.0 + math.exp(tone_clipped * _TONE_SHARPNESS)), 4)


def _resolve_event_code(event_code: str) -> Tuple[str, float]:
    """
    Resolve an EventCode to its (event_type_label, risk_weight) pair.

    Lookup strategy (most-specific first):
      1. Exact match on the full code     (e.g. "145" → "protests_violently")
      2. 3-character prefix match         (e.g. "1451" → lookup "145")
      3. 2-character prefix match         (e.g. "14xx" → lookup "14")
      4. String prefix match on GKG codes (e.g. "ECS*" → "ECS")
      5. Default fallback                 (weight=0.20)
    """
    code = str(event_code).strip().upper()

    # Direct match first
    if code in _EVENT_CATEGORY_WEIGHTS:
        return _EVENT_CATEGORY_WEIGHTS[code]

    # GKG-style string prefix (ECS, ENV, UNREST)
    for prefix in ("UNREST", "ECS", "ENV"):
        if code.startswith(prefix):
            return _EVENT_CATEGORY_WEIGHTS[prefix]

    # Numeric CAMEO prefix: try 3-digit, then 2-digit
    numeric = code[:3] if len(code) >= 3 else code
    if numeric in _EVENT_CATEGORY_WEIGHTS:
        return _EVENT_CATEGORY_WEIGHTS[numeric]

    numeric2 = code[:2] if len(code) >= 2 else code
    if numeric2 in _EVENT_CATEGORY_WEIGHTS:
        return _EVENT_CATEGORY_WEIGHTS[numeric2]

    return _DEFAULT_EVENT_TYPE, _DEFAULT_EVENT_WEIGHT


def _compute_confidence(
    tone_raw:   Optional[float],
    event_code: Optional[str],
) -> float:
    """
    Estimate how confident we are in the output score.

    Confidence degrades based on missing / invalid inputs:
      Both present and valid → 0.90  (ceiling; GDELT itself is noisy)
      Only tone available    → 0.65
      Only event_code        → 0.55
      Neither                → 0.20  (maximum uncertainty fallback)
    """
    has_tone  = tone_raw is not None
    has_code  = event_code is not None and str(event_code).strip() != ""
    unknown   = event_code is not None and _resolve_event_code(
                    event_code)[0] == _DEFAULT_EVENT_TYPE

    if has_tone and has_code and not unknown:
        return 0.90
    if has_tone and has_code and unknown:
        return 0.70   # code present but not in taxonomy
    if has_tone and not has_code:
        return 0.65
    if not has_tone and has_code and not unknown:
        return 0.55
    return 0.20


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def parse_gdelt_event(
    tone:        Any,
    event_code:  Any,
    *,
    tone_weight:  float = 0.50,
    event_weight: float = 0.50,
) -> Dict[str, Any]:
    """
    Parse a GDELT event record into a normalised social disruption signal.

    Parameters
    ----------
    tone : float | str | None
        GDELT Tone value.  Acceptable ranges:
          • float / int in  [-100, +100]    — native GDELT field
          • str  parseable as float         — e.g. "-34.5,12.3,..." (GKG V2Tone;
            only the *first* comma-delimited sub-field is used)
          • None / empty                    — treated as missing; confidence ↓

    event_code : str | int | None
        CAMEO event code.  Acceptable forms:
          • Numeric string "145", "193"     — CAMEO event codes
          • Integer 145                     — auto-converted to str
          • GKG theme prefix "ECS", "ENV"   — economic/environmental signals
          • None / empty                    — treated as missing; confidence ↓

    tone_weight : float, default 0.5
        Weight given to the tone component in the final fusion.
        tone_weight + event_weight should sum to 1.0.

    event_weight : float, default 0.5
        Weight given to the EventCode component in the final fusion.

    Returns
    -------
    dict:
      disruption_score : float [0, 1]
          Weighted fusion of tone risk and EventCode risk.
          0 = no disruption signal  |  1 = maximum disruption.
      event_type       : str
          Human-readable CAMEO category label.
      confidence       : float [0, 1]
          Model confidence in the output, degraded by missing inputs.
      debug            : dict
          Raw intermediate values for explainability / logging.
      error            : str | None
          Set only when a non-fatal error occurred (output is still valid).
    """
    error_msg:       Optional[str] = None
    tone_risk:       float = 0.5    # neutral fallback
    event_type_label: str  = _DEFAULT_EVENT_TYPE
    event_risk:      float = _DEFAULT_EVENT_WEIGHT
    tone_raw:        Optional[float] = None
    code_str:        Optional[str]   = None

    # ── 1. Parse Tone ────────────────────────────────────────────────────────
    if tone is not None and tone != "":
        try:
            # GKG V2Tone field: "tone,pos,neg,pol,ard,srd,wordcount"
            # We only want the first sub-field (overall document tone).
            tone_str = str(tone).split(",")[0].strip()
            tone_raw = float(tone_str)

            if not (-100.0 <= tone_raw <= 100.0):
                logger.warning(
                    "[GDELTParser] Tone %.2f is out of expected range [-100, 100]; "
                    "clamping.", tone_raw
                )
                tone_raw = max(-100.0, min(tone_raw, 100.0))

            tone_risk = _normalise_tone(tone_raw)

        except (ValueError, TypeError, IndexError) as exc:
            error_msg = f"tone parse error: {exc!r} (raw={tone!r})"
            logger.warning("[GDELTParser] %s", error_msg)
            # tone_risk stays at 0.5 (neutral)
    else:
        logger.debug("[GDELTParser] tone field missing — using neutral 0.5")

    # ── 2. Resolve EventCode ──────────────────────────────────────────────────
    if event_code is not None and str(event_code).strip() != "":
        try:
            code_str = str(int(event_code)) if isinstance(event_code, float) else str(event_code)
            event_type_label, event_risk = _resolve_event_code(code_str)
        except (ValueError, TypeError) as exc:
            error_msg = f"event_code parse error: {exc!r} (raw={event_code!r})"
            logger.warning("[GDELTParser] %s", error_msg)
            # Falls back to default weight
    else:
        logger.debug("[GDELTParser] event_code field missing — using default weight %.2f",
                     _DEFAULT_EVENT_WEIGHT)

    # ── 3. Weight validation ──────────────────────────────────────────────────
    # Normalise weights so they always sum to 1.0 even if caller passes bad values.
    total_w = tone_weight + event_weight
    if total_w <= 0 or not math.isfinite(total_w):
        tone_weight  = 0.50
        event_weight = 0.50
        logger.warning("[GDELTParser] Invalid weights; reset to 0.5 / 0.5")
    else:
        tone_weight  = tone_weight  / total_w
        event_weight = event_weight / total_w

    # ── 4. Fused disruption score ─────────────────────────────────────────────
    disruption_score = round(
        tone_weight * tone_risk + event_weight * event_risk,
        4,
    )

    # ── 5. Confidence ─────────────────────────────────────────────────────────
    confidence = _compute_confidence(tone_raw, code_str)

    # ── 6. Debug payload (full intermediate values for XAI / logging) ─────────
    debug = {
        "tone_raw":       tone_raw,
        "tone_risk":      tone_risk,
        "event_code_raw": code_str,
        "event_type":     event_type_label,
        "event_risk":     event_risk,
        "tone_weight":    round(tone_weight,  4),
        "event_weight":   round(event_weight, 4),
    }

    logger.debug(
        "[GDELTParser] tone=%s → risk=%.3f | code=%s → type=%s risk=%.3f "
        "| fused=%.3f conf=%.2f",
        tone_raw, tone_risk, code_str, event_type_label, event_risk,
        disruption_score, confidence,
    )

    return {
        "disruption_score": disruption_score,
        "event_type":       event_type_label,
        "confidence":       confidence,
        "debug":            debug,
        "error":            error_msg,
    }


def parse_gdelt_batch(
    records: list,
    *,
    tone_key:       str = "tone",
    event_code_key: str = "EventCode",
    tone_weight:    float = 0.50,
    event_weight:   float = 0.50,
) -> list:
    """
    Parse a list of GDELT record dicts, returning one result per record.

    Each record must be a dict (or dict-like).  Missing keys produce
    a low-confidence result rather than an exception.

    Parameters
    ----------
    records        : list of dicts from GDELT API or CSV
    tone_key       : key name for tone field (default "tone")
    event_code_key : key name for event code field (default "EventCode")
    tone_weight    : weight for tone component [0, 1]
    event_weight   : weight for event code component [0, 1]

    Returns
    -------
    list of parse_gdelt_event() result dicts, one per input record.
    """
    results = []
    for idx, rec in enumerate(records):
        try:
            result = parse_gdelt_event(
                tone        = rec.get(tone_key),
                event_code  = rec.get(event_code_key),
                tone_weight = tone_weight,
                event_weight= event_weight,
            )
            result["_index"] = idx
            results.append(result)
        except Exception as exc:
            # Belt-and-suspenders: parse_gdelt_event never raises, but guard anyway
            logger.error("[GDELTParser] Unexpected error at index %d: %s", idx, exc)
            results.append({
                "disruption_score": 0.5,
                "event_type":       "parse_error",
                "confidence":       0.10,
                "debug":            {},
                "error":            str(exc),
                "_index":           idx,
            })
    return results


def aggregate_batch_score(results: list) -> Dict[str, Any]:
    """
    Aggregate a batch of parse results into a single zone-level signal.

    Uses confidence-weighted mean (same formula as weighted_adjudicate)
    so high-confidence records dominate the aggregate.

    Returns
    -------
    dict:
      aggregate_disruption_score : float [0, 1]
      dominant_event_type        : str
      total_records              : int
      valid_records              : int
      mean_confidence            : float
    """
    if not results:
        return {
            "aggregate_disruption_score": 0.0,
            "dominant_event_type":        "no_data",
            "total_records":              0,
            "valid_records":              0,
            "mean_confidence":            0.0,
        }

    numerator   = 0.0
    denominator = 0.0
    event_counts: Dict[str, int] = {}
    valid = 0

    for r in results:
        score = float(r.get("disruption_score", 0.5))
        conf  = float(r.get("confidence",        0.5))
        etype = r.get("event_type", _DEFAULT_EVENT_TYPE)

        numerator   += score * conf
        denominator += conf
        event_counts[etype] = event_counts.get(etype, 0) + 1
        if r.get("error") is None:
            valid += 1

    agg_score   = round(numerator / denominator, 4) if denominator > 0 else 0.5
    mean_conf   = round(denominator / max(len(results), 1), 4)
    dominant    = max(event_counts, key=event_counts.get)

    return {
        "aggregate_disruption_score": agg_score,
        "dominant_event_type":        dominant,
        "total_records":              len(results),
        "valid_records":              valid,
        "mean_confidence":            mean_conf,
    }

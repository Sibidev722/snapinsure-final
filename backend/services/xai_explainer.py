"""
XAI Explainer — Explainable AI for SnapInsure's Graph Attention Network
========================================================================
Generates structured, human-readable explanations for GNN risk predictions
using node feature importance and GAT attention weights.

Design principles:
  • Zero hardcoded strings — all language is assembled from dynamic templates
    keyed on feature identity and importance magnitude.
  • Pure Python / NumPy — no torch dependency at call-time (tensors are
    accepted but immediately converted to plain Python types).
  • Composable output schema compatible with the GNN router API.

Public API:
  generate_explanation(
      node_features    : dict | list[float],
      attention_weights: list[dict] | list[float],  # see schema below
      feature_names    : list[str],
      risk_score       : float,                      # 0.0–1.0
      zone_id          : str         = "",
      neighbor_ids     : list[str]   = [],
      top_k            : int         = 3,
  ) -> ExplanationResult
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


# ─────────────────────────────────────────────────────────────────────────────
# Types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FeatureContribution:
    """One feature's contribution to the final risk prediction."""
    name: str           # e.g. "weather"
    value: float        # raw feature value (0.0–1.0)
    importance: float   # relative importance rank score (0.0–1.0)
    direction: str      # "positive" | "negative" | "neutral"
    label: str          # human-readable token e.g. "severe weather"


@dataclass(frozen=True)
class NeighborInfluence:
    """Attention-derived influence of one neighbouring zone."""
    node_id: str        # e.g. "Z3"
    attention: float    # raw attention weight (0.0–1.0, already normalised)
    rank: int           # 1-indexed rank (1 = most influential)
    label: str          # human-readable token e.g. "high-attention zone Z3"


@dataclass
class ExplanationResult:
    """Structured XAI output returned by generate_explanation()."""
    zone_id: str
    risk_score: float
    risk_level: str                           # "LOW" | "MEDIUM" | "HIGH"
    top_features: List[FeatureContribution]
    top_neighbors: List[NeighborInfluence]
    explanation: str                          # Full prose sentence
    explanation_parts: Dict[str, str] = field(default_factory=dict)
    # ^ structured sub-sentences for UI assembly:
    #   "opening", "feature_clause", "neighbor_clause", "closing"


# ─────────────────────────────────────────────────────────────────────────────
# Feature Vocabulary
# ─────────────────────────────────────────────────────────────────────────────
# Maps a feature_name → (low_label, medium_label, high_label).
# The correct label is chosen based on the feature's normalised value.
# Add new features here without touching any other code.

_FEATURE_VOCAB: Dict[str, Tuple[str, str, str]] = {
    # name              low                  medium                 high
    "weather":        ("mild conditions",   "weather disruption",  "severe weather"),
    "rain":           ("light rain",        "moderate rainfall",   "heavy rain"),
    "strikes":        ("calm social state", "social unrest",       "active strike"),
    "disruption":     ("stable area",       "area disruption",     "critical disruption"),
    "demand":         ("low demand",        "demand surge",        "extreme demand spike"),
    "earnings":       ("low earning zone",  "moderate earnings",   "high earning density"),
    "traffic":        ("free-flowing road", "traffic congestion",  "severe traffic block"),
    "congestion":     ("clear roads",       "traffic buildup",     "gridlock congestion"),
    "accident":       ("no incidents",      "minor incident",      "serious road accident"),
    "flood":          ("no flooding",       "local flooding",      "severe flooding"),
    "supply":         ("oversupply",        "balanced supply",     "supply shortage"),
    "risk":           ("minimal risk",      "elevated risk",       "critical risk signal"),
    "temperature":    ("cool temperature",  "high temperature",    "extreme heat"),
    "wind":           ("calm winds",        "strong winds",        "dangerous wind speed"),
    "sentiment":      ("positive signals",  "mixed signals",       "negative social signals"),
    "historical":     ("low activity area", "moderate history",    "historically volatile"),
    # ── Temporal features ──────────────────────────────────────────────────────
    # Labels describe the shift window, not the raw normalised value.
    # Thresholds (0.35 / 0.65) map roughly to:
    #   time_of_day:  0.35 ≈ 08h (morning), 0.65 ≈ 15h (afternoon peak)
    #   day_of_week:  0.35 ≈ Mon–Tue, 0.65 ≈ Thu–Fri (pre-weekend surge)
    "time_of_day":    ("off-peak hours",    "active shift window", "peak delivery hours"),
    "day_of_week":    ("early week period", "mid-week activity",   "high-demand weekend"),
}

# Fallback vocab pattern when feature_name is not in the dictionary
_FALLBACK_VOCAB: Tuple[str, str, str] = (
    "low {name} signal",
    "elevated {name} signal",
    "critical {name} signal",
)

# ─────────────────────────────────────────────────────────────────────────────
# Risk-level openings (keyed on risk_level × direction of top feature)
# Each value is a callable → str so we can inject dynamic zone IDs etc.
# ─────────────────────────────────────────────────────────────────────────────

_OPENING_TEMPLATES: Dict[str, Dict[str, str]] = {
    "HIGH": {
        "positive": "Elevated payout risk detected{zone_tag}",
        "negative": "Critically adverse conditions{zone_tag}",
        "neutral":  "High risk classification{zone_tag}",
    },
    "MEDIUM": {
        "positive": "Moderate risk conditions present{zone_tag}",
        "negative": "Partial disruption signals{zone_tag}",
        "neutral":  "Intermediate risk level{zone_tag}",
    },
    "LOW": {
        "positive": "Low risk environment{zone_tag}",
        "negative": "Minimal adverse signals{zone_tag}",
        "neutral":  "Stable operating conditions{zone_tag}",
    },
}

_CLOSING_BY_RISK: Dict[str, str] = {
    "HIGH":   "Immediate payout eligibility check triggered.",
    "MEDIUM": "Monitoring advised; conditions may escalate.",
    "LOW":    "No intervention required at this time.",
}


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _to_float(v: Any) -> float:
    """Safely coerce tensor scalars, numpy floats, or plain floats."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _risk_level(score: float) -> str:
    if score >= 0.65:
        return "HIGH"
    if score >= 0.35:
        return "MEDIUM"
    return "LOW"


def _direction(value: float, threshold_low: float = 0.35,
               threshold_high: float = 0.65) -> str:
    """Classify whether a feature value pushes risk up, down, or is neutral."""
    if value >= threshold_high:
        return "positive"   # positively contributing to risk
    if value <= threshold_low:
        return "negative"   # suppressing / contra-indicative of risk
    return "neutral"


def _feature_label(name: str, value: float) -> str:
    """
    Resolve the human-readable label for one feature at its current value.
    Picks the low / medium / high token from the vocab based on value magnitude.
    """
    norm_name = name.lower().strip()

    if norm_name in _FEATURE_VOCAB:
        low_lbl, med_lbl, high_lbl = _FEATURE_VOCAB[norm_name]
    else:
        # Build a contextual fallback from the raw name
        low_lbl  = _FALLBACK_VOCAB[0].format(name=norm_name)
        med_lbl  = _FALLBACK_VOCAB[1].format(name=norm_name)
        high_lbl = _FALLBACK_VOCAB[2].format(name=norm_name)

    if value >= 0.65:
        return high_lbl
    if value >= 0.35:
        return med_lbl
    return low_lbl


def _importance_score(value: float, risk_level: str) -> float:
    """
    Compute a scalar importance for a feature given its value and the overall
    risk level. High-value features matter more in HIGH risk; low-value
    features (suppressors) matter more in LOW risk.
    """
    if risk_level == "HIGH":
        # Weight towards high-value features (they drove risk up)
        return value
    if risk_level == "LOW":
        # Weight towards low-value features (they kept risk down)
        return 1.0 - value
    # MEDIUM — distance from 0.5 centre
    return abs(value - 0.5) * 2.0


def _parse_node_features(
    node_features: Union[Dict[str, float], Sequence[float]],
    feature_names: Sequence[str],
) -> List[Tuple[str, float]]:
    """
    Normalise node_features into a list of (feature_name, value) pairs.

    Accepts:
      • dict  — {name: value, ...}   (feature_names used only for ordering)
      • list  — [v1, v2, ...]         (zipped against feature_names)
    """
    if isinstance(node_features, dict):
        pairs = [(k, _to_float(v)) for k, v in node_features.items()]
        # Honour the caller's preferred ordering via feature_names
        name_set  = {k for k, _ in pairs}
        ordered   = [
            (n, node_features[n]) for n in feature_names if n in name_set
        ]
        remainder = [(k, v) for k, v in pairs if k not in {n for n, _ in ordered}]
        return [(n, _to_float(v)) for n, v in ordered + remainder]
    else:
        values = [_to_float(v) for v in node_features]
        names  = list(feature_names)
        # Pad or trim to match lengths
        while len(names) < len(values):
            names.append(f"feature_{len(names)}")
        return list(zip(names[: len(values)], values))


def _parse_attention_weights(
    attention_weights: Union[
        Sequence[Dict[str, Any]],   # [{node_id, weight}, ...]
        Sequence[float],            # [w0, w1, ...] — parallel to neighbor_ids
    ],
    neighbor_ids: Sequence[str],
) -> List[Tuple[str, float]]:
    """
    Normalise attention_weights into list of (node_id, weight) pairs.

    Accepts three formats:
      1. List of dicts:   [{\"node_id\": \"Z3\", \"weight\": 0.42}, ...]
      2. List of numbers: [0.42, 0.18, ...]  — zipped with neighbor_ids
      3. Tensor-like:     anything with .tolist()
    """
    # Handle tensor-like objects
    if hasattr(attention_weights, "tolist"):
        attention_weights = attention_weights.tolist()  # type: ignore[union-attr]

    if not attention_weights:
        return []

    pairs: List[Tuple[str, float]] = []

    if isinstance(attention_weights[0], dict):
        for item in attention_weights:
            nid = str(item.get("node_id", item.get("id", f"N{len(pairs)}")))
            w   = _to_float(item.get("weight", item.get("attention", 0.0)))
            pairs.append((nid, w))
    else:
        # Numeric sequence — zip with neighbor_ids
        ids = list(neighbor_ids)
        for idx, w in enumerate(attention_weights):
            nid = ids[idx] if idx < len(ids) else f"node_{idx}"
            pairs.append((nid, _to_float(w)))

    # Normalise weights so they sum to 1.0 (handles raw logits)
    total = sum(w for _, w in pairs)
    if total > 0:
        pairs = [(n, w / total) for n, w in pairs]

    return pairs


# ─────────────────────────────────────────────────────────────────────────────
# Sentence builders
# ─────────────────────────────────────────────────────────────────────────────

def _build_feature_clause(features: List[FeatureContribution]) -> str:
    """
    Assemble the feature portion of the explanation.
    e.g. "driven by severe weather, demand surge, and active strike"
    """
    if not features:
        return "driven by multiple risk signals"

    labels = [f.label for f in features]

    if len(labels) == 1:
        return f"driven by {labels[0]}"
    if len(labels) == 2:
        return f"driven by {labels[0]} and {labels[1]}"

    head = ", ".join(labels[:-1])
    return f"driven by {head}, and {labels[-1]}"


def _build_neighbor_clause(neighbors: List[NeighborInfluence]) -> str:
    """
    Assemble the graph-neighbourhood portion of the explanation.
    e.g. "with strong influence from nearby Z3 and Z7"
    """
    if not neighbors:
        return ""

    ids = [n.node_id for n in neighbors]

    if len(ids) == 1:
        return f"with strong graph influence from {ids[0]}"

    head = ", ".join(ids[:-1])
    return f"with strong graph influence from {head} and {ids[-1]}"


def _assemble_prose(
    opening: str,
    feature_clause: str,
    neighbor_clause: str,
    closing: str,
) -> str:
    """Join clauses into a single grammatically correct sentence."""
    parts = [opening]

    if feature_clause:
        parts.append(feature_clause)

    if neighbor_clause:
        # Attach neighbor clause as a subordinate phrase
        core = " ".join(parts) + ", " + neighbor_clause
        return core.strip().rstrip(",") + ". " + closing

    return " ".join(parts) + ". " + closing


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def generate_explanation(
    node_features: Union[Dict[str, float], Sequence[float]],
    attention_weights: Union[Sequence[Dict[str, Any]], Sequence[float]],
    feature_names: Sequence[str],
    risk_score: float = 0.5,
    zone_id: str = "",
    neighbor_ids: Sequence[str] = (),
    top_k: int = 3,
) -> ExplanationResult:
    """
    Generate a structured, human-readable XAI explanation for one GNN node.

    Parameters
    ----------
    node_features
        Feature vector for the target node.
        • dict  → {feature_name: value}
        • list  → values in the same order as feature_names
        Values should be normalised to [0.0, 1.0].

    attention_weights
        Attention weights for each incoming neighbour edge.
        • list[dict] → [{\"node_id\": str, \"weight\": float}]
        • list[float]→ parallel to neighbor_ids
        Raw logits are accepted and will be normalised internally.

    feature_names
        Ordered list of feature names matching the columns in node_features.

    risk_score
        Scalar output risk score from the GNN  [0.0, 1.0].

    zone_id
        Identifier of the target zone (e.g. \"Z4\"). Used in prose.

    neighbor_ids
        Ordered list of neighbour identifiers aligned with attention_weights
        when attention_weights is numeric (not dict).

    top_k
        Number of top features and neighbours to surface.

    Returns
    -------
    ExplanationResult
        Structured output with top_features, top_neighbors, explanation.
    """
    risk_score  = _to_float(risk_score)
    level       = _risk_level(risk_score)
    zone_tag    = f" in zone {zone_id}" if zone_id else ""

    # ── 1. Parse raw inputs ──────────────────────────────────────────────────
    feature_pairs = _parse_node_features(node_features, feature_names)
    attn_pairs    = _parse_attention_weights(attention_weights, neighbor_ids)

    # ── 2. Score & rank features ─────────────────────────────────────────────
    scored: List[Tuple[float, str, float]] = []  # (importance, name, value)
    for name, value in feature_pairs:
        imp = _importance_score(value, level)
        scored.append((imp, name, value))

    scored.sort(key=lambda t: t[0], reverse=True)   # descending importance

    top_features: List[FeatureContribution] = []
    for imp, name, value in scored[:top_k]:
        top_features.append(
            FeatureContribution(
                name=name,
                value=round(value, 4),
                importance=round(imp, 4),
                direction=_direction(value),
                label=_feature_label(name, value),
            )
        )

    # ── 3. Rank neighbours by attention ──────────────────────────────────────
    attn_pairs.sort(key=lambda t: t[1], reverse=True)

    top_neighbors: List[NeighborInfluence] = []
    for rank, (nid, attn) in enumerate(attn_pairs[:top_k], start=1):
        top_neighbors.append(
            NeighborInfluence(
                node_id=nid,
                attention=round(attn, 4),
                rank=rank,
                label=f"high-attention zone {nid}" if attn >= 0.3 else f"zone {nid}",
            )
        )

    # ── 4. Build prose ────────────────────────────────────────────────────────
    # Opening depends on risk level and the direction of the top feature
    top_direction = top_features[0].direction if top_features else "neutral"
    opening = _OPENING_TEMPLATES[level][top_direction].format(zone_tag=zone_tag)

    feature_clause  = _build_feature_clause(top_features)
    neighbor_clause = _build_neighbor_clause(top_neighbors)
    closing         = _CLOSING_BY_RISK[level]

    explanation = _assemble_prose(opening, feature_clause, neighbor_clause, closing)

    # ── 5. Structured sub-parts (for frontend partial rendering) ─────────────
    parts = {
        "opening":         opening,
        "feature_clause":  feature_clause,
        "neighbor_clause": neighbor_clause,
        "closing":         closing,
    }

    return ExplanationResult(
        zone_id=zone_id,
        risk_score=round(risk_score, 4),
        risk_level=level,
        top_features=top_features,
        top_neighbors=top_neighbors,
        explanation=explanation,
        explanation_parts=parts,
    )

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple
from geopy.distance import geodesic
import logging

logger = logging.getLogger(__name__)


# ── Decision thresholds (centralised — change here, affects everything) ─
_THRESHOLD_PASS:   float = 0.70  # weighted_score > this → PASS
_THRESHOLD_REVIEW: float = 0.40  # weighted_score > this → REVIEW  (else FAIL)


def weighted_adjudicate(
    agent_results: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Confidence-weighted consensus scoring over a list of agent result dicts.

    Each dict must contain:
      'score'       : float [0, 1]  — how "safe" / "approved" this agent rates the request
                      1.0 = fully safe (no anomaly), 0.0 = fully risky (hard block)
      'confidence'  : float (0, 1]  — how certain the agent is in its score
      'agent'       : str           — agent name (for explanation assembly)
      'reason'      : str           — single-line human-readable rationale

    Algorithm
    ---------
    weighted_score = Σ(scoreᵢ × confidenceᵢ) / Σ(confidenceᵢ)

    Agents with higher confidence pull the consensus toward their verdict.
    If ALL confidences are zero (degenerate case), arithmetic mean is used.

    Decision bands
    --------------
    weighted_score > _THRESHOLD_PASS   (0.70) → PASS
    weighted_score > _THRESHOLD_REVIEW (0.40) → REVIEW
    weighted_score ≤ _THRESHOLD_REVIEW        → FAIL

    Parameters
    ----------
    agent_results : sequence of agent dicts (at least one required)

    Returns
    -------
    dict:
      final_score          — float [0, 1], the consensus score
      decision             — "PASS" | "REVIEW" | "FAIL"
      combined_explanation — str, all agent rationales joined
      agent_breakdown      — list of per-agent score/confidence/contribution
      total_weight         — float, sum of confidences (diagnostic)
    """
    if not agent_results:
        raise ValueError("weighted_adjudicate requires at least one agent result.")

    numerator:   float = 0.0
    denominator: float = 0.0
    breakdown:   List[Dict[str, Any]] = []

    for r in agent_results:
        score = max(0.0, min(float(r.get("score", 0.5)), 1.0))
        conf  = max(0.0, min(float(r.get("confidence", 0.5)), 1.0))

        numerator   += score * conf
        denominator += conf

        breakdown.append({
            "agent":        r.get("agent", "UnknownAgent"),
            "score":        round(score, 4),
            "confidence":   round(conf, 4),
            "contribution": round(score * conf, 4),    # numerator share
            "reason":       r.get("reason", ""),
        })

    # ── Weighted mean with zero-denominator guard ────────────────────────
    if denominator > 0:
        final_score = round(numerator / denominator, 4)
    else:
        # All agents have zero confidence — fall back to arithmetic mean
        scores      = [r.get("score", 0.5) for r in agent_results]
        final_score = round(sum(scores) / len(scores), 4)

    # ── Decision band ────────────────────────────────────────────────────
    if final_score > _THRESHOLD_PASS:
        decision = "PASS"
    elif final_score > _THRESHOLD_REVIEW:
        decision = "REVIEW"
    else:
        decision = "FAIL"

    # ── Sort breakdown by contribution desc for readability ──────────────────
    breakdown.sort(key=lambda x: x["contribution"], reverse=True)

    # ── Explanation ─────────────────────────────────────────────────────────
    # Prefix each agent’s reason with their name, score, and confidence.
    parts = []
    for b in breakdown:
        icon = "[OK]" if b["score"] >= _THRESHOLD_PASS else (
               "[??]" if b["score"] >= _THRESHOLD_REVIEW else "[!!]")
        parts.append(
            f"{icon} {b['agent']} (α={b['score']:.2f}, c={b['confidence']:.2f}): {b['reason']}"
        )

    combine_verb = {
        "PASS":   "Consensus PASS",
        "REVIEW": "Consensus REVIEW — elevated uncertainty",
        "FAIL":   "Consensus FAIL",
    }[decision]

    combined_explanation = (
        f"{combine_verb} (weighted score: {final_score:.3f} / 1.000 | "
        f"threshold PASS>{_THRESHOLD_PASS} REVIEW>{_THRESHOLD_REVIEW}).\n"
        + "\n".join(parts)
    )

    return {
        "final_score":          final_score,
        "decision":            decision,
        "combined_explanation": combined_explanation,
        "agent_breakdown":      breakdown,
        "total_weight":         round(denominator, 4),
    }

class TelemetristAgent:
    @staticmethod
    def evaluate(
        worker_lat: float,
        worker_lon: float,
        center_lat: float,
        center_lon: float,
    ) -> dict:
        """
        GPS proximity check.
        Computes geodesic distance between the worker's reported position
        and the disruption event centre.

        Returns
        -------
        dict with keys: agent, status (PASS|FAIL), reason, confidence,
                        anomaly_score (0..1 — used by EnvironmentAgent)
        """
        try:
            distance_km = geodesic(
                (worker_lat, worker_lon),
                (center_lat, center_lon),
            ).km

            # Anomaly score grows linearly with distance up to 5 km cap.
            # 0 km → 0.0 (no anomaly)  |  ≥5 km → 1.0 (clear spoof)
            anomaly_score = round(min(distance_km / 5.0, 1.0), 4)

            if distance_km > 2.0:
                return {
                    "agent":         "TelemetristAgent",
                    "status":        "FAIL",
                    "reason":        f"Potential spoofing — distance {distance_km:.2f} km exceeds 2 km limit.",
                    # score: inverse of anomaly; spoof detected → near 0
                    "score":         round(1.0 - anomaly_score, 4),
                    "confidence":    0.95,
                    "anomaly_score": anomaly_score,
                    "distance_km":   round(distance_km, 3),
                }
            return {
                "agent":         "TelemetristAgent",
                "status":        "PASS",
                "reason":        f"Valid location — distance {distance_km:.2f} km within threshold.",
                # score: proximity score; close = safe = high score
                "score":         round(1.0 - anomaly_score, 4),
                "confidence":    0.98,
                "anomaly_score": anomaly_score,
                "distance_km":   round(distance_km, 3),
            }
        except Exception as exc:
            logger.error(f"TelemetristAgent error: {exc}")
            return {
                "agent":         "TelemetristAgent",
                "status":        "FAIL",
                "reason":        "Internal error calculating geodesic distance.",
                "score":         0.0,   # worst-case on error
                "confidence":    0.0,
                "anomaly_score": 1.0,
                "distance_km":   None,
            }


class EnvironmentAgent:
    """
    Cross-validates the GNN's structural risk signal against the
    Telemetrist's physical anomaly score using weighted fusion.

    Fusion model
    ------------
    Both inputs are normalised to [0, 1]:
      gnn_risk_score    — from the GNN decision engine prediction (HIGH→1.0)
      telemetrist_anomaly — the anomaly_score returned by TelemetristAgent

    Weighted fused score:
      fused = W_GNN * gnn + W_TELE * tele
      W_GNN  = 0.55  (graph-level structural risk carries more weight)
      W_TELE = 0.45  (physical proximity anomaly)

    Mismatch penalty:
      When the two inputs diverge significantly (|gnn - tele| > MISMATCH_THRESHOLD)
      we cannot be confident in either — apply an uncertainty penalty:
        fused = fused * (1 - MISMATCH_PENALTY * divergence)
      This pulls the score toward the middle, reflecting model disagreement.

    Regime thresholds:
      environment_risk_score ≥ HIGH_THRESHOLD   → HIGH   (strong risk)
      environment_risk_score ≥ MEDIUM_THRESHOLD  → MEDIUM (uncertain)
      environment_risk_score <  MEDIUM_THRESHOLD → LOW    (safe)
    """

    # ── Weights (must sum to 1.0) ──────────────────────────────────────────
    W_GNN:  float = 0.55
    W_TELE: float = 0.45

    # ── Mismatch / regime parameters ──────────────────────────────────────
    MISMATCH_THRESHOLD: float = 0.35   # divergence above this triggers penalty
    MISMATCH_PENALTY:   float = 0.20   # max fractional reduction in fused score
    HIGH_THRESHOLD:     float = 0.65
    MEDIUM_THRESHOLD:   float = 0.35

    @classmethod
    def evaluate(
        cls,
        gnn_risk_score: float,
        telemetrist_result: dict,
    ) -> dict:
        """
        Parameters
        ----------
        gnn_risk_score
            Scalar risk score from the GNN engine.  Should be the
            calibrated confidence value of the HIGH class [0, 1].
            If passing a prediction label, map: LOW→0.1, MEDIUM→0.5, HIGH→0.9.

        telemetrist_result
            The full dict returned by TelemetristAgent.evaluate().
            Must contain 'anomaly_score' [0, 1].

        Returns
        -------
        dict with keys:
          agent                  : str   — "EnvironmentAgent"
          status                 : str   — PASS | MODERATE | FAIL
          environment_risk_score : float — [0, 1] fused risk
          regime                 : str   — LOW | MEDIUM | HIGH
          confidence             : float — certainty in the output
          explanation            : str   — human-readable justification
          debug                  : dict  — raw intermediate values
        """
        try:
            # ── 1. Input normalisation ────────────────────────────────────────
            gnn  = max(0.0, min(float(gnn_risk_score), 1.0))
            tele = max(0.0, min(float(telemetrist_result.get("anomaly_score", 0.0)), 1.0))

            # ── 2. Weighted fusion ────────────────────────────────────────────
            fused: float = cls.W_GNN * gnn + cls.W_TELE * tele

            # ── 3. Mismatch / uncertainty penalty ────────────────────────────
            divergence    = abs(gnn - tele)
            mismatch_flag = divergence > cls.MISMATCH_THRESHOLD

            if mismatch_flag:
                # The two sensors disagree — reduce confidence proportionally.
                # divergence ∈ (0.35, 1.0] → penalty ∈ (0.0, 0.20]
                scaled_div = (divergence - cls.MISMATCH_THRESHOLD) / (1.0 - cls.MISMATCH_THRESHOLD)
                penalty    = cls.MISMATCH_PENALTY * scaled_div
                fused      = fused * (1.0 - penalty)

            fused = round(max(0.0, min(fused, 1.0)), 4)

            # ── 4. Regime classification ──────────────────────────────────────
            if fused >= cls.HIGH_THRESHOLD:
                regime = "HIGH"
                status = "FAIL"
            elif fused >= cls.MEDIUM_THRESHOLD:
                regime = "MEDIUM"
                status = "MODERATE"     # soft fail — escalate, not block
            else:
                regime = "LOW"
                status = "PASS"

            # ── 5. Confidence ─────────────────────────────────────────────────
            # High confidence when both signals *agree* (low divergence).
            # Minimum confidence 0.50 so MODERATE cases are never dismissed.
            confidence = round(max(0.50, 1.0 - divergence), 4)

            # ── 6. Dynamic explanation ────────────────────────────────────────
            explanation = cls._build_explanation(
                gnn=gnn, tele=tele, fused=fused,
                regime=regime, mismatch=mismatch_flag,
                divergence=divergence,
            )

            return {
                "agent":                 "EnvironmentAgent",
                "status":               status,
                "environment_risk_score": fused,
                "regime":               regime,
                "confidence":           confidence,
                "explanation":          explanation,
                "debug": {
                    "gnn_input":    round(gnn, 4),
                    "tele_input":   round(tele, 4),
                    "divergence":   round(divergence, 4),
                    "mismatch":     mismatch_flag,
                    "fused_raw":    round(cls.W_GNN * gnn + cls.W_TELE * tele, 4),
                    "fused_final":  fused,
                    "weights":      {"gnn": cls.W_GNN, "telemetrist": cls.W_TELE},
                },
            }

        except Exception as exc:
            logger.error(f"EnvironmentAgent error: {exc}")
            return {
                "agent":                 "EnvironmentAgent",
                "status":               "FAIL",
                "environment_risk_score": 1.0,   # worst-case on error
                "regime":               "HIGH",
                "confidence":           0.0,
                "explanation":          "Internal error during environment risk fusion.",
                "debug":                {},
            }

    # ── Internal ─────────────────────────────────────────────────────────────
    @staticmethod
    def _build_explanation(
        *,
        gnn: float,
        tele: float,
        fused: float,
        regime: str,
        mismatch: bool,
        divergence: float,
    ) -> str:
        """
        Constructs a human-readable explanation from the fusion parameters.
        No hardcoded strings — language is assembled from the input values.
        """
        gnn_desc  = "high" if gnn  >= 0.65 else "moderate" if gnn  >= 0.35 else "low"
        tele_desc = "high" if tele >= 0.65 else "moderate" if tele >= 0.35 else "low"

        if not mismatch:
            # Both sensors agree
            if regime == "HIGH":
                core = (
                    f"Both structural risk ({gnn_desc}, {gnn:.0%}) and "
                    f"physical anomaly ({tele_desc}, {tele:.0%}) signals are elevated — "
                    "strong environment risk confirmed."
                )
            elif regime == "MEDIUM":
                core = (
                    f"Moderate structural risk ({gnn_desc}, {gnn:.0%}) and "
                    f"physical anomaly ({tele_desc}, {tele:.0%}) — "
                    "conditions require monitoring."
                )
            else:
                core = (
                    f"Both structural risk ({gnn_desc}, {gnn:.0%}) and "
                    f"physical anomaly ({tele_desc}, {tele:.0%}) are low — "
                    "environment is stable."
                )
        else:
            # Signals disagree — surface uncertainty explicitly
            dominant = "GNN graph model" if gnn > tele else "physical telemetry"
            subdued  = "physical telemetry" if gnn > tele else "GNN graph model"
            core = (
                f"Signal mismatch detected (divergence {divergence:.0%}): "
                f"{dominant} indicates elevated risk while {subdued} shows lower concern. "
                f"Fused score ({fused:.0%}) reflects weighted consensus under uncertainty."
            )

        return f"[EnvironmentAgent | {regime}] {core}"


class EconomistAgent:
    @staticmethod
    async def evaluate(worker_id: str, payout_request: float, db: Any) -> dict:
        """
        Fetch last 7 days earnings from MongoDB.
        Compute average hourly income.
        If payout request > 200% of average → "FAIL: Anomaly"
        Else → "PASS"
        """
        try:
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            
            # Assuming 'earnings' collection exists. We aggregate hourly earnings
            cursor = db["earnings"].find({
                "worker_id": worker_id,
                "timestamp": {"$gte": seven_days_ago}
            })
            
            earnings = await cursor.to_list(length=100)
            
            # Mock if not found to allow smooth testing
            if not earnings:
                avg_hourly_income = 25.0  # Default mock average hourly income
            else:
                total_earnings = sum(float(e.get("amount", 0)) for e in earnings)
                hours_worked = sum(float(e.get("hours", 0)) for e in earnings)
                
                if hours_worked > 0:
                    avg_hourly_income = total_earnings / hours_worked
                else:
                    avg_hourly_income = 25.0
                    
            anomaly_threshold = avg_hourly_income * 2.0
            
            if payout_request > anomaly_threshold:
                return {
                    "agent":      "EconomistAgent",
                    "status":     "FAIL",
                    "reason":     f"Anomaly. Payout request {payout_request} exceeds 200% of avg hourly income {avg_hourly_income:.2f}.",
                    # score: how far over the threshold; 0 = extreme anomaly
                    "score":      round(max(0.0, 1.0 - (payout_request / max(anomaly_threshold, 1e-8))), 4),
                    "confidence": 0.90,
                }

            # Score: ratio of avg to payout (clipped at 1.0 for normal cases)
            # e.g. payout=100, avg=200 → score ≈ 1.0 (well within limits)
            #      payout=190, avg=200 → score ≈ 0.5 (approaching threshold)
            safety_ratio = avg_hourly_income / max(payout_request, 1e-8)
            return {
                "agent":      "EconomistAgent",
                "status":     "PASS",
                "reason":     f"Payout request {payout_request} is within acceptable limits (avg hourly: {avg_hourly_income:.2f}).",
                "score":      round(min(safety_ratio / 2.0, 1.0), 4),  # fully safe at ratio ≥2
                "confidence": 0.95,
            }
        except Exception as exc:
            logger.error(f"EconomistAgent error: {exc}")
            return {
                "agent":      "EconomistAgent",
                "status":     "FAIL",
                "reason":     "Internal Error checking earnings",
                "score":      0.0,
                "confidence": 0.0,
            }


class AdjudicatorAgent:
    """
    Final decision gate — weighted consensus scoring over all upstream agents.

    Replaces the binary PASS/FAIL gate with confidence-weighted scoring:
      •  Each agent contributes a score [0, 1] weighted by its confidence.
      •  Final score = Σ(scoreᵢ × confᵢ) / Σ(confᵢ)
      •  Three decision bands:
           PASS   (score > 0.70) — fully approved
           REVIEW (score > 0.40) — flag for human review
           FAIL   (score ≤ 0.40) — rejected

    Backward compatibility
    ----------------------
    The returned dict still contains 'status' mapped from the new decision
    and 'reason' for any code that consumes those keys.
    """

    # Map new decision labels to legacy status values consumed by claim_router
    _DECISION_TO_STATUS: Dict[str, str] = {
        "PASS":   "PASS",
        "REVIEW": "ESCALATE",   # REVIEW → soft escalate (not a hard block)
        "FAIL":   "FAIL",
    }

    @classmethod
    def evaluate(
        cls,
        telemetrist_result: dict,
        economist_result: dict,
        environment_result: Optional[dict] = None,
    ) -> dict:
        """
        Parameters
        ----------
        telemetrist_result  Output of TelemetristAgent.evaluate()
        economist_result    Output of EconomistAgent.evaluate()
        environment_result  Output of EnvironmentAgent.evaluate() (optional)

        Returns
        -------
        dict with keys:
          agent                — "AdjudicatorAgent"
          status               — "PASS" | "ESCALATE" | "FAIL"  (legacy key)
          decision             — "PASS" | "REVIEW"  | "FAIL"  (new key)
          final_score          — float [0, 1], the consensus score
          reason               — str, combined explanation
          confidence           — float, geometric mean of agent confidences
          gates                — dict, per-agent pass/fail for legacy consumers
          agent_breakdown      — list, per-agent scores and contributions
          combined_explanation — str, full multi-line explanation
        """
        try:
            # ── 1. Build agent payload for weighted_adjudicate ─────────────────
            # EnvironmentAgent returns environment_risk_score (risk = bad),
            # so we invert it to get a safety score for the consensus function.
            agents_payload: List[Dict[str, Any]] = [
                {
                    "agent":      "TelemetristAgent",
                    "score":      telemetrist_result.get("score", (
                                      1.0 if telemetrist_result.get("status") == "PASS" else 0.0
                                  )),
                    "confidence": telemetrist_result.get("confidence", 0.5),
                    "reason":     telemetrist_result.get("reason", ""),
                },
                {
                    "agent":      "EconomistAgent",
                    "score":      economist_result.get("score", (
                                      1.0 if economist_result.get("status") == "PASS" else 0.0
                                  )),
                    "confidence": economist_result.get("confidence", 0.5),
                    "reason":     economist_result.get("reason", ""),
                },
            ]

            if environment_result is not None:
                # EnvironmentAgent: risk score → safety score (invert)
                env_risk  = float(environment_result.get("environment_risk_score", 0.5))
                env_score = round(1.0 - env_risk, 4)
                agents_payload.append({
                    "agent":      "EnvironmentAgent",
                    "score":      env_score,
                    "confidence": environment_result.get("confidence", 0.5),
                    "reason":     environment_result.get("explanation", ""),
                })

            # ── 2. Weighted consensus ─────────────────────────────────────────
            consensus = weighted_adjudicate(agents_payload)

            decision    = consensus["decision"]
            final_score = consensus["final_score"]
            status      = cls._DECISION_TO_STATUS[decision]

            # ── 3. Legacy gate dict (kept for claim_router backward compat) ─────
            gates = {
                "telemetrist":  telemetrist_result.get("status"),
                "economist":    economist_result.get("status"),
                "environment":  environment_result.get("status") if environment_result else "N/A",
                "consensus":    decision,
            }

            # ── 4. Geometric-mean confidence (penalises low-confidence agents) ──
            confs = [p["confidence"] for p in agents_payload]
            geom_conf = round(
                math.prod(confs) ** (1.0 / max(len(confs), 1)), 4
            )

            return {
                "agent":                "AdjudicatorAgent",
                "status":               status,              # legacy key
                "decision":             decision,            # new key
                "final_score":          final_score,
                "reason":               consensus["combined_explanation"],
                "confidence":           geom_conf,
                "gates":                gates,
                "agent_breakdown":      consensus["agent_breakdown"],
                "combined_explanation": consensus["combined_explanation"],
                "total_weight":         consensus["total_weight"],
            }

        except Exception as exc:
            logger.error(f"AdjudicatorAgent error: {exc}", exc_info=True)
            return {
                "agent":      "AdjudicatorAgent",
                "status":     "FAIL",
                "decision":   "FAIL",
                "final_score": 0.0,
                "reason":     f"Internal error during adjudication: {exc}",
                "confidence": 0.0,
                "gates":      {},
                "agent_breakdown": [],
                "combined_explanation": "",
                "total_weight": 0.0,
            }

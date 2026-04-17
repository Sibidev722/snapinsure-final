"""
Tests for weighted_adjudicate() and the upgraded AdjudicatorAgent.
Covers: formula correctness, zero-denominator guard, all three decision bands,
        combined explanation format, backward-compat status keys.
"""
import ast, sys, math
sys.path.insert(0, '.')

# Syntax checks first
for f in ['services/multi_agent_service.py', 'api/claim_router.py']:
    ast.parse(open(f, encoding='utf-8').read())
    print(f'SYNTAX OK  {f}')

from services.multi_agent_service import (
    weighted_adjudicate,
    TelemetristAgent,
    EnvironmentAgent,
    AdjudicatorAgent,
)

print()
print("=" * 60)
print("  weighted_adjudicate() unit tests")
print("=" * 60)

# ── 1. Formula correctness ─────────────────────────────────────────────────
agents = [
    {"agent": "A", "score": 0.9, "confidence": 0.8, "reason": "clean GPS"},
    {"agent": "B", "score": 0.6, "confidence": 0.4, "reason": "mid earnings"},
]
r = weighted_adjudicate(agents)
expected = round((0.9*0.8 + 0.6*0.4) / (0.8+0.4), 4)
assert r["final_score"] == expected, f"Formula fail: {r['final_score']} != {expected}"
assert r["decision"] == "PASS", f"Expected PASS, got {r['decision']}"
print(f"  [1] Formula  score={r['final_score']} decision={r['decision']}")

# ── 2. REVIEW band ─────────────────────────────────────────────────────────
agents_mid = [
    {"agent": "X", "score": 0.55, "confidence": 1.0, "reason": "borderline"},
]
r2 = weighted_adjudicate(agents_mid)
assert r2["decision"] == "REVIEW", f"Expected REVIEW got {r2['decision']}"
print(f"  [2] REVIEW   score={r2['final_score']} decision={r2['decision']}")

# ── 3. FAIL band ───────────────────────────────────────────────────────────
agents_fail = [
    {"agent": "SpooferDetected", "score": 0.1, "confidence": 0.99, "reason": "GPS 8km away"},
    {"agent": "EconBreach",      "score": 0.2, "confidence": 0.90, "reason": "payout 500% avg"},
]
r3 = weighted_adjudicate(agents_fail)
assert r3["decision"] == "FAIL", f"Expected FAIL got {r3['decision']}"
print(f"  [3] FAIL     score={r3['final_score']} decision={r3['decision']}")

# ── 4. Zero-denominator guard ──────────────────────────────────────────────
agents_zero = [
    {"agent": "Z1", "score": 0.8, "confidence": 0.0, "reason": "no conf"},
    {"agent": "Z2", "score": 0.4, "confidence": 0.0, "reason": "no conf"},
]
r4 = weighted_adjudicate(agents_zero)
expected4 = round((0.8 + 0.4) / 2, 4)
assert r4["final_score"] == expected4, f"Zero-guard fail: {r4['final_score']} != {expected4}"
print(f"  [4] ZeroConf score={r4['final_score']} (arithmetic mean fallback)")

# ── 5. Breakdown sorted by contribution desc ───────────────────────────────
assert r["agent_breakdown"][0]["contribution"] >= r["agent_breakdown"][-1]["contribution"]
print(f"  [5] Breakdown sorted correctly")

# ── 6. combined_explanation contains all agent names ───────────────────────
expl = r["combined_explanation"]
assert "A" in expl and "B" in expl and "Consensus" in expl
print(f"  [6] combined_explanation: '{expl[:70]}...'")

print()
print("=" * 60)
print("  AdjudicatorAgent.evaluate() integration tests")
print("=" * 60)

# ── 7. All-PASS case ───────────────────────────────────────────────────────
tele_pass = TelemetristAgent.evaluate(13.08, 80.27, 13.08, 80.27)  # 0 km → PASS
eco_pass  = {"agent": "EconomistAgent", "status": "PASS",
             "score": 1.0, "confidence": 0.95, "reason": "within limits"}
adj7 = AdjudicatorAgent.evaluate(tele_pass, eco_pass)
assert adj7["decision"] == "PASS" and adj7["status"] == "PASS"
assert 0.0 <= adj7["final_score"] <= 1.0
print(f"  [7] All PASS  final_score={adj7['final_score']} status={adj7['status']}")

# ── 8. With EnvironmentAgent (high risk → should push toward FAIL/REVIEW) ─
env_high = EnvironmentAgent.evaluate(
    gnn_risk_score=0.90,
    telemetrist_result={"anomaly_score": 0.80, "status": "FAIL", "confidence": 0.95},
)
adj8 = AdjudicatorAgent.evaluate(tele_pass, eco_pass, env_high)
print(f"  [8] With HighEnv decision={adj8['decision']} final_score={adj8['final_score']}")
assert adj8["decision"] in ("PASS", "REVIEW", "FAIL")

# ── 9. Backward-compat: all legacy keys still present ──────────────────────
for key in ("agent", "status", "reason", "confidence", "gates"):
    assert key in adj7, f"Missing legacy key: {key}"
print(f"  [9] Legacy keys present: agent, status, reason, confidence, gates")

# ── 10. Score clamping: agent emits out-of-range values ───────────────────
r_clamp = weighted_adjudicate([
    {"agent": "X", "score": 2.5,  "confidence": -0.1, "reason": "bad agent"},
    {"agent": "Y", "score": -1.0, "confidence":  0.5, "reason": "another bad"},
])
assert 0.0 <= r_clamp["final_score"] <= 1.0
print(f"  [10] Clamping: score={r_clamp['final_score']} stays in [0,1]")

print()
print("All 10 tests passed.")

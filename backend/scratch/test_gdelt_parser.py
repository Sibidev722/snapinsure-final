"""
Comprehensive tests for gdelt_parser.parse_gdelt_event()
Covers: tone normalisation, EventCode taxonomy, confidence, batch, aggregation,
        all error/edge cases.
"""
import ast, sys, math
sys.path.insert(0, '.')

ast.parse(open('services/gdelt_parser.py', encoding='utf-8').read())
print('SYNTAX OK  services/gdelt_parser.py')

from services.gdelt_parser import (
    parse_gdelt_event,
    parse_gdelt_batch,
    aggregate_batch_score,
    _normalise_tone,
    _resolve_event_code,
)

print()
print("=" * 64)
print("  _normalise_tone() — sigmoid checkpoints")
print("=" * 64)
cases = [(-100, 0.993), (-50, 0.924), (0, 0.500), (50, 0.076), (100, 0.007)]
for tone, expected_approx in cases:
    result = _normalise_tone(tone)
    ok = abs(result - expected_approx) < 0.01
    print(f"  tone={tone:+4d}  → risk={result:.4f}  (expected ~{expected_approx})  {'OK' if ok else 'FAIL'}")
    assert ok, f"Sigmoid mismatch at tone={tone}"

print()
print("=" * 64)
print("  _resolve_event_code() — prefix hierarchy")
print("=" * 64)
code_tests = [
    ("145",  "protests_violently",        0.85),
    ("1451", "protests_violently",        0.85),   # longer → prefix to "145"
    ("14",   "protest",                   0.70),   # 2-digit root
    ("193",  "conduct_missile_attack",    0.92),
    ("ECS",  "economic_stress",           0.60),
    ("ECSFOO","economic_stress",          0.60),   # GKG prefix
    ("999",  "unknown_event",             0.20),   # unknown
    ("",     "unknown_event",             0.20),   # empty
]
for code, expected_type, expected_w in code_tests:
    etype, weight = _resolve_event_code(code)
    ok = (etype == expected_type) and (abs(weight - expected_w) < 1e-6)
    print(f"  code={code:<10} → type={etype:<30} weight={weight}  {'OK' if ok else f'FAIL got {etype},{weight}'}")
    assert ok

print()
print("=" * 64)
print("  parse_gdelt_event() — full pipeline")
print("=" * 64)

# 1. Both inputs available — protest code + negative tone
r = parse_gdelt_event(tone=-65.0, event_code="145")
assert 0.7 < r["disruption_score"] <= 1.0, f"Expected high score, got {r['disruption_score']}"
assert r["event_type"] == "protests_violently"
assert r["confidence"] == 0.90
assert r["error"] is None
print(f"  [1] protest + neg tone  score={r['disruption_score']}  conf={r['confidence']}  OK")

# 2. Positive tone + cooperative code → low disruption
r2 = parse_gdelt_event(tone=45.0, event_code="04")
assert r2["disruption_score"] < 0.25, f"Expected low score, got {r2['disruption_score']}"
assert r2["event_type"] == "consult"
print(f"  [2] consult + pos tone  score={r2['disruption_score']}  OK")

# 3. Missing tone — confidence penalty
r3 = parse_gdelt_event(tone=None, event_code="143")
assert r3["confidence"] == 0.55, f"Expected 0.55, got {r3['confidence']}"
assert r3["debug"]["tone_raw"] is None
print(f"  [3] missing tone        conf={r3['confidence']}  OK")

# 4. Missing event_code — confidence penalty
r4 = parse_gdelt_event(tone=-30.0, event_code=None)
assert r4["confidence"] == 0.65, f"Expected 0.65, got {r4['confidence']}"
print(f"  [4] missing event_code  conf={r4['confidence']}  OK")

# 5. Both missing — lowest confidence
r5 = parse_gdelt_event(tone=None, event_code=None)
assert r5["confidence"] == 0.20, f"Expected 0.20, got {r5['confidence']}"
assert r5["disruption_score"] == round(0.5*0.5 + 0.5*0.20, 4)
print(f"  [5] both missing        score={r5['disruption_score']}  conf={r5['confidence']}  OK")

# 6. GKG V2Tone string format (comma-delimited)
r6 = parse_gdelt_event(tone="-34.5,12.3,46.8,0,1,2,900", event_code="14")
assert abs(r6["debug"]["tone_raw"] - (-34.5)) < 0.01
print(f"  [6] GKG V2Tone string   tone_raw={r6['debug']['tone_raw']}  OK")

# 7. Invalid tone string → error field set, score still returned
r7 = parse_gdelt_event(tone="not_a_number", event_code="14")
assert r7["error"] is not None
assert 0.0 <= r7["disruption_score"] <= 1.0
print(f"  [7] invalid tone str    error='{r7['error'][:40]}...'  score still valid={r7['disruption_score']}  OK")

# 8. Out-of-range tone → clamped, no exception
r8 = parse_gdelt_event(tone=250.0, event_code="01")
assert 0.0 <= r8["disruption_score"] <= 1.0
print(f"  [8] out-of-range tone   score={r8['disruption_score']} (clamped)  OK")

# 9. Economic stress EventCode
r9 = parse_gdelt_event(tone=-20.0, event_code="ECS")
assert r9["event_type"] == "economic_stress"
print(f"  [9] ECS economic stress score={r9['disruption_score']}  type={r9['event_type']}  OK")

# 10. Integer event_code
r10 = parse_gdelt_event(tone=-10.0, event_code=193)
assert r10["event_type"] == "conduct_missile_attack"
print(f"  [10] int event_code=193  type={r10['event_type']}  OK")

# 11. Custom weights (70/30 tone-heavy)
r11 = parse_gdelt_event(tone=-80.0, event_code="01", tone_weight=0.70, event_weight=0.30)
r11_expected = round(0.70 * _normalise_tone(-80.0) + 0.30 * 0.05, 4)
assert abs(r11["disruption_score"] - r11_expected) < 1e-4, f"Weight fusion fail: {r11['disruption_score']} != {r11_expected}"
print(f"  [11] custom weights     score={r11['disruption_score']}  expected={r11_expected}  OK")

# 12. Invalid weights → auto-normalised
r12 = parse_gdelt_event(tone=0.0, event_code="14", tone_weight=0.0, event_weight=0.0)
assert 0.0 <= r12["disruption_score"] <= 1.0
print(f"  [12] zero weights       score={r12['disruption_score']} (normalised)  OK")

print()
print("=" * 64)
print("  parse_gdelt_batch() + aggregate_batch_score()")
print("=" * 64)

records = [
    {"tone": -70.0, "EventCode": "145"},   # violent protest
    {"tone": -40.0, "EventCode": "14"},    # protest
    {"tone":  10.0, "EventCode": "04"},    # diplomatic (low risk)
    {"tone": None,  "EventCode": "ECS"},   # economic stress, no tone
    {},                                     # completely empty record
]
batch = parse_gdelt_batch(records)
assert len(batch) == 5
assert all(0.0 <= r["disruption_score"] <= 1.0 for r in batch)
assert all(r["_index"] == i for i, r in enumerate(batch))
print(f"  [13] batch parse         records={len(batch)}  all scores in [0,1]  OK")

agg = aggregate_batch_score(batch)
assert 0.0 <= agg["aggregate_disruption_score"] <= 1.0
assert agg["total_records"] == 5
print(f"  [14] batch aggregate     agg_score={agg['aggregate_disruption_score']}  "
      f"dominant={agg['dominant_event_type']}  valid={agg['valid_records']}  OK")

# 15. Empty batch
agg_empty = aggregate_batch_score([])
assert agg_empty["aggregate_disruption_score"] == 0.0
assert agg_empty["dominant_event_type"] == "no_data"
print(f"  [15] empty batch         score={agg_empty['aggregate_disruption_score']}  OK")

print()
print("All 15 tests passed.")

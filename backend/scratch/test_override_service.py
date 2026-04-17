"""
Tests for override_service.apply_override() — runs without a real DB.
Uses a mock DB object that captures writes so we can assert them.
"""
import ast, sys, asyncio
sys.path.insert(0, '.')

# ── syntax checks ──────────────────────────────────────────────────────────
for f in ['services/override_service.py', 'api/override_router.py', 'main.py']:
    ast.parse(open(f, encoding='utf-8').read())
    print(f'SYNTAX OK  {f}')

from services.override_service import apply_override, get_overrides_for_claim


# ── Minimal mock DB ─────────────────────────────────────────────────────────
class MockCollection:
    def __init__(self):
        self.docs = []
        self.updated = []

    async def insert_one(self, doc):
        self.docs.append(doc)
        class R:
            inserted_id = "mock_override_id_abc123"
        return R()

    async def update_one(self, _filter, _update):
        self.updated.append((_filter, _update))

    def find(self, *a, **kw):
        return self

    def sort(self, *a, **kw):
        return self

    async def to_list(self, **kw):
        return self.docs


class MockDB:
    def __init__(self):
        self.claim_overrides = MockCollection()
        self.audit_trails    = MockCollection()

    def __getitem__(self, key):
        return getattr(self, key.replace("-", "_"), MockCollection())


# ── Test runner ─────────────────────────────────────────────────────────────
def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# Shared FAIL decision fixture
FAIL_DECISION = {
    "decision":             "FAIL",
    "status":               "FAIL",
    "final_score":          0.18,
    "confidence":           0.93,
    "combined_explanation": "GPS spoof + earnings anomaly detected.",
    "gates":                {"telemetrist": "FAIL", "economist": "FAIL"},
}

print()
print("=" * 62)
print("  apply_override() unit tests")
print("=" * 62)

db = MockDB()

# ── 1. Happy path: FAIL → override applied ──────────────────────────────────
result = run(apply_override(
    claim_id    = "CLM-2024-001",
    decision    = FAIL_DECISION,
    admin_input = {
        "admin_id":        "admin_ravi",
        "override_reason": "Worker verified on-site by supervisor; GPS glitch confirmed.",
    },
    db=db,
))
assert result.success, f"Expected success, got error: {result.error}"
assert result.original_decision  == "FAIL"
assert result.overridden_decision == "APPROVED_BY_OVERRIDE"
assert result.override_id         == "mock_override_id_abc123"
assert len(db.claim_overrides.docs) == 1
assert db.claim_overrides.docs[0]["record_type"] == "human_override"
assert len(db.audit_trails.updated) == 1   # audit_trail annotated
print(f"  [1] PASS:  override applied | id={result.override_id}")

# ── 2. Non-FAIL decision → hard reject ─────────────────────────────────────
result2 = run(apply_override(
    claim_id    = "CLM-2024-002",
    decision    = {"decision": "PASS", "status": "PASS"},
    admin_input = {
        "admin_id":        "admin_ravi",
        "override_reason": "Trying to override an already-approved claim.",
    },
    db=db,
))
assert not result2.success
assert "not eligible" in result2.error
print(f"  [2] PASS:  non-FAIL denied | error='{result2.error[:55]}...'")

# ── 3. Empty admin_id → validation error ───────────────────────────────────
result3 = run(apply_override(
    claim_id    = "CLM-2024-003",
    decision    = FAIL_DECISION,
    admin_input = {"admin_id": "", "override_reason": "GPS confirmed on site."},
    db=db,
))
assert not result3.success
assert "admin_id" in result3.error
print(f"  [3] PASS:  empty admin_id rejected | error='{result3.error}'")

# ── 4. Reason too short → validation error ─────────────────────────────────
result4 = run(apply_override(
    claim_id    = "CLM-2024-004",
    decision    = FAIL_DECISION,
    admin_input = {"admin_id": "admin_X", "override_reason": "OK"},
    db=db,
))
assert not result4.success
assert "override_reason" in result4.error
print(f"  [4] PASS:  short reason rejected | error='{result4.error[:60]}...'")

# ── 5. REJECTED label also eligible ────────────────────────────────────────
result5 = run(apply_override(
    claim_id    = "CLM-2024-005",
    decision    = {"decision": "REJECTED", "status": "FAIL", "final_score": 0.2},
    admin_input = {
        "admin_id":        "admin_priya",
        "override_reason": "Policy exception approved by regional manager on 17-Apr.",
    },
    db=db,
))
assert result5.success
assert result5.original_decision == "REJECTED"
print(f"  [5] PASS:  REJECTED also overridable | new={result5.overridden_decision}")

# ── 6. Override record schema has all required fields ───────────────────────
rec = db.claim_overrides.docs[0]
for key in ["record_type", "claim_id", "admin_id", "override_reason",
            "timestamp", "original_decision", "overridden_decision",
            "adjudication_snapshot", "source"]:
    assert key in rec, f"Missing key in override record: {key}"
print(f"  [6] PASS:  override record has all required fields")

# ── 7. Adjudication snapshot stores original score ─────────────────────────
snap = rec["adjudication_snapshot"]
assert snap["final_score"] == FAIL_DECISION["final_score"]
assert snap["confidence"]  == FAIL_DECISION["confidence"]
print(f"  [7] PASS:  adjudication_snapshot preserved | score={snap['final_score']}")

# ── 8. Timestamps are ISO-8601 UTC ─────────────────────────────────────────
from datetime import datetime, timezone
ts = datetime.fromisoformat(result.timestamp)
assert ts.tzinfo is not None, "Timestamp must be timezone-aware"
print(f"  [8] PASS:  timestamp is timezone-aware ISO-8601 | ts={result.timestamp}")

print()
print("All 8 tests passed.")

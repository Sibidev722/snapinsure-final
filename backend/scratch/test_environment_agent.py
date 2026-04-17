import ast, sys

# --- Syntax check ---
for f in ['services/multi_agent_service.py', 'api/claim_router.py']:
    ast.parse(open(f, encoding='utf-8').read())
    print(f'OK  {f}')

# --- Unit tests for EnvironmentAgent ---
sys.path.insert(0, '.')
from services.multi_agent_service import EnvironmentAgent, TelemetristAgent, AdjudicatorAgent

def run(label, gnn, tele_anomaly):
    tele_status = 'PASS' if tele_anomaly < 0.5 else 'FAIL'
    tele = {'anomaly_score': tele_anomaly, 'status': tele_status, 'confidence': 0.95}
    r = EnvironmentAgent.evaluate(gnn, tele)
    score   = r['environment_risk_score']
    regime  = r['regime']
    mm      = r['debug']['mismatch']
    expl    = r['explanation']
    print(f'  [{label}] gnn={gnn} tele={tele_anomaly} -> score={score} regime={regime} mismatch={mm}')
    print(f'           {expl}')
    return r

print()
# 1. Both HIGH -> strong risk -> FAIL
r = run('BOTH HIGH    ', gnn=0.85, tele_anomaly=0.80)
assert r['regime'] == 'HIGH' and r['status'] == 'FAIL', 'Both-high case must be FAIL/HIGH'

# 2. Both LOW -> stable -> PASS  
r = run('BOTH LOW     ', gnn=0.10, tele_anomaly=0.05)
assert r['regime'] == 'LOW' and r['status'] == 'PASS', 'Both-low case must be PASS/LOW'

# 3. Mismatch: GNN high, telemetry low
r = run('MISMATCH H/L ', gnn=0.90, tele_anomaly=0.05)
assert r['debug']['mismatch'] is True, 'Divergence 0.85 must trigger mismatch'

# 4. Mismatch: GNN low, telemetry high
r = run('MISMATCH L/H ', gnn=0.05, tele_anomaly=0.90)
assert r['debug']['mismatch'] is True, 'Divergence 0.85 must trigger mismatch'

# 5. Edge: out-of-range inputs clamped to [0,1]
r_clamp = EnvironmentAgent.evaluate(2.5, {'anomaly_score': -0.3, 'status': 'PASS', 'confidence': 0.9})
score_ok = 0.0 <= r_clamp['environment_risk_score'] <= 1.0
print(f'  [CLAMP] score={r_clamp["environment_risk_score"]} clamped_correctly={score_ok}')
assert score_ok, 'Out-of-range inputs must be clamped to [0,1]'

# 6. AdjudicatorAgent 3-way consensus with env result
tele3 = TelemetristAgent.evaluate(13.08, 80.27, 13.08, 80.27)  # same point -> PASS, anomaly=0
eco3  = {'agent': 'EconomistAgent', 'status': 'PASS', 'confidence': 0.95}
adj3  = AdjudicatorAgent.evaluate(tele3, eco3, r_clamp)
status3 = adj3['status']
gates3  = adj3['gates']
conf3   = adj3['confidence']
print(f'  [ADJUDICATOR] status={status3} conf={conf3} gates={gates3}')
assert 0.0 <= conf3 <= 1.0, 'Confidence must be in [0,1]'

print()
print('All tests passed.')

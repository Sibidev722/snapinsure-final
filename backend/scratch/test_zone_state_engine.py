import os, sys
os.environ.setdefault('MONGO_URI', 'mongodb+srv://sibidev722:Sibi123@cluster0.tb47qsu.mongodb.net/?appName=Cluster0')
sys.path.insert(0, '.')

# Verify main.py compiles cleanly
import ast
with open('main.py', encoding='utf-8') as f:
    src = f.read()
try:
    ast.parse(src)
    print('main.py: AST OK')
except SyntaxError as e:
    print(f'main.py SYNTAX ERROR: {e}')
    sys.exit(1)

# Test ZoneStateEngine decision logic
from services.zone_state_engine import ZoneStateEngine
engine = ZoneStateEngine()

engine.update_weather_score('Z1', 'heavy', 12.5, 'Thunderstorm', 'openweathermap')
engine.update_weather_score('Z5', 'none',  0.0,  'Clear',        'open-meteo')
engine.update_traffic_score('Z1', 65.0, 12.0)
engine.update_traffic_score('Z5', 10.0,  2.0)
engine.update_disruption_score('Z3', 'strike', 'high', 0.88)
engine.update_demand_score('Z7', 45.0, 100.0)

results = {}
for zid in ['Z1', 'Z3', 'Z5', 'Z7']:
    d = engine.compute_zone_state(zid)
    results[zid] = d['state']
    print(f"  {zid}: {d['state']:6s} | {d['reason'][:65]}")

# Verify expected states
assert results['Z1'] == 'RED',    f"Z1 should be RED (heavy rain + 65% traffic), got {results['Z1']}"
assert results['Z3'] == 'RED',    f"Z3 should be RED (strike detected), got {results['Z3']}"
assert results['Z5'] == 'GREEN',  f"Z5 should be GREEN (clear + low traffic), got {results['Z5']}"
assert results['Z7'] == 'YELLOW', f"Z7 should be YELLOW (55% demand drop), got {results['Z7']}"

print()
print('All assertions passed. ZoneStateEngine decision logic: PASS')

# Verify all services import
modules = [
    'services.zone_state_engine',
    'services.weather_ingestion_service',
    'services.traffic_ingestion_service',
    'services.demand_ingestion_service',
    'workers.zone_state_worker',
    'api.zone_state_router',
]
import importlib
for m in modules:
    importlib.import_module(m)
    print(f'  IMPORT OK: {m}')

print()
print('ALL CHECKS PASSED')

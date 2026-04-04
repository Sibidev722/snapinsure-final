import sys
sys.path.insert(0, '.')

from services.income_os_service import income_os
from api.income_os_router import router

print('Income OS imports: OK')
z = income_os.zone_scores()
print(f'Zone scores: {len(z)} zones')
f = income_os.forecast('ZOM-1001', 'Z5')
print(f'Forecast: 1h={f["next_1_hour_income"]} shift={f["next_shift_income"]} conf={f["confidence_score"]}')
s = income_os.scenario('ZOM-1001', 'Z5')
print(f'Scenario: stay={s["stay"]["income_per_hour"]} move={s["move"]["income_per_hour"]} best={s["best_option"]}')
sg = income_os.suggestion('ZOM-1001', 'Z5')
print(f'Suggestion priority={sg["priority"]} action={sg["action_type"]}')
g = income_os.set_guarantee('ZOM-1001', 800.0)
print(f'Guarantee: premium={g["premium"]}')
print('ALL CHECKS PASSED')

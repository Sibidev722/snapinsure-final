# 🚀 SnapInsure: Demo Feature Documentation

This document outlines the three advanced intelligence modules of the SnapInsure platform. These features are designed to provide gig workers with "Income Certainty" in an unpredictable disruption economy.

---

## 🌓 1. Shift-Based Income Guarantee
**Goal**: Protects a worker's total earnings for a specific time window.

### 🛠️ Technical Logic
- **Definition**: Each worker is assigned a `SHIFTS_CONFIG` (Morning, Lunch, Evening, Night) with a target `expected_income` (e.g., ₹800).
- **Tracking**: The system tracks `current_earnings` in real-time as the worker moves across the city map.
- **Trigger**:
    - **Condition**: Worker's `zone_state == "RED"` (Severe Disruption).
    - **Logic**: If `current_earnings < expected_income`, the **Unified Payout Engine** calculates the shortfall.
- **Payout**:
    - **Amount**: `expected_income - current_earnings`.
    - **Display**: Labeled as **"Shift Guarantee"** in the transaction history.

> [!TIP]
> **Demo Script**: "Even if a worker is physically blocked from completing orders for 2 hours, SnapInsure ensures their shift target is met by auto-depositing the shortfall."

---

## 📉 2. Demand-Collapse Protection
**Goal**: Parametric protection against a sudden plunge in order volume (order-drought).

### 🛠️ Technical Logic
- **Baseline**: Each zone has a `baseline_orders` value (e.g., 250 orders/min).
- **Detection**: The simulation engine monitors `orders_per_minute`.
- **Trigger**:
    - **Condition**: `current_orders < baseline_orders * 0.8` (20% drop).
    - **Logic**: Calculates `order_loss` and translates it into a financial loss per missed order.
- **Payout**: 
    - **Formula**: `max(2, missed_orders) * AVG_ORDER_VALUE (₹80)`.
    - **Display**: Labeled as **"Demand Collapse"** in the live feed.

> [!IMPORTANT]
> This is a **Zero-Claim** payout. The worker does not need to report the lull; the system detects the platform-wide order drop and pays out instantly.

---

## 🧠 3. AI Zone Advisor
**Goal**: Real-time optimization to help workers "Stay vs. Move" for maximum profit.

### 🛠️ Technical Logic
- **Location**: API endpoint `GET /ai/suggest?worker_id=xxx`.
- **Scoring Algorithm**: A **Composite Score** is calculated for every zone (Z1–Z9):
    - **Income Potential**: `Demand Score * (1 - Risk * 0.5)`.
    - **Risk Penalty**: `RED` zones get a `-1.0` penalty, effectively excluding them.
    - **Risk Pool Bonus**: Zones with **5+ active workers** get a priority boost, as they share the risk.
- **Output**:
    - **Recommended**: The zone with the highest composite score.
    - **Avoid**: Any zone currently in a `RED` state.

### 🖥️ UI Visualization
- **Advisor Panel**: Located in the **Mission Control** or **Income OS** sidebar.
- **Live Advice**: Dynamically updates descriptions based on city risk (e.g., *"Heavy rain in Z4. Move to Z7 for better liquidity."*)

---

## 🛠️ How to Trigger via Backend
You can manually trigger these states to show the system's reaction:
1.  **Rain/Traffic**: `POST /sim/trigger` with `{"event_type": "rain"}` or `{"event_type": "traffic"}`.
2.  **Demand Collapse**: `POST /sim/trigger` with `{"event_type": "demand"}`.
3.  **Check Suggestion**: `GET /ai/suggest` to see the AI Advisor's live ranking change.

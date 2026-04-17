# 🛡️ SnapInsure: The Zero-Claim Platform for Gig Workers

**Instant Income Protection Powered by AI Risk Graphs & Real-Time Disruption Monitoring.**

SnapInsure is a high-fidelity fintech platform designed to eliminate income volatility for gig workers (Zomato, Swiggy, Uber, etc.). Unlike traditional insurance, SnapInsure uses **Parametric Triggers**—when a city disruption (rain, traffic, or strike) occurs, workers are compensated **instantly** without ever filing a claim.

---

## ✨ Features that WOW
- **🚀 Zero-Claim Payouts**: Real-time detection of city-wide disruptions triggers instant payouts to worker wallets.
- **🧠 AI Zone Advisor**: A live recommendation engine that ranks city zones based on Demand, Risk, and Pool status to help workers earn more.
- **🌓 Shift-Based Income Guarantee**: Automates "shortfall" compensation if a worker's shift target isn't met due to area blocks.
- **📡 Live City Graph**: A `NetworkX`-powered backend that simulates city-wide disruptions and calculates time loss for every worker.
- **🗺️ Interactive Mission Control**: A premium Mapbox-powered dashboard with real-time GPS telemetry and live event feeds.

---

## 🛠️ Technical Stack

- **Backend**: FastAPI (Python 3.10+) — Hosted on **Render**
- **Frontend**: React 19 + Tailwind CSS + Framer Motion — Hosted on **Vercel**
- **Real-Time**: WebSockets for sub-second city updates.
- **Database**: MongoDB Atlas for verified worker stats.
- **Maps**: Mapbox GL JS for interactive telemetry.

---

## 🚀 One-Click Deployment

### 1. Backend (Render)
1.  Connect your repo to **Render**.
2.  Create a new **Web Service**.
3.  Set the **Root Directory** to `backend`.
4.  Add these **Environment Variables**:
    - `MONGO_URI`: Your MongoDB Atlas connection string.
    - `SECRET_KEY`: A random string for JWT auth.
5.  Render will auto-deploy using the `runtime.txt` and `requirements.txt`.

### Database (MongoDB Atlas)
- Pre-loaded with demo users.
- Live active session & fraud tracking.

## ⚙️ How It Works (The 3 Zones)
1. 🟢 **GREEN ZONE:** Normal operations. Optimal route available.
2. 🟡 **YELLOW ZONE:** Delayed. Alternative routes forced due to traffic/strikes causing inefficiency. (Calculates Time Loss = New Route - Optimal Route).
3. 🔴 **RED ZONE:** Blocked. Route infeasible due to floods, severe strikes. Instantly triggers full Peak Income Compensation.

## 🌍 Hackathon Deployment Instructions (Manual Steps)
If Auto-Deploy fails due to Branch Protection rules, follow these steps to go live instantly:

1. **GitHub Merge:** Merge the `deployment-ready` branch into `main` (requires owner approval).
2. **Frontend Deployment:** Vercel is connected. Wait 60s for the Build (`npm run build`). Add the `VITE_BACKEND_URL=https://snapinsure.onrender.com` Environment Variable.
3. **Backend Deployment:** Render is connected via the `render.yaml` Blueprint. Or just deploy `backend` folder as Web Service. Ensure `MONGODB_URL` is set to an Atlas Cluster.

---
Built for the Guidewire Hackathon.

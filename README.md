<div align="center">

# 🚀 SnapInsure
**Instant Income Protection for Gig Workers — Powered by AI & Live Risk Graphs**

[![Deployed on Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fkamalesh2602%2FGuidewire)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/kamalesh2602/Guidewire)

</div>

## 🎯 The Pitch
SnapInsure is a zero-claim, AI-powered parametric insurance system that uses a live graph neural network to detect disruptions and automatically compensate gig workers in real time. We protect income, not just assets.

## 🌟 Demo Credentials
Access the live platform using the following verified worker profiles:

| Phone Number | Platform | City | Role |
|--------------|----------|------|------|
| **`9876543210`** | Swiggy | Chennai | Primary Demo Account |
| **`9876543211`** | Zomato | Bangalore | Fallback Account |
| **`9876543212`** | Zepto | Hyderabad | Testing Account |

> **Note:** Demo mode is active. Entering a Red Zone will *always* trigger an automated payout between ₹100–₹200 to demonstrate the engine.

## 🛠️ System Architecture

### Frontend (React + Vite + TailwindCSS 4)
- **Deployment:** Vercel (`src/`, `components/`)
- **Real-Time Data:** WebSockets connected to backend Graph simulation.
- **Mapping:** Mapbox GL for live worker telemetry.

### Backend (FastAPI + Python 3.12)
- **Deployment:** Render (Web Service based on `main.py`)
- **Simulation Engine:** `services/simulation_service.py` runs a ticker to simulate city disruptions.
- **Graph Neural Network:** Uses `NetworkX` to evaluate alternative routes and measure time loss.
- **Payout Engine:** `services/unified_payout_engine.py` guarantees automated compensation calculating expected income vs exact disruption severity.

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

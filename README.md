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

### 2. Frontend (Vercel)
1.  Connect your repo to **Vercel**.
2.  Set the **Root Directory** to `frontend`.
3.  Add these **Environment Variables**:
    - `VITE_BACKEND_URL`: Your Render backend URL (e.g., `https://snapinsure-api.onrender.com`).
    - `VITE_MAPBOX_TOKEN`: Your Mapbox public access token.
4.  Vercel will auto-build and deploy your project.

---

## 🏁 Quick Start (Local)

### 1. Backend
```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### 2. Frontend
```powershell
cd frontend
npm install
npm run dev
```

---

## 🌟 Demo Guide
Use these pre-loaded accounts to explore the platform:

<<<<<<< HEAD
| Role | Phone Number | Platform | City |Reg_no
| :--- | :--- | :--- | :--- |
| **Primary Demo** | `9876543210` | Swiggy | Chennai |SWG123
| **Testing** | `9876543211` | Zomato | Bangalore |ZOM123
=======
| Role | Phone Number | Platform | City |
| :--- | :--- | :--- | :--- |
| **Primary Demo** | `9876543210` | Swiggy | Chennai |
| **Testing** | `9876543211` | Zomato | Bangalore |
>>>>>>> e66175c (Final system integration: GNN, ESG, agents, UI fixes, parametric engine)

> [!TIP]
> **To showcase the Payout Engine**: Go to the **City Map** tab in the dashboard and use the **Manual Trigger** buttons (Rain/Traffic). Watch the live notifications and wallet balance update instantly as the "Zero-Claim" engine fires!

---

Built for the **Guidewire Hackathon**.  
*Ensuring the backbone of our economy stays protected, one tick at a time.*

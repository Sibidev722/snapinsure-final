import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Login from './components/Login'
import Dashboard from './components/Dashboard'
import CityMap from './components/CityMap'
import AnalyticsDashboard from './components/AnalyticsDashboard'
import WalletView from './components/WalletView'
import IncomeOS from './components/IncomeOS'
import { Shield, MapPin, BarChart3, Wallet, User, LogOut, TerminalSquare, Zap, Brain } from 'lucide-react'

// ── Debug Overlay ────────────────────────────────────────────────────────────
const DeveloperDebugOverlay = ({ cityState }) => {
  const [isOpen, setIsOpen] = useState(false);
  if (!cityState) return null;
  const zones = cityState.analytics;
  const recentPayout = cityState.analytics?.recent_payouts?.[0];

  return (
    <div className="fixed bottom-4 right-4 z-50">
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            className="mb-2 glass bg-[#0B0F14]/95 border border-brand/30 rounded-2xl p-4 w-96 shadow-glow-brand flex flex-col gap-3 font-mono text-xs"
          >
            <div className="flex items-center justify-between border-b border-white/10 pb-2">
              <span className="text-brand font-bold flex items-center gap-1.5">
                <TerminalSquare className="w-3.5 h-3.5"/> Orchestrator Debug Panel
              </span>
              <button onClick={() => setIsOpen(false)} className="text-slate-400 hover:text-white text-base">✕</button>
            </div>

            {/* Zone Distribution */}
            <div className="space-y-1">
              <p className="text-[10px] uppercase tracking-widest text-slate-500 mb-2">Zone Distribution</p>
              <div className="grid grid-cols-3 gap-2">
                <div className="bg-safe/10 border border-safe/20 rounded-lg p-2 text-center">
                  <p className="text-lg font-black text-safe">{zones?.green_zones ?? 0}</p>
                  <p className="text-[9px] text-safe/60 uppercase">SECURE</p>
                </div>
                <div className="bg-warn/10 border border-warn/20 rounded-lg p-2 text-center">
                  <p className="text-lg font-black text-warn">{zones?.yellow_zones ?? 0}</p>
                  <p className="text-[9px] text-warn/60 uppercase">DELAYED</p>
                </div>
                <div className="bg-danger/10 border border-danger/20 rounded-lg p-2 text-center">
                  <p className="text-lg font-black text-danger">{zones?.red_zones ?? 0}</p>
                  <p className="text-[9px] text-danger/60 uppercase">BLOCKED</p>
                </div>
              </div>
            </div>

            {/* Engine Metrics */}
            <div className="space-y-1.5 border-t border-white/10 pt-2">
              <p className="text-[10px] uppercase tracking-widest text-slate-500 mb-2">Engine Metrics</p>
              {[
                { label: 'Tick Count', value: zones?.tick ?? 0, color: 'text-safe' },
                { label: 'Active Disruptions', value: zones?.active_disruptions ?? 0, color: 'text-warn' },
                { label: 'Workers in RED', value: zones?.workers_in_red ?? 0, color: 'text-danger' },
                { label: 'Total Payout Today', value: `₹${(zones?.total_payout_today ?? 0).toFixed(0)}`, color: 'text-safe' },
                { label: 'PoW Fraud Engine', value: 'DEMO BYPASS', color: 'text-brand' },
              ].map(r => (
                <div key={r.label} className="flex justify-between text-slate-300">
                  <span>{r.label}:</span>
                  <span className={r.color + ' font-bold'}>{r.value}</span>
                </div>
              ))}
            </div>

            {/* Last Payout Breakdown */}
            {recentPayout && (
              <div className="border-t border-white/10 pt-2 space-y-1">
                <p className="text-[10px] uppercase tracking-widest text-slate-500 mb-2">Last Payout Breakdown</p>
                <div className="bg-safe/5 border border-safe/20 rounded-lg p-3 space-y-1">
                  <div className="flex justify-between text-safe"><span>Amount:</span><span className="font-black">₹{recentPayout.amount}</span></div>
                  <div className="flex justify-between text-slate-300"><span>Type:</span><span>{recentPayout.reason}</span></div>
                  <div className="text-brand text-[10px] mt-1 leading-relaxed">{recentPayout.calculation_details}</div>
                  <div className="flex justify-between text-slate-400 text-[10px]"><span>Source:</span><span>{recentPayout.pool_used ? '🏦 Risk Pool' : '⚡ System Reserve'}</span></div>
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
      <button
        onClick={() => setIsOpen(o => !o)}
        className={`w-10 h-10 rounded-full glass border flex items-center justify-center transition-all shadow-xl backdrop-blur-md ${
          isOpen ? 'border-brand/50 text-brand bg-brand/10' : 'border-white/10 text-slate-400 hover:text-brand hover:border-brand/30'
        }`}
      >
        <TerminalSquare className="w-4 h-4" />
      </button>
    </div>
  )
}

const WS_URL = import.meta.env.VITE_BACKEND_URL ? import.meta.env.VITE_BACKEND_URL.replace(/^http/, 'ws') + '/ws/city' : 'ws://localhost:8000/ws/city'

export default function App() {
  const [user, setUser]           = useState(null)
  const [platform, setPlatform]   = useState(null)
  const [activeTab, setActiveTab] = useState('dashboard')
  const [cityState, setCityState] = useState(null)
  const [wsConnected, setWsConnected] = useState(false)
  // Live payout queue — real-time NOTIFICATION messages get pushed here immediately
  const [livePayouts, setLivePayouts] = useState([])

  const wsRef             = useRef(null)
  const reconnectTimerRef = useRef(null)
  const seenNotifIds      = useRef(new Set())

  const handleLogin  = (u, p) => { setUser(u); setPlatform(p) }
  const handleLogout = () => {
    setUser(null); setPlatform(null)
    localStorage.removeItem('snapinsure_token')
  }

  const connectWs = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return
    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      setWsConnected(true)
      clearTimeout(reconnectTimerRef.current)
    }
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.type === 'city_update') {
          setCityState(data)
        } else if (data.type === 'NOTIFICATION' && data.payload?.type === 'PAYOUT') {
          // Instant real-time payout event — deduplicate by backend UUID
          const p = data.payload
          const pid = p.id || `${p.timestamp}-${p.amount}`
          if (!seenNotifIds.current.has(pid)) {
            seenNotifIds.current.add(pid)
            setLivePayouts(prev => [p, ...prev].slice(0, 20))
          }
        }
      } catch (_) {}
    }
    ws.onerror = () => setWsConnected(false)
    ws.onclose = () => {
      setWsConnected(false)
      reconnectTimerRef.current = setTimeout(connectWs, 3000)
    }
  }, [])

  useEffect(() => {
    connectWs()
    return () => { wsRef.current?.close(); clearTimeout(reconnectTimerRef.current) }
  }, [connectWs])

  if (!user) return <Login onLogin={handleLogin} />

  const TABS = [
    { id: 'dashboard', label: 'My Dashboard', icon: <User className="w-4 h-4"/> },
    { id: 'income',    label: 'Income OS',    icon: <Brain className="w-4 h-4"/>, badge: 'AI' },
    { id: 'map',       label: 'City Map',      icon: <MapPin className="w-4 h-4"/> },
    { id: 'analytics', label: 'Analytics',     icon: <BarChart3 className="w-4 h-4"/> },
    { id: 'wallet',    label: 'Wallet',         icon: <Wallet className="w-4 h-4"/> },
  ]

  return (
    <div className="min-h-screen bg-surface bg-gradient-mesh flex flex-col relative overflow-x-hidden">
      {/* ── Navbar ─────────────────────────────────────────── */}
      <nav className="sticky top-0 z-40 glass border-b border-white/5 py-3 px-6 md:px-12 flex items-center justify-between shadow-md">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-brand/10 border border-brand/20 flex items-center justify-center shadow-glow-brand">
            <Shield className="w-4 h-4 text-brand" />
          </div>
          <div>
            <h1 className="text-lg font-black text-white tracking-tight leading-none">Snap<span className="text-brand">Insure</span></h1>
            <p className="text-[9px] uppercase font-bold text-slate-500 tracking-widest flex items-center gap-1">
              <span className={`w-1.5 h-1.5 rounded-full ${wsConnected ? 'bg-safe animate-pulse' : 'bg-danger'}`} />
              {wsConnected ? 'Live · Real-time' : 'Reconnecting...'}
            </p>
          </div>
        </div>

        <div className="flex gap-1.5">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 border rounded-xl text-sm font-semibold transition-all relative ${
                activeTab === tab.id
                  ? 'bg-brand/10 text-brand border-brand/30 shadow-glow-brand'
                  : 'text-slate-400 hover:bg-white/5 border-transparent hover:border-white/10'
              }`}
            >
              {tab.icon}
              <span className="hidden md:inline">{tab.label}</span>
              {tab.badge && (
                <span className="hidden md:inline text-[8px] font-black bg-violet-500/30 text-violet-300 border border-violet-500/40 px-1.5 py-0 rounded-full ml-0.5">
                  {tab.badge}
                </span>
              )}
            </button>
          ))}
          <button onClick={handleLogout} className="ml-1 flex items-center justify-center px-3 py-2 rounded-xl text-slate-500 hover:text-danger hover:bg-danger/10 transition-colors">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </nav>

      {/* ── Content ──────────────────────────────────────────── */}
      <main className="flex-1 w-full max-w-7xl mx-auto p-4 md:p-8 flex flex-col relative">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.25 }}
            className="w-full flex-1 flex flex-col"
          >
            {activeTab === 'dashboard'  && <Dashboard cityState={cityState} user={user} platform={platform} livePayouts={livePayouts} />}
            {activeTab === 'income'     && <IncomeOS cityState={cityState} user={user} />}
            {activeTab === 'map'        && <CityMap cityState={cityState} user={user} />}
            {activeTab === 'analytics'  && <AnalyticsDashboard cityState={cityState} user={user} />}
            {activeTab === 'wallet'     && <WalletView cityState={cityState} user={user} />}
          </motion.div>
        </AnimatePresence>
      </main>

      <DeveloperDebugOverlay cityState={cityState} />
    </div>
  )
}

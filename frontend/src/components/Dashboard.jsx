import { useState, useEffect, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Shield, CloudRain, Car, Megaphone, Zap, TrendingUp,
  RefreshCw, CheckCircle, AlertTriangle, XCircle,
  ArrowUpRight, Clock, Activity, BarChart3, Wallet,
  User, Users, MapPin, LogOut, Bell, Info, Sparkles, Navigation
} from 'lucide-react'
import { RadialBarChart, RadialBar, PolarAngleAxis, ResponsiveContainer, AreaChart, Area, Tooltip, XAxis } from 'recharts'
import Map, { Marker, NavigationControl, Source, Layer } from 'react-map-gl/mapbox'
import 'mapbox-gl/dist/mapbox-gl.css'
import { useSimulationStore } from '../store/useSimulationStore'

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || ''
const SIM_API = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'
const GIG_API = `${SIM_API}/gig`

const ZONE_COLORS  = { GREEN: '#10b981', YELLOW: '#f59e0b', RED: '#ef4444' }
const ZONE_MAP = {
  GREEN:  { label: 'SAFE',    emoji: '🟢', textColor: 'text-safe',   borderColor: 'border-safe',   bgColor: 'bg-safe/10',   glowClass: 'zone-ring-green',  },
  YELLOW: { label: 'DELAYED', emoji: '🟡', textColor: 'text-warn',   borderColor: 'border-warn',   bgColor: 'bg-warn/10',   glowClass: 'zone-ring-yellow', },
  RED:    { label: 'BLOCKED', emoji: '🔴', textColor: 'text-danger', borderColor: 'border-danger', bgColor: 'bg-danger/10', glowClass: 'zone-ring-red',    },
}
const SIM_SCENARIOS = [
  { id: 'rain',    label: 'Heavy Rain',    icon: '🌧️', zone: 'RED',    risk: 0.91, payout: 150 },
  { id: 'traffic', label: 'Traffic Delay', icon: '🚧', zone: 'YELLOW', risk: 0.62, payout: 80 },
  { id: 'strike',  label: 'Strike',        icon: '📢', zone: 'RED',    risk: 0.88, payout: 150 },
  { id: 'demand',  label: 'Demand Drop',   icon: '📉', zone: 'RED',    risk: 0.95, payout: 25000 },
]

function LiveDot({ color = 'bg-safe' }) {
  return (
    <span className="relative flex h-2.5 w-2.5">
      <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${color} opacity-60`} />
      <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${color}`} />
    </span>
  )
}

function ZoneOrb({ zone, riskScore, isScanning, stats }) {
  const z = ZONE_MAP[zone] || ZONE_MAP.GREEN
  
  // Calculate if demand is collapsed
  const isDemandCollapsed = stats && (stats.ordersPerMin < stats.baselineOrders * 0.6 || stats.activeRes < 15);
  
  return (
    <div className="flex flex-col items-center justify-center gap-4">
      <div className="relative">
        <motion.div
          className={`w-36 h-36 rounded-full border-4 ${z.borderColor} ${z.bgColor} flex flex-col items-center justify-center ${z.glowClass} ${isDemandCollapsed ? 'animate-pulse' : ''}`}
          animate={{ scale: zone === 'RED' ? [1, 1.02, 1] : 1 }}
          transition={{ duration: 1.5, repeat: zone === 'RED' ? Infinity : 0 }}
        >
          <span className="text-3xl">{z.emoji}</span>
          <span className={`text-xs font-black tracking-widest mt-1 ${z.textColor}`}>{zone}</span>
        </motion.div>
        {isScanning && (
          <motion.div
            className="absolute -inset-3 rounded-full border border-brand/30"
            animate={{ scale: [1, 1.15, 1], opacity: [0.5, 0, 0.5] }}
            transition={{ duration: 2, repeat: Infinity }}
          />
        )}
      </div>
      <div className={`tag ${z.bgColor} ${z.textColor} border ${z.borderColor}`}>
        <Activity className="w-3 h-3" />{z.label}
      </div>
      
      {/* Live Demand Stats */}
      {stats && stats.baselineOrders ? (
        <div className="w-full flex items-center justify-between gap-2 mt-2">
          <div className={`glass flex-1 rounded-lg p-2 text-center shadow-inner border ${isDemandCollapsed ? 'border-danger/30' : 'border-white/5'}`}>
            <p className="text-[9px] uppercase tracking-wider text-slate-500 font-bold mb-0.5">Orders</p>
            <p className={`text-lg font-black ${isDemandCollapsed ? 'text-danger' : 'text-slate-200'}`}>
              {stats.ordersPerMin}<span className="text-[10px] text-slate-500 ml-1">/min</span>
            </p>
          </div>
          <div className="glass flex-1 rounded-lg p-2 text-center shadow-inner border border-white/5">
            <p className="text-[9px] uppercase tracking-wider text-slate-500 font-bold mb-0.5">Active Rest.</p>
            <p className={`text-lg font-black ${stats.activeRes < 15 ? 'text-danger' : 'text-slate-200'}`}>
              {stats.activeRes}
            </p>
          </div>
        </div>
      ) : null}

      <div className="w-full mt-2">
        <div className="flex justify-between text-[10px] text-slate-500 mb-1.5 uppercase font-bold tracking-wider">
          <span>Risk Score</span>
          <span className={z.textColor}>{(riskScore * 100).toFixed(0)}%</span>
        </div>
        <div className="h-2 bg-white/5 rounded-full overflow-hidden">
          <motion.div
            className="h-full rounded-full"
            style={{
              background: zone === 'GREEN'  ? 'linear-gradient(90deg,#10b981,#34d399)'
                        : zone === 'YELLOW' ? 'linear-gradient(90deg,#f59e0b,#fbbf24)'
                        :                     'linear-gradient(90deg,#ef4444,#f87171)',
              boxShadow: zone === 'RED' ? '0 0 8px rgba(239,68,68,0.5)' : undefined
            }}
            initial={{ width: 0 }}
            animate={{ width: `${riskScore * 100}%` }}
            transition={{ duration: 1.2, ease: [0.34, 1.56, 0.64, 1] }}
          />
        </div>
      </div>
    </div>
  )
}

function TriggerFeed({ events }) {
  const ICONS  = { WEATHER: <CloudRain className="w-3.5 h-3.5" />, PAYOUT: <Wallet className="w-3.5 h-3.5" />, TRAFFIC: <Car className="w-3.5 h-3.5" />, STRIKE: <Megaphone className="w-3.5 h-3.5" />, SYSTEM: <Activity className="w-3.5 h-3.5" />, CARBON_REWARD: <Sparkles className="w-3.5 h-3.5" /> }
  const COLORS = { WEATHER: 'text-blue-400 bg-blue-400/10 border-blue-400/20', PAYOUT: 'text-safe bg-safe/10 border-safe/20', TRAFFIC: 'text-warn bg-warn/10 border-warn/20', STRIKE: 'text-danger bg-danger/10 border-danger/20', SYSTEM: 'text-brand bg-brand/10 border-brand/20', CARBON_REWARD: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20' }
  return (
    <div className="space-y-2 max-h-[220px] overflow-y-auto custom-scrollbar">
      {events.length === 0 && <p className="text-xs text-slate-600 uppercase tracking-widest animate-pulse py-4 text-center">Monitoring regional signals...</p>}
      <AnimatePresence>
        {events.map((e, i) => (
          <motion.div key={e.id}
            className="flex items-start gap-3 p-3.5 rounded-xl bg-white/5 border border-white/5 hover:bg-white/10 transition-all"
            initial={{ opacity: 0, x: -15 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.35 }}>
            <div className={`tag border ${COLORS[e.type] || COLORS.SYSTEM} flex-shrink-0 mt-0.5`}>{ICONS[e.type] || ICONS.SYSTEM}</div>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-slate-200 font-medium leading-snug">{e.msg}</p>
              <div className="flex items-center gap-3 mt-1">
                <span className="text-[10px] text-slate-600">{e.time || new Date(e.timestamp || Date.now()).toLocaleTimeString()}</span>
              </div>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}

/* ─── Main Dashboard ──────────────────────────────────────── */
export default function Dashboard({ user, platform, onLogout, cityState, wsConnected, livePayouts = [] }) {
  const [zone, setZone]             = useState('GREEN')
  const [riskScore, setRiskScore]   = useState(0.12)
  const [lastPayout, setLastPayout] = useState(null)
  const [totalProtection, setTotalProtection] = useState(user?.total_protection || 3200)
  const [weeklyPremium]             = useState(Math.round(Math.random() * 30 + 55))
  const activeClaim                 = useSimulationStore(state => state.activeClaim)
  const [payoutHistory, setPayoutHistory]     = useState([])
  const [triggerEvents, setTriggerEvents]     = useState([])
  const [isScanning, setIsScanning]           = useState(false)
  const [isRefreshing, setIsRefreshing]       = useState(false)
  const [simLoading, setSimLoading]           = useState(null)
  const [activeShift, setActiveShift]         = useState(null)
  const [shiftSaving, setShiftSaving]         = useState(false)
  const [powData, setPowData]                 = useState(null)
  const [showNotif, setShowNotif]             = useState(false)
  const [aiAdvice, setAiAdvice]               = useState(null)
  const [aiLoading, setAiLoading]             = useState(false)
  const [showDemoPanel, setShowDemoPanel]     = useState(false)
  const [esgStats, setEsgStats]               = useState({
    total_carbon_saved: user?.total_carbon_saved || 0,
    discount: user?.esg_discount || 0,
    badge: user?.esg_badge || 'Bronze'
  })
  const [viewport, setViewport]               = useState({ latitude: 13.0827, longitude: 80.2707, zoom: 11 })
  const scanIntervalRef = useRef(null)
  const prevZoneRef     = useRef('GREEN')
  const seenPayoutIds   = useRef(new Set())

  const userId = user?.user_id || 'ZOM-1001'

  // ── Sync from WebSocket city state ─────────────────────────────────────────
  useEffect(() => {
    if (!cityState) return

    const myWorker = cityState.workers?.find(w => w.id === userId)
    if (myWorker) {
      const newZone = myWorker.zone_state || 'GREEN'
      setZone(newZone)

      // Find zone risk score
      const zoneData = cityState.zones?.find(z => z.id === myWorker.zone_id)
      if (zoneData) {
        setRiskScore(zoneData.risk_score ?? 0.12)
      }

      // Center map on worker
      if (myWorker.lat && myWorker.lon) {
        setViewport(v => ({ ...v, latitude: myWorker.lat, longitude: myWorker.lon }))
      }

      setTotalProtection(myWorker.total_protection || 3200)
      
      if (myWorker.shift) {
        setActiveShift(myWorker.shift)
      }
      if (myWorker.pow) {
        setPowData(myWorker.pow)
      }

      // If zone changed flash the scanning indicator
      if (newZone !== prevZoneRef.current) {
        setIsScanning(true)
        setTimeout(() => setIsScanning(false), 2000)
        prevZoneRef.current = newZone
      }
    }

    // Consume events from WS
    if (cityState.events?.length) {
      cityState.events.forEach(ev => {
        const evId = `${ev.type}-${ev.timestamp}-${ev.amount}`
        const mapped = {
          id: Date.now() + Math.random(),
          type: ev.type,
          msg: ev.msg,
          time: new Date(ev.timestamp || Date.now()).toLocaleTimeString(),
        }
        setTriggerEvents(prev => [mapped, ...prev].slice(0, 15))

        if (ev.type === 'PAYOUT' && ev.amount && !seenPayoutIds.current.has(evId)) {
          seenPayoutIds.current.add(evId)
          const p = {
            id: evId,
            amount: ev.amount,
            reason: ev.reason || ev.msg,
            calculation: ev.calculation_details,
            zone: ev.zone,
            time: new Date(ev.timestamp || Date.now()).toLocaleTimeString()
          }
          setLastPayout(p)
          setTotalProtection(t => +(t + ev.amount).toFixed(0))
          setPayoutHistory(prev => [p, ...prev].slice(0, 8))
          setShowNotif(true)
          setTimeout(() => setShowNotif(false), 4500)
        }
      })
    }

    // FALLBACK: also consume from analytics.recent_payouts (poll path)
    if (cityState.analytics?.recent_payouts?.length) {
      cityState.analytics.recent_payouts.slice(0, 3).forEach(p => {
        const evId = `PAYOUT-${p.timestamp}-${p.amount}`
        if (p.amount && !seenPayoutIds.current.has(evId)) {
          seenPayoutIds.current.add(evId)
          const record = {
            id: evId,
            amount: p.amount,
            reason: p.reason,
            calculation: p.calculation_details,
            zone: p.zone,
            time: new Date(p.timestamp || Date.now()).toLocaleTimeString()
          }
          setLastPayout(record)
          setPayoutHistory(prev => [record, ...prev].slice(0, 8))
          setShowNotif(true)
          setTimeout(() => setShowNotif(false), 4500)
        }
      })
    }
  }, [cityState?.timestamp, userId])

  // ── Consume live real-time payouts from WebSocket NOTIFICATION events ─────────
  useEffect(() => {
    if (!livePayouts?.length) return
    const latest = livePayouts[0]
    if (!latest) return
    const pid = latest.id || `${latest.timestamp}-${latest.amount}`
    if (seenPayoutIds.current.has(pid)) return
    seenPayoutIds.current.add(pid)

    const p = {
      id: pid,
      amount: latest.amount,
      reason: latest.reason,
      reason_explanation: latest.reason_explanation,
      calculation: latest.calculation_details,
      source: latest.source,
      zone: latest.zone,
      pool_used: latest.pool_used,
      time: new Date(latest.timestamp || Date.now()).toLocaleTimeString()
    }
    setLastPayout(p)
    setTotalProtection(t => +(t + latest.amount).toFixed(0))
    setPayoutHistory(prev => [p, ...prev].slice(0, 10))
    setShowNotif(true)
    setTimeout(() => setShowNotif(false), 6000)

    // Sync ESG stats if it was an ESG update
    if (latest.type === 'SYSTEM' && latest.msg.includes('ESG:')) {
      const myWorker = cityState?.workers?.find(w => w.id === userId)
      if (myWorker) {
        setEsgStats({
          total_carbon_saved: myWorker.total_carbon_saved || 0,
          discount: myWorker.esg_discount || 0,
          badge: myWorker.esg_badge || 'Bronze'
        })
      }
    }
  }, [livePayouts])

  // ── Background scanning ping ─────────────────────────────
  useEffect(() => {
    scanIntervalRef.current = setInterval(() => setIsScanning(v => !v), 7000)
    return () => clearInterval(scanIntervalRef.current)
  }, [])

  const handleRefresh = async () => {
    setIsRefreshing(true)
    setIsScanning(true)
    try {
      const token = localStorage.getItem('snapinsure_token')
      const res = await fetch(`${GIG_API}/dashboard/${userId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (res.ok) {
        const data = await res.json()
        setZone(data.zone || 'GREEN')
        setRiskScore(data.risk_score ?? 0.12)
        setTotalProtection(data.total_protection || totalProtection)
      }
    } catch (_) {}
    setIsRefreshing(false)
    setIsScanning(false)
  }

  const setShift = async (shiftId) => {
    setShiftSaving(shiftId)
    try {
      const token = localStorage.getItem('snapinsure_token')
      const res = await fetch(`${GIG_API}/shift`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ user_id: userId, shift_id: shiftId })
      })
      if (res.ok) {
        const body = await res.json()
        setActiveShift(body.shift)
      }
    } catch {}
    setShiftSaving(false)
  }

  const runSimulation = async (scenario) => {
    if (simLoading) return
    setSimLoading(scenario.id)
    setIsScanning(true)

    setTriggerEvents(prev => [{
      id: Date.now(), type: 'SYSTEM', msg: `Simulating: ${scenario.label}...`, time: new Date().toLocaleTimeString()
    }, ...prev].slice(0, 15))

    try {
      const token = localStorage.getItem('snapinsure_token')
      await fetch(`${SIM_API}/sim/trigger`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ event_type: scenario.id }),
      })
      // UI updates will come through WebSocket
    } catch {
      // Fallback: apply locally
      setZone(scenario.zone)
      setRiskScore(scenario.risk)
      setTimeout(() => {
        const p = { amount: scenario.payout, reason: `${scenario.label} — automated payout`, time: new Date().toLocaleTimeString() }
        setLastPayout(p)
        setPayoutHistory(prev => [p, ...prev].slice(0, 8))
        setTotalProtection(t => +(t + scenario.payout).toFixed(0))
        setShowNotif(true)
        setTimeout(() => setShowNotif(false), 4500)
      }, 1500)
    } finally {
      setTimeout(() => { setSimLoading(null); setIsScanning(false) }, 2000)
    }
  }

  const getAiAdvice = async () => {
    setAiLoading(true)
    try {
      const res = await fetch(`${SIM_API}/ai/suggest?worker_id=${userId}`)
      if (res.ok) {
        const data = await res.json()
        setAiAdvice(data)
      }
    } catch (_) {}
    setAiLoading(false)
  }

  const zConf = ZONE_MAP[zone] || ZONE_MAP.GREEN
  const chartData = payoutHistory.slice().reverse().map((p, i) => ({ name: `P${i + 1}`, amount: p.amount }))
  if (chartData.length < 2) for (let i = chartData.length; i < 4; i++) chartData.unshift({ name: `P${i + 1}`, amount: 0 })

  // Build zone GeoJSON overlay for mini map
  const myWorkerData = cityState?.workers?.find(w => w.id === userId)
  const currentZoneData = cityState?.zones?.find(z => z.id === myWorkerData?.zone_id)

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 relative">

      {/* ── Payout notification toast — RICH EXPLAINABILITY ── */}
      <AnimatePresence>
        {showNotif && lastPayout && (
          <motion.div
            className="fixed top-20 right-4 z-50 glass border border-safe/40 rounded-2xl p-5 shadow-[0_0_40px_rgba(16,185,129,0.25)] w-80 max-w-[calc(100vw-2rem)]"
            initial={{ opacity: 0, x: 80, scale: 0.92 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 80, scale: 0.92 }}
            transition={{ type: 'spring', bounce: 0.3 }}
          >
            {/* Header */}
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-xl bg-safe/20 flex items-center justify-center border border-safe/30 shadow-glow-safe">
                <Zap className="w-5 h-5 text-safe" />
              </div>
              <div>
                <p className="text-[10px] text-safe/80 font-bold uppercase tracking-widest">Auto-Credited · Insurance</p>
                <p className="text-2xl font-black text-white leading-none">₹{lastPayout.amount}</p>
              </div>
              <button onClick={() => setShowNotif(false)} className="ml-auto text-slate-500 hover:text-white text-lg leading-none">✕</button>
            </div>
            {/* Explainability card */}
            <div className="space-y-2 text-xs">
              <div className="flex justify-between border-b border-white/5 pb-2">
                <span className="text-slate-500">Type</span>
                <span className="text-safe font-bold">{lastPayout.reason}</span>
              </div>
              {lastPayout.reason_explanation && (
                <div className="flex justify-between border-b border-white/5 pb-2">
                  <span className="text-slate-500">Reason</span>
                  <span className="text-white text-right max-w-[60%] leading-tight">{lastPayout.reason_explanation}</span>
                </div>
              )}
              {lastPayout.calculation && (
                <div className="flex justify-between border-b border-white/5 pb-2">
                  <span className="text-slate-500">Calculation</span>
                  <span className="text-brand font-mono text-right max-w-[60%] leading-tight">{lastPayout.calculation}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-slate-500">Source</span>
                <span className={`font-bold ${lastPayout.pool_used ? 'text-brandlt' : 'text-warn'}`}>
                  {lastPayout.pool_used ? '🏦 Risk Pool' : '⚡ System Reserve'}
                </span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Active Claim Processing Header Bar ────────────────── */}
      <AnimatePresence>
        {activeClaim && (
          <motion.div
            initial={{ opacity: 0, y: -20, height: 0 }}
            animate={{ opacity: 1, y: 0, height: 'auto' }}
            exit={{ opacity: 0, y: -20, height: 0 }}
            className="mb-6 overflow-hidden"
          >
            <div className="glass rounded-2xl p-4 border border-brand/40 shadow-glow-brand relative overflow-hidden bg-brand/5">
              <div className="absolute inset-0 bg-[url('/mesh.svg')] opacity-10" />
              <div className="relative z-10 flex flex-col md:flex-row items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-brand/20 flex flex-shrink-0 items-center justify-center border border-brand/30 shadow-[0_0_15px_rgba(59,130,246,0.3)]">
                  {activeClaim.status === 'processing' ? (
                    <Activity className="w-6 h-6 text-brandlt animate-pulse" />
                  ) : activeClaim.status === 'approved' || activeClaim.status === 'paid' ? (
                    <CheckCircle className="w-6 h-6 text-safe" />
                  ) : (
                    <Clock className="w-6 h-6 text-warn" />
                  )}
                </div>
                <div className="flex-1 w-full text-center md:text-left">
                  <p className="text-[10px] uppercase font-black tracking-widest text-brand mb-0.5 animate-pulse">
                    Automated Claim Engine Active
                  </p>
                  <p className="text-sm text-slate-200">
                    Claim <span className="font-mono text-white">{activeClaim.claim_id || 'ID-XXX'}</span> for <span className="font-bold">{activeClaim.worker_name || 'Worker'}</span> is currently <span className="uppercase font-bold text-white tracking-wide">{activeClaim.status}</span>
                  </p>
                </div>
                <div className="w-full md:w-64">
                  <div className="flex justify-between text-[10px] font-bold text-slate-400 mb-1.5 uppercase tracking-wider">
                    <span>Progress</span>
                    <span className="text-white">
                      {activeClaim.status === 'filed' ? '25%' : activeClaim.status === 'processing' ? '65%' : '100%'}
                    </span>
                  </div>
                  <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                    <motion.div
                      className={`h-full rounded-full ${
                        activeClaim.status === 'approved' || activeClaim.status === 'paid'
                          ? 'bg-safe'
                          : 'bg-brand shadow-[0_0_8px_rgba(59,130,246,0.5)]'
                      }`}
                      initial={{ width: 0 }}
                      animate={{
                        width: activeClaim.status === 'filed' ? '25%' : activeClaim.status === 'processing' ? '65%' : '100%'
                      }}
                      transition={{ duration: 1.5, ease: 'easeInOut' }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Worker Identity Bar ──────────────────────────────── */}
      <motion.div className="glass rounded-2xl p-4 mb-6 flex flex-col sm:flex-row items-start sm:items-center gap-4 relative overflow-hidden"
        initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1, duration: 0.5 }}>
        {isScanning && <div className="laser-line" />}
        <div className="flex items-center gap-4 flex-1">
          <div className="relative flex-shrink-0">
            <div className="w-12 h-12 rounded-xl glass flex items-center justify-center text-2xl">
              {platform?.id === 'zomato' ? '🍕' : platform?.id === 'swiggy' ? '🛵' : platform?.id === 'uber' ? '🚗' : '⚡'}
            </div>
            <div className="absolute -bottom-1 -right-1 w-5 h-5 bg-safe rounded-full border-2 border-surface flex items-center justify-center">
              <CheckCircle className="w-3 h-3 text-white" />
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-base font-black text-white">{user?.name}</h2>
              <span className="tag bg-brand/10 text-brandlt border border-brand/20">{user?.company}</span>
              <span className={`tag ${wsConnected ? 'bg-safe/10 text-safe border-safe/20' : 'bg-slate-700 text-slate-500 border-slate-600'} border`}>
                <span className={`w-1.5 h-1.5 rounded-full ${wsConnected ? 'bg-safe animate-pulse' : 'bg-slate-500'}`} />
                {wsConnected ? 'LIVE' : 'OFFLINE'}
              </span>
            </div>
            <div className="flex items-center gap-3 mt-1">
              <span className="text-xs text-slate-500 flex items-center gap-1"><MapPin className="w-3 h-3" />{user?.city}</span>
              <span className="text-xs text-slate-500">ID: {user?.user_id}</span>
              {myWorkerData?.zone_id && (
                <span className="text-xs text-slate-500">Zone: {myWorkerData.zone_id} ({currentZoneData?.name || ''})</span>
              )}
            </div>
          </div>
        </div>
        <div className="text-right flex-shrink-0 flex flex-col items-end">
          <p className="text-[10px] text-slate-500 uppercase tracking-wider font-bold">Current Zone</p>
          <div className="flex items-center gap-3">
             {currentZoneData?.surge > 1.0 && (
               <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-warn/10 border border-warn/20 text-warn animate-pulse">
                  <TrendingUp className="w-3 h-3" />
                  <span className="text-[10px] font-black">{currentZoneData.surge}x SURGE</span>
               </div>
             )}
             <p className={`text-2xl font-black ${zConf.textColor}`}>{zone}</p>
          </div>
        </div>
      </motion.div>

      {/* ── PoW Validation Bar ──────────────────────────────── */}
      {powData && (
        <motion.div className="glass rounded-2xl p-4 mb-6 flex flex-col lg:flex-row items-center justify-between gap-4 relative overflow-hidden"
          initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12, duration: 0.5 }}>
          
          <div className="flex items-center gap-4">
            <div className={`w-12 h-12 rounded-xl flex items-center justify-center border-2 ${powData.is_valid ? 'bg-safe/10 border-safe/30 text-safe shadow-glow-safe' : 'bg-danger/10 border-danger/30 text-danger shadow-[0_0_15px_rgba(239,68,68,0.5)] animate-pulse'}`}>
               {powData.is_valid ? <CheckCircle className="w-6 h-6" /> : <XCircle className="w-6 h-6" />}
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-widest font-bold text-slate-500 mb-0.5">Automated Validation</p>
              {powData.is_valid ? (
                <p className="text-lg font-black text-white flex items-center gap-2">Proof of Work Verified <span className="text-safe text-sm bg-safe/20 rounded-full">✅</span></p>
              ) : (
                <p className="text-lg font-black text-danger flex items-center gap-2">Insufficient Activity <span className="text-danger text-sm bg-danger/20 rounded-full">❌</span></p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-4 lg:ml-auto">
            <div className="text-right flex-shrink-0">
              <p className="text-[10px] text-slate-500 uppercase font-bold tracking-wider mb-1">Fraud Score</p>
              <div className="flex items-center gap-2">
                <div className="w-24 h-2 bg-white/10 rounded-full overflow-hidden">
                  <motion.div className={`h-full rounded-full ${powData.fraud_score > 50 ? 'bg-safe' : 'bg-danger'}`} animate={{ width: `${powData.fraud_score}%` }} />
                </div>
                <span className="text-xs font-black text-white">{powData.fraud_score}/100</span>
              </div>
            </div>

            <div className="hidden sm:flex items-center gap-4 border-l border-white/10 pl-4 h-10">
              <div>
                <p className="text-[9px] text-slate-500 uppercase tracking-widest font-bold mb-0.5"><Clock className="w-3 h-3 inline mr-1 text-slate-400"/>Active</p>
                <p className="text-sm font-semibold text-white">{Math.floor(powData.active_time / 60)}m {powData.active_time % 60}s</p>
              </div>
              <div>
                <p className="text-[9px] text-slate-500 uppercase tracking-widest font-bold mb-0.5">Idle</p>
                <p className={`text-sm font-semibold ${powData.idle_time > 90 ? 'text-danger' : 'text-slate-300'}`}>{Math.floor(powData.idle_time / 60)}m {powData.idle_time % 60}s</p>
              </div>
              <div>
                <p className="text-[9px] text-slate-500 uppercase tracking-widest font-bold mb-0.5"><CheckCircle className="w-3 h-3 inline mr-1 text-slate-400"/>Trips</p>
                <p className="text-sm font-semibold text-white">{powData.completed_trips}</p>
              </div>
            </div>
          </div>
        </motion.div>
      )}

      {/* ── Main 4-card Grid ─────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {/* Card 1 — Zone */}
        <motion.div className="col-span-2 lg:col-span-1 glass rounded-2xl p-5 shadow-card"
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15, duration: 0.5 }}>
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-4 flex items-center gap-2">
            <Activity className="w-3.5 h-3.5 text-brand" /> Current Zone
          </p>
          <ZoneOrb 
            zone={zone} 
            riskScore={riskScore} 
            isScanning={isScanning} 
            stats={{
              ordersPerMin: currentZoneData?.orders_per_minute,
              baselineOrders: currentZoneData?.baseline_orders,
              activeRes: currentZoneData?.active_restaurants
            }}
          />
        </motion.div>

        {/* Card 2 — Active Risk Factors */}
        <motion.div className="col-span-2 lg:col-span-1 glass rounded-2xl p-5 shadow-card"
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2, duration: 0.5 }}>
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-4 flex items-center gap-2">
            <AlertTriangle className="w-3.5 h-3.5 text-brand" /> Disruption Factors
          </p>
          <div className="space-y-3">
            {[
              { key: 'rain',    label: 'Heavy Rain',     icon: <CloudRain className="w-4 h-4" />, color: 'text-blue-400', bg: 'bg-blue-400/10', border: 'border-blue-400/20' },
              { key: 'traffic', label: 'Traffic Delay',  icon: <Car className="w-4 h-4" />,       color: 'text-warn',     bg: 'bg-warn/10',     border: 'border-warn/20' },
              { key: 'strike',  label: 'Strike/Protest', icon: <Megaphone className="w-4 h-4" />, color: 'text-danger',   bg: 'bg-danger/10',   border: 'border-danger/20' },
            ].map(f => {
              const active = zone === 'RED' || (zone === 'YELLOW' && f.key === 'traffic')
              return (
                <motion.div key={f.key}
                  className={`flex items-center gap-3 p-3 rounded-xl border transition-all duration-500 ${active ? `${f.bg} ${f.border}` : 'bg-white/2 border-white/5'}`}
                  animate={{ scale: active ? [1, 1.02, 1] : 1 }} transition={{ duration: 0.4 }}>
                  <div className={`${f.color} flex-shrink-0`}>{f.icon}</div>
                  <p className={`text-xs font-semibold ${active ? f.color : 'text-slate-500'}`}>{f.label}</p>
                  <div className={`ml-auto w-2 h-2 rounded-full ${active ? `${f.color.replace('text-', 'bg-')} animate-pulse` : 'bg-slate-700'}`} />
                </motion.div>
              )
            })}
          </div>
        </motion.div>

        {/* Card 3 — Collective Risk Pool */}
        <motion.div className="glass glass-hover rounded-2xl p-5 flex flex-col gap-1 relative overflow-hidden shadow-card"
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25, duration: 0.5 }}>
          <div className="absolute top-0 right-0 w-32 h-32 bg-brand/10 rounded-full blur-2xl flex-shrink-0 pointer-events-none" />
          <div className="flex items-center justify-between mb-3 relative z-10">
            <div className="w-9 h-9 rounded-xl bg-white/5 flex items-center justify-center text-brandlt"><Users className="w-4 h-4" /></div>
            <span className="tag bg-brand/10 text-brandlt border border-brand/20">{(currentZoneData?.pool_contributors || 0)} Locals</span>
          </div>
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest relative z-10">Local Risk Pool</p>
          <p className="text-3xl font-black text-brandlt relative z-10">₹{(currentZoneData?.pool_balance || 0).toLocaleString(window.navigator.language, {maximumFractionDigits: 0})}</p>
          <p className="text-xs text-slate-500 mt-0.5 relative z-10">Mutualized protection fund</p>
        </motion.div>

        {/* Card 4 — Last Payout */}
        <motion.div className="glass glass-hover rounded-2xl p-5 flex flex-col gap-1 relative overflow-hidden shadow-card"
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3, duration: 0.5 }}>
          <div className="flex items-center justify-between mb-3">
            <div className="w-9 h-9 rounded-xl bg-white/5 flex items-center justify-center text-slate-400"><Wallet className="w-4 h-4" /></div>
            {lastPayout && <span className="tag bg-safe/10 text-safe border border-safe/20 animate-pulse">✓ Just Credited</span>}
          </div>
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest">Last Payout</p>
          <p className={`text-3xl font-black ${lastPayout ? 'text-safe' : 'text-white'}`}>{lastPayout ? `₹${lastPayout.amount}` : '—'}</p>
          {lastPayout && (
            <>
              <p className="text-xs text-safe/80 mt-0.5 font-semibold">{lastPayout.reason}</p>
              <p className="text-[10px] text-slate-600 mt-1">{lastPayout.time}</p>
            </>
          )}
          {!lastPayout && <p className="text-xs text-slate-500 mt-0.5">Automated Risk Engine Live</p>}
        </motion.div>

        {/* Card 5 — Environmental Impact (ESG) */}
        <motion.div className="col-span-2 lg:col-span-1 glass glass-hover rounded-2xl p-5 flex flex-col gap-1 relative overflow-hidden shadow-card"
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35, duration: 0.5 }}>
          <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/5 rounded-full blur-2xl flex-shrink-0 pointer-events-none" />
          <div className="flex items-center justify-between mb-3 relative z-10">
            <div className="w-9 h-9 rounded-xl bg-emerald-500/10 flex items-center justify-center text-emerald-400 border border-emerald-500/20 shadow-glow-safe">
              <Sparkles className="w-4 h-4" />
            </div>
            <span className={`tag ${esgStats.badge === 'Green Elite' ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30 shadow-glow-safe' : 'bg-white/5 text-slate-400 border-white/10'}`}>
               {esgStats.badge}
            </span>
          </div>
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest relative z-10">Green Savings</p>
          <p className="text-3xl font-black text-emerald-400 relative z-10">{esgStats.total_carbon_saved} <span className="text-xs text-slate-500">kg/CO₂</span></p>
          <div className="flex items-center gap-2 mt-2 relative z-10">
             <div className="bg-emerald-500/10 border border-emerald-500/20 rounded px-2 py-0.5">
                <p className="text-[9px] font-black text-emerald-400">{Math.round(esgStats.discount * 100)}% PREM. DISCOUNT</p>
             </div>
          </div>
        </motion.div>
      </div>

      {/* ── Transaction Feed ─────────────────────────────────── */}
      {payoutHistory.length > 0 && (
        <motion.div className="glass rounded-2xl p-5 mb-6 shadow-card"
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.32, duration: 0.5 }}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2"><Zap className="w-4 h-4 text-safe" /> Live Transaction Feed</h3>
            <span className="tag bg-safe/10 text-safe border border-safe/20">{payoutHistory.length} Payouts</span>
          </div>
          <div className="space-y-2 max-h-48 overflow-y-auto custom-scrollbar">
            <AnimatePresence>
              {payoutHistory.map((p, i) => (
                <motion.div key={p.id || i}
                  initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}
                  className="flex items-center gap-4 p-3 rounded-xl bg-safe/5 border border-safe/10">
                  <div className="w-10 h-10 rounded-xl bg-safe/15 flex items-center justify-center flex-shrink-0">
                    <Zap className="w-4 h-4 text-safe" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-black text-safe">₹{p.amount}</p>
                      <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full ${
                        p.zone === 'RED' ? 'bg-danger/20 text-danger' : 'bg-warn/20 text-warn'
                      }`}>{p.zone || 'DISRUPTION'}</span>
                    </div>
                    <p className="text-xs text-slate-400 truncate">{p.reason}</p>
                    {p.calculation && <p className="text-[10px] text-slate-600 font-mono">{p.calculation}</p>}
                  </div>
                  <span className="text-[10px] text-slate-600 flex-shrink-0">{p.time}</span>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </motion.div>
      )}

      {/* ── Middle Row: Mapbox + AI Feed ──────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        {/* Mini map */}
        <motion.div className="lg:col-span-2 glass rounded-2xl shadow-card relative overflow-hidden"
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35, duration: 0.5 }}>
          <div className="absolute top-4 left-4 right-4 z-10 flex items-center justify-between pointer-events-none">
            <div className="glass px-3 py-1.5 rounded-full flex items-center gap-2 pointer-events-auto">
              <MapPin className="w-3.5 h-3.5 text-brandlt" />
              <span className="text-[10px] font-bold text-slate-300 uppercase tracking-widest">{user?.city} Live Feed</span>
            </div>
            {isScanning && <span className="tag bg-brand/10 text-brandlt border border-brand/20 animate-pulse">SYNCING GPS...</span>}
          </div>

          <Map
            {...viewport}
            onMove={evt => setViewport(evt.viewState)}
            mapStyle="mapbox://styles/mapbox/dark-v11"
            mapboxAccessToken={MAPBOX_TOKEN}
            style={{ width: '100%', height: '340px' }}
          >
            <NavigationControl position="bottom-right" />

            {/* Zone overlay */}
            {cityState?.zones && (
              <Source id="zones-mini" type="geojson" data={{
                type: 'FeatureCollection',
                features: cityState.zones.map(z => ({
                  type: 'Feature',
                  geometry: { type: 'Point', coordinates: [z.lon, z.lat] },
                  properties: { state: z.state }
                }))
              }}>
                <Layer id="zones-mini-circle" type="circle" paint={{
                  'circle-radius': 60,
                  'circle-color': ['match', ['get', 'state'], 'RED', '#ef4444', 'YELLOW', '#f59e0b', '#10b981'],
                  'circle-opacity': 0.18,
                  'circle-stroke-width': 1.5,
                  'circle-stroke-color': ['match', ['get', 'state'], 'RED', '#ef4444', 'YELLOW', '#f59e0b', '#10b981'],
                  'circle-stroke-opacity': 0.5,
                }} />
              </Source>
            )}

            {/* All workers as dots */}
            {cityState?.workers?.map(w => (
              <Marker key={w.id} latitude={w.lat} longitude={w.lon}>
                <div className="relative">
                  {w.id === userId && <div className="absolute -inset-1 rounded-full border-2 border-brand/60 animate-ping opacity-60" />}
                  <div className="w-4 h-4 rounded-full border-2 border-white/30"
                    style={{
                      background: ZONE_COLORS[w.zone_state] + 'aa',
                      boxShadow: w.id === userId ? `0 0 10px ${ZONE_COLORS[w.zone_state]}` : 'none',
                    }} />
                </div>
              </Marker>
            ))}
          </Map>

          <div className="absolute inset-x-0 bottom-0 h-12 bg-gradient-to-t from-[#161b27] to-transparent pointer-events-none" />
        </motion.div>

        {/* AI Feed */}
        <div className="flex flex-col gap-4 lg:col-span-1">
          <motion.div className="glass rounded-2xl p-5 shadow-card flex-1 flex flex-col"
            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4, duration: 0.5 }}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-400 flex items-center gap-2">
                <LiveDot color={zone === 'RED' ? 'bg-danger' : 'bg-brand'} /> AI Feed
              </h3>
              <button onClick={handleRefresh} disabled={isRefreshing}
                className="w-6 h-6 rounded-lg bg-white/5 flex items-center justify-center text-slate-500 hover:text-white transition-all">
                <RefreshCw className={`w-3 h-3 ${isRefreshing ? 'animate-spin' : ''}`} />
              </button>
            </div>
            <div className="flex-1 overflow-hidden"><TriggerFeed events={triggerEvents} /></div>
          </motion.div>

          {lastPayout && (
            <motion.div className="glass rounded-2xl p-5 shadow-card hidden lg:flex flex-col"
              initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.45, duration: 0.5 }}>
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-3 flex items-center gap-2">
                <Zap className="w-3.5 h-3.5 text-safe" /> Last Disruption
              </p>
              <div className="glass bg-safe/10 border border-safe/20 rounded-xl p-3">
                <p className="text-xl font-black text-safe">₹{lastPayout.amount}</p>
                <p className="text-[10px] text-slate-400 mt-1 truncate">{lastPayout.reason}</p>
              </div>
            </motion.div>
          )}
        </div>
      </div>
      
      {/* ── Shift Insurance Panel ──────────────────────────── */}
      <motion.div className="glass rounded-2xl p-5 mb-6 shadow-card"
        initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.42, duration: 0.5 }}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-bold text-white flex items-center gap-2"><Clock className="w-4 h-4 text-brand" /> Shift Insurance</h3>
            <p className="text-xs text-slate-500 mt-0.5">Insure your specific time slot. We guarantee your expected earnings.</p>
          </div>
          {activeShift && activeShift.compensated && <span className="tag bg-safe/10 text-safe border border-safe/20">Shift Compensated</span>}
        </div>

        {activeShift && !activeShift.compensated ? (
          <div className="bg-white/5 border border-white/10 rounded-xl p-4 mb-4">
            <div className="flex justify-between items-end mb-2">
              <div>
                <p className="text-[10px] uppercase font-bold text-brand tracking-wider mb-1 flex items-center gap-1.5">
                  <LiveDot color="bg-brand" /> ACTIVE SHIFT: {activeShift.name}
                </p>
                <p className="text-2xl font-black text-white">₹{(activeShift.current_earnings || 0).toFixed(0)} <span className="text-xs text-slate-500 font-normal">earned of ₹{activeShift.expected_income}</span></p>
              </div>
              <div className="text-right">
                <p className="text-[10px] uppercase tracking-wider text-slate-500 font-bold">Guaranteed</p>
                <p className="text-sm font-black text-safe">₹{(Math.max(0, activeShift.expected_income - (activeShift.current_earnings || 0))).toFixed(0)}</p>
              </div>
            </div>
            <div className="h-2.5 w-full bg-white/10 rounded-full overflow-hidden">
                <motion.div className="h-full bg-gradient-to-r from-brand to-safe rounded-full"
                  initial={{ width: 0 }} animate={{ width: `${Math.min(((activeShift.current_earnings || 0) / activeShift.expected_income) * 100, 100)}%` }}
                  transition={{ duration: 1.2 }}
                />
            </div>
          </div>
        ) : (
          <div className="bg-white/2 border border-white/5 rounded-xl p-3 mb-4 text-center">
            <p className="text-xs text-slate-400 font-semibold">{activeShift?.compensated ? 'Shift guaranteed target met/paid.' : 'Select a shift to insure your expected income.'}</p>
          </div>
        )}

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[
            { id: 'morning', label: 'Morning (6-10 AM)', expected: 800 },
            { id: 'lunch', label: 'Lunch (10 AM-2 PM)', expected: 600 },
            { id: 'evening', label: 'Evening (4-8 PM)', expected: 900 },
            { id: 'night', label: 'Night (8 PM-12 AM)', expected: 1200 },
          ].map(shift => (
            <button key={shift.id} disabled={shiftSaving === shift.id || (!activeShift?.compensated && activeShift?.shift_id === shift.id)}
             onClick={() => setShift(shift.id)}
             className={`p-3 rounded-xl border text-left transition-all relative overflow-hidden ${
               !activeShift?.compensated && activeShift?.shift_id === shift.id 
                 ? 'bg-brand/20 border-brand text-white shadow-glow-brand' 
                 : 'bg-white/5 border-white/10 text-slate-300 hover:bg-white/10 focus:ring-2 focus:ring-brand'
             }`}>
              {shiftSaving === shift.id && <div className="absolute inset-0 bg-white/5 animate-pulse" />}
              <p className="text-xs font-bold mb-1 relative z-10">{shift.label}</p>
              <p className="text-[10px] opacity-70 relative z-10 text-brandlt">Guarantee: ₹{shift.expected}</p>
            </button>
          ))}
        </div>
      </motion.div>

      {/* ── AI Zone Advisor ─────────────────────────────── */}
      <motion.div className="glass rounded-2xl p-5 mb-6 shadow-card"
        initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.43, duration: 0.5 }}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-brand" /> AI Zone Advisor
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">Live recommendation based on demand, risk, and earnings potential.</p>
          </div>
          <button onClick={getAiAdvice} disabled={aiLoading}
            className="btn-primary text-xs px-4 py-2 flex items-center gap-2 disabled:opacity-60">
            {aiLoading
              ? <><RefreshCw className="w-3 h-3 animate-spin" /> Analysing...</>
              : <><Navigation className="w-3 h-3" /> Get Recommendation</>}
          </button>
        </div>
        <AnimatePresence>
          {aiAdvice && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="space-y-3">
              <div className="flex items-start gap-4 p-4 rounded-xl bg-safe/5 border border-safe/20">
                <div className="w-11 h-11 rounded-xl bg-safe/15 flex items-center justify-center border border-safe/30 flex-shrink-0">
                  <Navigation className="w-5 h-5 text-safe" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-sm font-black text-white">Move to {aiAdvice.recommended?.name}</p>
                    <span className={`tag border ${aiAdvice.recommended?.risk_level === 'Low' ? 'bg-safe/10 text-safe border-safe/20' : 'bg-warn/10 text-warn border-warn/20'}`}>
                      {aiAdvice.recommended?.risk_level} Risk
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 leading-relaxed">{aiAdvice.recommended?.reason}</p>
                  <div className="flex items-center gap-4 mt-2">
                    <span className="text-xs font-bold text-safe">Est. ₹{aiAdvice.recommended?.estimated_hourly_inr}/hr</span>
                    {aiAdvice.recommended?.pool_active && <span className="text-xs text-brandlt">🏦 Pool active</span>}
                  </div>
                </div>
              </div>
              {aiAdvice.avoid?.length > 0 && (
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-slate-600 mb-2 font-bold">⚠ Avoid Now</p>
                  <div className="flex flex-wrap gap-2">
                    {aiAdvice.avoid.map(z => (
                      <div key={z.zone_id} className="text-[11px] px-3 py-1.5 rounded-lg bg-danger/10 border border-danger/20 text-danger font-semibold">
                        {z.name} — {z.reason}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* ── Simulation/Diagnostics Panel (Hidden by default) ── */}
      <div className="mb-6">
        <button
          onClick={() => setShowDemoPanel(!showDemoPanel)}
          className="flex items-center gap-2 text-[10px] font-bold text-slate-600 hover:text-slate-400 uppercase tracking-widest transition-all mb-2"
        >
          {showDemoPanel ? <XCircle className="w-3 h-3" /> : <RefreshCw className="w-3 h-3" />}
          {showDemoPanel ? 'Hide' : 'Show'} System Diagnostics
        </button>

        <AnimatePresence>
          {showDemoPanel && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden"
            >
              <div className="glass rounded-2xl p-5 border border-white/5 shadow-card">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="text-sm font-bold text-white">System Override & Diagnostics</h3>
                    <p className="text-xs text-slate-500 mt-0.5">Emergency manual triggers — bypasses real-world signal engine</p>
                  </div>
                  <div className="tag bg-brand/10 text-brandlt border border-brand/20"><Info className="w-3 h-3" />Demo Fallback</div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                  {SIM_SCENARIOS.map(s => (
                    <motion.button key={s.id} onClick={() => runSimulation(s)} disabled={!!simLoading}
                      className={`relative flex items-center gap-3 p-4 rounded-xl border transition-all duration-200 text-left overflow-hidden ${
                        simLoading === s.id ? 'border-brand/40 bg-brand/10' : 'border-white/10 bg-white/5 hover:border-white/20 hover:bg-white/10'
                      } disabled:opacity-60`}
                      whileTap={{ scale: 0.97 }}>
                      {simLoading === s.id && <div className="absolute inset-0 overflow-hidden"><div className="shimmer-bg absolute inset-0 opacity-30" /></div>}
                      <span className="text-2xl relative z-10">{s.icon}</span>
                      <div className="relative z-10">
                        <p className="text-sm font-semibold text-white">{s.label}</p>
                        <p className="text-[11px] text-slate-500 mt-0.5">→ {s.zone} zone • ₹{s.payout} payout</p>
                      </div>
                    </motion.button>
                  ))}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── Protection Tracking ──────────────────────────── */}
      <motion.div className="glass rounded-2xl p-5 shadow-card"
        initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5, duration: 0.5 }}>
        <div className="flex items-center justify-between mb-5">
          <div>
            <h3 className="text-sm font-bold text-white flex items-center gap-2"><BarChart3 className="w-4 h-4 text-brand" />Protection Tracking</h3>
            <p className="text-xs text-slate-500 mt-0.5">Lifetime coverage and earnings protection</p>
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          <div className="rounded-xl bg-gradient-to-br from-brand/10 to-transparent border border-brand/15 p-4">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">Total Protected</p>
            <p className="text-2xl font-black gradient-text-brand">₹{totalProtection.toLocaleString()}</p>
            <div className="mt-2 h-1.5 bg-white/5 rounded-full overflow-hidden">
              <motion.div className="h-full rounded-full bg-gradient-to-r from-brand to-brandlt"
                initial={{ width: 0 }} animate={{ width: `${Math.min((totalProtection / 10000) * 100, 100)}%` }}
                transition={{ duration: 1.5, ease: [0.34, 1.56, 0.64, 1] }} />
            </div>
            <p className="text-[10px] text-slate-600 mt-1">of ₹10,000 goal</p>
          </div>
          <div className="rounded-xl bg-gradient-to-br from-safe/10 to-transparent border border-safe/15 p-4">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">Disruptions Covered</p>
            <p className="text-2xl font-black gradient-text-safe">{payoutHistory.length}</p>
            <div className="mt-2 flex gap-1">
              {Array.from({ length: Math.min(payoutHistory.length, 8) }).map((_, i) => (
                <motion.div key={i} className="h-5 flex-1 rounded-sm bg-safe/30" initial={{ scaleY: 0 }} animate={{ scaleY: 1 }} transition={{ delay: i * 0.08 }} style={{ transformOrigin: 'bottom' }} />
              ))}
              {Array.from({ length: Math.max(0, 8 - payoutHistory.length) }).map((_, i) => <div key={i} className="h-5 flex-1 rounded-sm bg-white/5" />)}
            </div>
            <p className="text-[10px] text-slate-600 mt-1">events this session</p>
          </div>
          <div className="rounded-xl bg-gradient-to-br from-warn/10 to-transparent border border-warn/15 p-4">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">Avg Payout</p>
            <p className="text-2xl font-black text-warn">
              ₹{payoutHistory.length ? Math.round(payoutHistory.reduce((a, p) => a + p.amount, 0) / payoutHistory.length) : 0}
            </p>
            <div className="mt-2 h-1.5 bg-white/5 rounded-full overflow-hidden">
              <motion.div className="h-full rounded-full bg-gradient-to-r from-warn to-warnlt"
                initial={{ width: 0 }} animate={{ width: `${Math.min(payoutHistory.length * 20, 100)}%` }} transition={{ duration: 1.2 }} />
            </div>
            <p className="text-[10px] text-slate-600 mt-1">per disruption event</p>
          </div>
        </div>

        {/* Chart */}
        {payoutHistory.length > 0 && (
          <div className="rounded-xl bg-white/2 border border-white/5 p-4">
            <p className="text-xs text-slate-500 font-semibold mb-3 uppercase tracking-wider">Payout History</p>
            <div className="h-28">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -30 }}>
                  <defs>
                    <linearGradient id="payGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="name" tick={{ fontSize: 9, fill: '#475569' }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ background: '#161b27', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '10px', fontSize: '11px', color: '#f1f5f9' }} formatter={(v) => [`₹${v}`, 'Payout']} />
                  <Area type="monotone" dataKey="amount" stroke="#10b981" strokeWidth={2} fill="url(#payGrad)" dot={{ fill: '#10b981', strokeWidth: 0, r: 3 }} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </motion.div>

      <div className="text-center mt-8 pb-4">
        <p className="text-xs text-slate-700">SnapInsure v2.0 • Zero-Claim AI Engine • Real-Time WebSocket • {new Date().toLocaleDateString('en-IN', { dateStyle: 'medium' })}</p>
      </div>
    </div>
  )
}

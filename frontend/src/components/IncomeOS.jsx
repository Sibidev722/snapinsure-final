import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  TrendingUp, TrendingDown, Minus, Brain, MapPin, Zap, ArrowRight,
  RefreshCw, CheckCircle, AlertTriangle, XCircle, Navigation,
  BarChart2, Shield, Lock, Unlock, ChevronUp, ChevronDown,
  DollarSign, Activity, Star, Clock
} from 'lucide-react'

const SIM_API = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

// ── Animated counter ─────────────────────────────────────────────────────────
function AnimatedNumber({ value, prefix = '', suffix = '', duration = 800, className = '' }) {
  const [display, setDisplay] = useState(value)
  const prevRef = useRef(value)
  const frameRef = useRef(null)

  useEffect(() => {
    const start = prevRef.current
    const end = value
    if (start === end) return
    const startTime = performance.now()

    const step = (now) => {
      const elapsed = now - startTime
      const progress = Math.min(elapsed / duration, 1)
      const ease = 1 - Math.pow(1 - progress, 3)
      const current = Math.round(start + (end - start) * ease)
      setDisplay(current)
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(step)
      } else {
        prevRef.current = end
      }
    }
    frameRef.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frameRef.current)
  }, [value, duration])

  return (
    <span className={className}>
      {prefix}{display.toLocaleString()}{suffix}
    </span>
  )
}

// ── Trend icon ────────────────────────────────────────────────────────────────
function TrendIcon({ trend, size = 'w-4 h-4' }) {
  if (trend === 'UP')   return <TrendingUp   className={`${size} text-emerald-400`} />
  if (trend === 'DOWN') return <TrendingDown className={`${size} text-red-400`} />
  return <Minus className={`${size} text-slate-500`} />
}

// ── Priority badge ────────────────────────────────────────────────────────────
const PRIORITY_STYLES = {
  CRITICAL:      'bg-red-500/20 text-red-400 border-red-500/40',
  HIGH:          'bg-orange-500/20 text-orange-400 border-orange-500/40',
  WARNING:       'bg-orange-500/20 text-orange-400 border-orange-500/40',
  MEDIUM:        'bg-amber-500/20 text-amber-400 border-amber-500/40',
  LOW:           'bg-blue-500/20 text-blue-400 border-blue-500/40',
  INFO:          'bg-emerald-500/20 text-emerald-400 border-emerald-500/40',
  OPTIONAL_MOVE: 'bg-violet-500/20 text-violet-400 border-violet-500/40',
}

function PriorityBadge({ priority }) {
  return (
    <span className={`text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded-full border ${PRIORITY_STYLES[priority] || PRIORITY_STYLES.INFO}`}>
      {priority}
    </span>
  )
}

// ── Confidence meter ──────────────────────────────────────────────────────────
function ConfidenceMeter({ score }) {
  const pct = Math.round(score * 100)
  const color = pct >= 70 ? '#10b981' : pct >= 45 ? '#f59e0b' : '#ef4444'
  const label = pct >= 70 ? 'High' : pct >= 45 ? 'Moderate' : 'Low'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ background: color }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 1, ease: 'easeOut' }}
        />
      </div>
      <span className="text-[10px] font-bold" style={{ color }}>{label} {pct}%</span>
    </div>
  )
}

// ── Zone rank bar ─────────────────────────────────────────────────────────────
function ZoneRankRow({ zone, index }) {
  const stateColor = zone.state === 'GREEN' ? '#10b981' : zone.state === 'YELLOW' ? '#f59e0b' : '#ef4444'
  const scoreWidth = `${Math.max((zone.composite_score / 1.0) * 100, 4)}%`

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.04 }}
      className={`flex items-center gap-3 p-3 rounded-xl transition-all ${zone.is_best ? 'bg-emerald-500/10 border border-emerald-500/25' : 'bg-white/2 border border-white/5 hover:bg-white/5'}`}
    >
      {/* Rank badge */}
      <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-black flex-shrink-0 ${zone.is_best ? 'bg-emerald-500/30 text-emerald-300' : 'bg-white/5 text-slate-500'}`}>
        {zone.rank}
      </div>

      {/* Zone info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-bold text-slate-200 truncate">{zone.name}</span>
          {zone.is_best && <Star className="w-3 h-3 text-emerald-400 flex-shrink-0" />}
          <span className="ml-auto text-[9px] font-bold px-1.5 py-0.5 rounded-full" style={{ color: stateColor, background: stateColor + '20' }}>
            {zone.state}
          </span>
        </div>
        <div className="h-1 bg-white/5 rounded-full overflow-hidden">
          <motion.div
            className="h-full rounded-full"
            style={{ background: stateColor }}
            initial={{ width: 0 }}
            animate={{ width: scoreWidth }}
            transition={{ duration: 0.8, delay: index * 0.04 }}
          />
        </div>
      </div>

      {/* Income */}
      <div className="text-right flex-shrink-0">
        <p className="text-xs font-black text-white">₹{zone.income_per_hour}/h</p>
        <p className="text-[9px] text-slate-600">score {zone.composite_score.toFixed(2)}</p>
      </div>
    </motion.div>
  )
}

// ── Guarantee mode panel ──────────────────────────────────────────────────────
function GuaranteePanel({ userId, currentZoneState, onGuaranteePayout }) {
  const [status, setStatus]       = useState(null)
  const [inputVal, setInputVal]   = useState('')
  const [loading, setLoading]     = useState(false)
  const [enabled, setEnabled]     = useState(false)
  const [payoutBanner, setPayoutBanner] = useState(null)

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${SIM_API}/income-os/guarantee/${userId}`)
      if (res.ok) {
        const data = await res.json()
        setStatus(data)
        if (data.enabled) setEnabled(true)

        // If newly triggered
        if (data.payout_triggered && !payoutBanner) {
          const shortfall = data.shortfall
          setPayoutBanner(shortfall)
          onGuaranteePayout?.(shortfall)
        }
      }
    } catch (_) {}
  }, [userId, payoutBanner, onGuaranteePayout])

  useEffect(() => {
    fetchStatus()
    const id = setInterval(fetchStatus, 5000)
    return () => clearInterval(id)
  }, [fetchStatus])

  const enableGuarantee = async () => {
    const amount = parseFloat(inputVal)
    if (!amount || amount < 50 || amount > 5000) return
    setLoading(true)
    try {
      const res = await fetch(`${SIM_API}/income-os/guarantee`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ worker_id: userId, min_income: amount, shift_hours: 4 })
      })
      if (res.ok) {
        setEnabled(true)
        fetchStatus()
      }
    } catch (_) {}
    setLoading(false)
  }

  const disableGuarantee = async () => {
    setLoading(true)
    try {
      await fetch(`${SIM_API}/income-os/guarantee/${userId}`, { method: 'DELETE' })
      setEnabled(false)
      setStatus(null)
      setPayoutBanner(null)
      setInputVal('')
    } catch (_) {}
    setLoading(false)
  }

  const pct = status?.pct_achieved ?? 0
  const shortfall = status?.shortfall ?? 0

  return (
    <div className="space-y-4">
      {/* Payout banner */}
      <AnimatePresence>
        {payoutBanner && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="flex items-center gap-3 p-4 rounded-xl bg-emerald-500/15 border border-emerald-500/40 shadow-[0_0_25px_rgba(16,185,129,0.2)]"
          >
            <div className="w-10 h-10 rounded-xl bg-emerald-500/20 flex items-center justify-center flex-shrink-0">
              <Zap className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <p className="text-[10px] text-emerald-400/80 font-bold uppercase tracking-widest">Guarantee Payout Triggered</p>
              <p className="text-xl font-black text-white">₹{Math.round(payoutBanner)} credited</p>
            </div>
            <button onClick={() => setPayoutBanner(null)} className="ml-auto text-slate-500 hover:text-white">✕</button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main card */}
      <div className={`rounded-xl p-4 border transition-all ${enabled ? 'bg-violet-500/10 border-violet-500/30' : 'bg-white/3 border-white/8'}`}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            {enabled ? <Lock className="w-4 h-4 text-violet-400" /> : <Unlock className="w-4 h-4 text-slate-500" />}
            <span className="text-xs font-bold text-white">
              {enabled ? 'Guarantee Active' : 'Guarantee Mode Off'}
            </span>
          </div>
          {enabled && status?.payout_triggered && (
            <span className="text-[9px] font-black bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded-full">PAID OUT</span>
          )}
        </div>

        {!enabled ? (
          <div className="space-y-3">
            <p className="text-xs text-slate-500 leading-relaxed">
              Set a minimum shift income. If disruption reduces your earnings below that level, we pay the shortfall automatically.
            </p>
            <div className="flex gap-2">
              <div className="flex-1 relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm font-bold">₹</span>
                <input
                  type="number"
                  placeholder="Min income (e.g. 500)"
                  value={inputVal}
                  onChange={e => setInputVal(e.target.value)}
                  className="w-full bg-white/5 border border-white/10 rounded-lg pl-7 pr-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500/50 transition-all"
                  min="50" max="5000"
                />
              </div>
              <button
                onClick={enableGuarantee}
                disabled={loading || !inputVal}
                className="px-4 py-2 rounded-lg bg-violet-600/80 hover:bg-violet-600 text-white text-xs font-bold transition-all disabled:opacity-40 flex items-center gap-1.5"
              >
                {loading ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Shield className="w-3 h-3" />}
                Activate
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {/* Progress */}
            <div>
              <div className="flex justify-between text-[10px] text-slate-500 mb-1.5">
                <span>Earned: ₹{status?.current_earned?.toFixed(0) ?? 0}</span>
                <span>Target: ₹{status?.min_income ?? 0}</span>
              </div>
              <div className="h-3 bg-white/5 rounded-full overflow-hidden border border-white/5">
                <motion.div
                  className={`h-full rounded-full ${pct >= 60 ? 'bg-gradient-to-r from-violet-500 to-purple-400' : 'bg-gradient-to-r from-red-600 to-red-400 animate-pulse'}`}
                  initial={{ width: 0 }}
                  animate={{ width: `${pct}%` }}
                  transition={{ duration: 1 }}
                />
              </div>
              <div className="flex justify-between mt-1">
                <span className="text-[9px] text-slate-600">{pct.toFixed(0)}% achieved</span>
                {shortfall > 0 && (
                  <span className="text-[9px] text-red-400 font-bold animate-pulse">
                    ₹{shortfall.toFixed(0)} shortfall at risk
                  </span>
                )}
              </div>
            </div>

            {/* Premium */}
            <div className="flex items-center justify-between text-xs bg-white/3 rounded-lg p-2.5 border border-white/5">
              <span className="text-slate-500">Premium charged</span>
              <span className="text-violet-400 font-bold">₹{status?.premium?.toFixed(0) ?? 0}</span>
            </div>

            {/* Zone warning */}
            {(currentZoneState === 'RED' || currentZoneState === 'YELLOW') && !status?.payout_triggered && (
              <div className="flex items-center gap-2 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30">
                <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
                <p className="text-[10px] text-amber-300 font-medium">Zone disruption detected — payout may trigger soon.</p>
              </div>
            )}

            <button
              onClick={disableGuarantee}
              disabled={loading}
              className="text-[10px] text-slate-600 hover:text-red-400 transition-colors flex items-center gap-1"
            >
              <XCircle className="w-3 h-3" /> Disable guarantee
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main IncomeOS component ───────────────────────────────────────────────────
export default function IncomeOS({ user, cityState }) {
  const userId = user?.user_id || 'ZOM-1001'

  const [forecast,  setForecast]  = useState(null)
  const [scenario,  setScenario]  = useState(null)
  const [suggestion, setSuggestion] = useState(null)
  const [zones,     setZones]     = useState([])
  const [loading,   setLoading]   = useState(true)
  const [lastRefresh, setLastRefresh] = useState(null)
  const [guaranteePayout, setGuaranteePayout] = useState(null)

  // Get worker's current zone from city state
  const myWorker = cityState?.workers?.find(w => w.id === userId)
  const currentZoneId = myWorker?.zone_id
  const currentZoneState = myWorker?.zone_state || 'GREEN'

  // Prefer WebSocket income_os data when fresh — fall back to HTTP polling
  useEffect(() => {
    if (myWorker?.income_os) {
      const ios = myWorker.income_os
      if (ios.forecast)   setForecast(ios.forecast)
      if (ios.scenario)   setScenario(ios.scenario)
      if (ios.suggestion) setSuggestion(ios.suggestion)
      setLoading(false)
    }
  }, [cityState?.timestamp, myWorker?.income_os])

  // HTTP poll for zone scores (not per-worker)
  const fetchZones = useCallback(async () => {
    try {
      const res = await fetch(`${SIM_API}/income-os/zones/ranked`)
      if (res.ok) {
        const data = await res.json()
        setZones(data.zones || [])
      }
    } catch (_) {}
  }, [])

  // Fallback HTTP poll (when WS data not available)
  const fetchAll = useCallback(async () => {
    setLoading(true)
    try {
      const [fRes, sRes, suRes] = await Promise.all([
        fetch(`${SIM_API}/income-os/forecast/${userId}${currentZoneId ? `?zone_id=${currentZoneId}` : ''}`),
        fetch(`${SIM_API}/income-os/scenario/${userId}${currentZoneId ? `?zone_id=${currentZoneId}` : ''}`),
        fetch(`${SIM_API}/income-os/suggestion/${userId}${currentZoneId ? `?zone_id=${currentZoneId}` : ''}`),
      ])
      if (fRes.ok)  setForecast(await fRes.json())
      if (sRes.ok)  setScenario(await sRes.json())
      if (suRes.ok) setSuggestion(await suRes.json())
      setLastRefresh(new Date())
    } catch (_) {}
    setLoading(false)
  }, [userId, currentZoneId])

  // Initial load + zone scores poll every 10s
  useEffect(() => {
    fetchAll()
    fetchZones()
    const id = setInterval(fetchZones, 10000)
    return () => clearInterval(id)
  }, [fetchAll, fetchZones])

  // Auto-refresh forecast every 5s if WS data stale
  useEffect(() => {
    const id = setInterval(() => {
      if (!myWorker?.income_os) fetchAll()
    }, 5000)
    return () => clearInterval(id)
  }, [myWorker?.income_os, fetchAll])

  // Derive values
  const next1h    = forecast?.next_1_hour_income ?? 0
  const nextShift = forecast?.next_shift_income  ?? 0
  const confidence = forecast?.confidence_score  ?? 0
  const trend      = forecast?.trend             ?? 'FLAT'
  const riskLevel  = forecast?.risk_level        ?? 'MODERATE'

  const bestOption  = scenario?.best_option  ?? 'STAY'
  const incomeDelta = scenario?.income_delta ?? 0
  const stayIncome  = scenario?.stay?.income_per_hour ?? 0
  const moveIncome  = scenario?.move?.income_per_hour ?? 0

  const aiMsg      = suggestion?.message     ?? ''
  const aiPriority = suggestion?.priority    ?? 'INFO'
  const aiAction   = suggestion?.action_type ?? 'STAY'

  const bestZone = zones[0]

  // Color helpers
  const zoneStateColor = { GREEN: 'text-emerald-400', YELLOW: 'text-amber-400', RED: 'text-red-400' }
  const zoneStateBg    = { GREEN: 'bg-emerald-500/10 border-emerald-500/20', YELLOW: 'bg-amber-500/10 border-amber-500/20', RED: 'bg-red-500/10 border-red-500/20' }

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">

      {/* ── Header ────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2">
            <span className="w-8 h-8 rounded-xl bg-violet-500/20 border border-violet-500/30 flex items-center justify-center">
              <Brain className="w-4 h-4 text-violet-400" />
            </span>
            Income OS
            <span className="text-[10px] font-bold bg-violet-500/20 text-violet-400 border border-violet-500/30 px-2 py-0.5 rounded-full ml-1">AI-POWERED</span>
          </h1>
          <p className="text-xs text-slate-500 mt-0.5 ml-10">Real-time income intelligence — forecast, compare, decide, guarantee.</p>
        </div>

        <div className="flex items-center gap-3">
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-bold ${zoneStateBg[currentZoneState] || zoneStateBg.GREEN}`}>
            <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: currentZoneState === 'GREEN' ? '#10b981' : currentZoneState === 'YELLOW' ? '#f59e0b' : '#ef4444' }} />
            <span className={zoneStateColor[currentZoneState] || 'text-emerald-400'}>Zone {currentZoneId || '—'}</span>
          </div>
          <button
            onClick={() => { fetchAll(); fetchZones() }}
            disabled={loading}
            className="w-8 h-8 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-slate-500 hover:text-white transition-all"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </motion.div>

      {/* ── Row 1: Forecast + Scenario ─────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        {/* 📈 Income Forecast */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="glass rounded-2xl p-5 shadow-card"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500 flex items-center gap-2">
              <TrendingUp className="w-3.5 h-3.5 text-violet-400" /> Income Forecast
            </h3>
            <div className="flex items-center gap-2">
              <TrendIcon trend={trend} />
              <PriorityBadge priority={riskLevel === 'HIGH' ? 'HIGH' : riskLevel === 'LOW' ? 'INFO' : 'MEDIUM'} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 mb-4">
            {/* Next 1H */}
            <div className="bg-white/3 rounded-xl p-4 border border-white/5 text-center relative overflow-hidden group">
              <div className="absolute inset-0 bg-violet-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
              <p className="text-[9px] uppercase tracking-widest text-slate-600 font-bold mb-1 flex items-center justify-center gap-1">
                <Clock className="w-2.5 h-2.5" /> Next 1 Hour
              </p>
              {loading ? (
                <div className="h-8 bg-white/5 rounded animate-pulse w-20 mx-auto" />
              ) : (
                <AnimatedNumber value={next1h} prefix="₹" className="text-3xl font-black text-white" />
              )}
              <p className="text-[9px] text-slate-600 mt-1">estimated</p>
            </div>

            {/* Next Shift */}
            <div className="bg-white/3 rounded-xl p-4 border border-white/5 text-center relative overflow-hidden group">
              <div className="absolute inset-0 bg-emerald-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
              <p className="text-[9px] uppercase tracking-widest text-slate-600 font-bold mb-1 flex items-center justify-center gap-1">
                <Activity className="w-2.5 h-2.5" /> Next Shift
              </p>
              {loading ? (
                <div className="h-8 bg-white/5 rounded animate-pulse w-24 mx-auto" />
              ) : (
                <AnimatedNumber value={nextShift} prefix="₹" className="text-3xl font-black text-emerald-400" />
              )}
              <p className="text-[9px] text-slate-600 mt-1">4-hour window</p>
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-[10px] uppercase tracking-wider text-slate-600 font-bold">Forecast Confidence</p>
            <ConfidenceMeter score={confidence} />
          </div>

          <div className="mt-3 grid grid-cols-3 gap-2">
            {[
              { label: 'Risk', value: riskLevel },
              { label: 'Zone', value: forecast?.zone_state || '—' },
              { label: 'Efficiency', value: `${Math.round((forecast?.efficiency_factor || 0.8) * 100)}%` },
            ].map(item => (
              <div key={item.label} className="text-center bg-white/2 rounded-lg p-2 border border-white/5">
                <p className="text-[8px] text-slate-600 uppercase tracking-wider mb-0.5">{item.label}</p>
                <p className={`text-xs font-bold ${
                  item.value === 'HIGH' || item.value === 'RED' ? 'text-red-400' :
                  item.value === 'MODERATE' || item.value === 'YELLOW' ? 'text-amber-400' :
                  'text-emerald-400'
                }`}>{item.value}</p>
              </div>
            ))}
          </div>
        </motion.div>

        {/* ⚖️ Scenario Comparison */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="glass rounded-2xl p-5 shadow-card"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500 flex items-center gap-2">
              <BarChart2 className="w-3.5 h-3.5 text-violet-400" /> Scenario Comparison
            </h3>
            <motion.div
              animate={{ scale: [1, 1.05, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
              className={`text-[9px] font-black px-3 py-1 rounded-full border ${
                bestOption === 'MOVE'
                  ? 'bg-amber-500/20 text-amber-400 border-amber-500/40'
                  : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
              }`}
            >
              {bestOption === 'MOVE' ? '⚡ MOVE RECOMMENDED' : '✅ STAY OPTIMAL'}
            </motion.div>
          </div>

          <div className="grid grid-cols-2 gap-3 mb-4">
            {/* Stay */}
            <div className={`rounded-xl p-4 border transition-all ${bestOption === 'STAY' ? 'bg-emerald-500/10 border-emerald-500/30 shadow-[0_0_20px_rgba(16,185,129,0.1)]' : 'bg-white/3 border-white/5 opacity-60'}`}>
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle className={`w-4 h-4 ${bestOption === 'STAY' ? 'text-emerald-400' : 'text-slate-600'}`} />
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Stay</p>
                {bestOption === 'STAY' && <span className="ml-auto text-[8px] bg-emerald-500/20 text-emerald-400 px-1.5 py-0.5 rounded-full font-black">BEST</span>}
              </div>
              <p className="text-xs text-slate-500 mb-1 truncate">{scenario?.stay?.zone_name || '—'}</p>
              {loading ? (
                <div className="h-7 bg-white/5 rounded animate-pulse w-16" />
              ) : (
                <AnimatedNumber value={stayIncome} prefix="₹" suffix="/hr" className={`text-2xl font-black ${bestOption === 'STAY' ? 'text-emerald-400' : 'text-slate-300'}`} />
              )}
            </div>

            {/* Move */}
            <div className={`rounded-xl p-4 border transition-all ${bestOption === 'MOVE' ? 'bg-amber-500/10 border-amber-500/30 shadow-[0_0_20px_rgba(245,158,11,0.1)]' : 'bg-white/3 border-white/5 opacity-60'}`}>
              <div className="flex items-center gap-2 mb-2">
                <Navigation className={`w-4 h-4 ${bestOption === 'MOVE' ? 'text-amber-400' : 'text-slate-600'}`} />
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Move</p>
                {bestOption === 'MOVE' && <span className="ml-auto text-[8px] bg-amber-500/20 text-amber-400 px-1.5 py-0.5 rounded-full font-black">BEST</span>}
              </div>
              <p className="text-xs text-slate-500 mb-1 truncate">{scenario?.move?.zone_name || '—'}</p>
              {loading ? (
                <div className="h-7 bg-white/5 rounded animate-pulse w-16" />
              ) : (
                <AnimatedNumber value={moveIncome} prefix="₹" suffix="/hr" className={`text-2xl font-black ${bestOption === 'MOVE' ? 'text-amber-400' : 'text-slate-300'}`} />
              )}
              {scenario?.move?.distance_km > 0 && (
                <p className="text-[9px] text-slate-600 mt-0.5">{scenario.move.distance_km} km away</p>
              )}
            </div>
          </div>

          {incomeDelta > 0 && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className={`flex items-center gap-2 px-4 py-3 rounded-xl border ${bestOption === 'MOVE' ? 'bg-amber-500/10 border-amber-500/25' : 'bg-white/3 border-white/5'}`}
            >
              {bestOption === 'MOVE' ? <ChevronUp className="w-4 h-4 text-amber-400" /> : <CheckCircle className="w-4 h-4 text-emerald-400" />}
              <p className="text-xs text-slate-300 flex-1">
                {bestOption === 'MOVE'
                  ? <><span className="font-black text-amber-400">₹{incomeDelta} more/hr</span> by moving to {scenario?.move?.zone_name}</>
                  : <><span className="font-black text-emerald-400">+₹{incomeDelta}/hr advantage</span> staying in current zone</>
                }
              </p>
            </motion.div>
          )}
        </motion.div>
      </div>

      {/* ── Row 2: AI Suggestion + Zone Rankings ─────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">

        {/* 🧠 AI Suggestion */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="lg:col-span-2 glass rounded-2xl p-5 shadow-card"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500 flex items-center gap-2">
              <Brain className="w-3.5 h-3.5 text-violet-400" /> AI Decision
            </h3>
            <PriorityBadge priority={aiPriority} />
          </div>

          {/* Big suggestion card */}
          <AnimatePresence mode="wait">
            <motion.div
              key={aiMsg}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.3 }}
              className={`p-4 rounded-xl border mb-4 ${
                aiAction === 'STAY' || aiAction === 'INFO' ? 'bg-emerald-500/8 border-emerald-500/20' :
                aiAction === 'MOVE' || aiAction === 'OPTIONAL_MOVE' ? 'bg-amber-500/8 border-amber-500/20' :
                aiAction === 'EVACUATE' || aiAction === 'CRITICAL' ? 'bg-red-500/10 border-red-500/30 animate-pulse' :
                'bg-white/3 border-white/8'
              }`}
            >
              {loading ? (
                <div className="space-y-2">
                  <div className="h-4 bg-white/5 rounded animate-pulse" />
                  <div className="h-4 bg-white/5 rounded animate-pulse w-3/4" />
                </div>
              ) : (
                <p className="text-sm text-slate-200 leading-relaxed font-medium">{aiMsg}</p>
              )}
            </motion.div>
          </AnimatePresence>

          {/* Action metrics */}
          {suggestion && (
            <div className="grid grid-cols-2 gap-2">
              <div className="bg-white/2 rounded-lg p-3 border border-white/5">
                <p className="text-[9px] text-slate-600 uppercase tracking-wider mb-1">Action</p>
                <p className="text-xs font-bold text-white">{aiAction.replace('_', ' ')}</p>
              </div>
              <div className="bg-white/2 rounded-lg p-3 border border-white/5">
                <p className="text-[9px] text-slate-600 uppercase tracking-wider mb-1">Uplift</p>
                <p className={`text-xs font-bold ${incomeDelta > 0 ? 'text-emerald-400' : 'text-slate-400'}`}>
                  {incomeDelta > 0 ? `+₹${incomeDelta}/hr` : 'None'}
                </p>
              </div>
              <div className="bg-white/2 rounded-lg p-3 border border-white/5">
                <p className="text-[9px] text-slate-600 uppercase tracking-wider mb-1">Distance</p>
                <p className="text-xs font-bold text-white">
                  {suggestion.distance_km > 0 ? `${suggestion.distance_km} km` : 'N/A'}
                </p>
              </div>
              <div className="bg-white/2 rounded-lg p-3 border border-white/5">
                <p className="text-[9px] text-slate-600 uppercase tracking-wider mb-1">Confidence</p>
                <p className={`text-xs font-bold ${confidence >= 0.7 ? 'text-emerald-400' : confidence >= 0.45 ? 'text-amber-400' : 'text-red-400'}`}>
                  {Math.round(confidence * 100)}%
                </p>
              </div>
            </div>
          )}
        </motion.div>

        {/* 🗺️ Zone Rankings */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="lg:col-span-3 glass rounded-2xl p-5 shadow-card"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500 flex items-center gap-2">
              <MapPin className="w-3.5 h-3.5 text-violet-400" /> Zone Rankings
            </h3>
            {bestZone && (
              <div className="flex items-center gap-1.5 text-[10px] text-emerald-400 font-bold">
                <Star className="w-3 h-3" />
                {bestZone.name} is best
              </div>
            )}
          </div>

          <div className="space-y-2 max-h-[360px] overflow-y-auto custom-scrollbar pr-1">
            {zones.length === 0 ? (
              <div className="space-y-2">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="h-14 bg-white/3 rounded-xl animate-pulse" />
                ))}
              </div>
            ) : (
              zones.map((zone, i) => <ZoneRankRow key={zone.zone_id} zone={zone} index={i} />)
            )}
          </div>
        </motion.div>
      </div>

      {/* ── Row 3: Guaranteed Income Mode ─────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
        className="glass rounded-2xl p-5 shadow-card"
      >
        <div className="flex items-center gap-3 mb-5">
          <div className="w-9 h-9 rounded-xl bg-violet-500/15 border border-violet-500/25 flex items-center justify-center">
            <DollarSign className="w-4.5 h-4.5 text-violet-400" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              💰 Guaranteed Income Mode
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">Set a minimum shift income. We pay the shortfall if disruption hits your earnings.</p>
          </div>
        </div>

        <GuaranteePanel
          userId={userId}
          currentZoneState={currentZoneState}
          onGuaranteePayout={setGuaranteePayout}
        />
      </motion.div>

      {/* ── Demo CTA Banner ─────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
        className="glass rounded-2xl p-5 border border-violet-500/20 bg-violet-500/5 flex items-center gap-4"
      >
        <div className="w-10 h-10 rounded-xl bg-violet-500/20 flex items-center justify-center flex-shrink-0">
          <Zap className="w-5 h-5 text-violet-400" />
        </div>
        <div className="flex-1">
          <p className="text-sm font-bold text-white">Demo Flow: Watch Income OS in Action</p>
          <p className="text-xs text-slate-500 mt-0.5">
            Trigger a disruption from <strong className="text-slate-300">Mission Control</strong> → watch the forecast drop → see AI recommend a move → enable Guarantee mode → see the payout trigger.
          </p>
        </div>
        <ArrowRight className="w-5 h-5 text-violet-400 flex-shrink-0" />
      </motion.div>

    </div>
  )
}

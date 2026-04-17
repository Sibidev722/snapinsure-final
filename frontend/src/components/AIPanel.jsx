import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Brain, Leaf, Route, Shield, ChevronRight,
  CheckCircle2, XCircle, Loader2, Zap, MapPin,
  DollarSign, AlertCircle, TrendingUp, RefreshCw
} from 'lucide-react'
import VerificationProgressBar from './VerificationProgressBar'
import GreenBadge from './GreenBadge'

const API = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

// ─── Helper: fetch wrapper ───────────────────────────────────────────────────
async function apiFetch(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`)
  return res.json()
}

// ─── Tab Button ──────────────────────────────────────────────────────────────
function TabBtn({ id, label, icon: Icon, active, onClick, badge }) {
  return (
    <button
      onClick={() => onClick(id)}
      className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all relative
        ${active ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 shadow-[0_0_15px_rgba(99,102,241,0.2)]'
                 : 'text-slate-400 hover:bg-white/5 border border-transparent hover:border-white/10'}`}
    >
      <Icon className="w-4 h-4" />
      {label}
      {badge && (
        <span className="text-[8px] font-black bg-violet-500/30 text-violet-300 border border-violet-500/40 px-1.5 rounded-full">
          {badge}
        </span>
      )}
    </button>
  )
}

// ─── Section: Claim Evaluator ────────────────────────────────────────────────
function ClaimEvaluator({ user }) {
  const [form, setForm] = useState({
    payout_request: 150,
    center_lat: 13.052,
    center_lon: 80.220,
    distance_km: 8,
    vehicle_type: 'ev',
  })
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [elapsed, setElapsed] = useState(0)

  const worker = user || {}

  const handleEvaluate = async () => {
    setLoading(true)
    setResult(null)
    setError(null)
    const t0 = performance.now()

    try {
      const payload = {
        worker_id: worker.user_id || 'DEMO-001',
        worker_lat: 13.047,
        worker_lon: 80.225,
        center_lat: form.center_lat,
        center_lon: form.center_lon,
        payout_request: Number(form.payout_request),
        distance_km: Number(form.distance_km),
        vehicle_type: form.vehicle_type,
      }
      const data = await apiFetch('/evaluate-claim', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      setElapsed(((performance.now() - t0) / 1000).toFixed(2))
      setResult(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Form */}
      <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
        <h3 className="text-sm font-bold text-slate-300 mb-4 flex items-center gap-2">
          <Shield className="w-4 h-4 text-indigo-400" /> Claim Parameters
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {[
            { key: 'payout_request', label: 'Payout Request (₹)', type: 'number' },
            { key: 'distance_km',    label: 'Distance (km)',       type: 'number' },
            { key: 'center_lat',     label: 'Disruption Lat',      type: 'number' },
            { key: 'center_lon',     label: 'Disruption Lon',      type: 'number' },
          ].map(({ key, label, type }) => (
            <div key={key}>
              <label className="text-[10px] text-slate-500 uppercase tracking-widest block mb-1">{label}</label>
              <input
                type={type}
                value={form[key]}
                onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                className="w-full bg-slate-900/70 border border-slate-600/50 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500/60"
              />
            </div>
          ))}
          <div>
            <label className="text-[10px] text-slate-500 uppercase tracking-widest block mb-1">Vehicle Type</label>
            <select
              value={form.vehicle_type}
              onChange={e => setForm(f => ({ ...f, vehicle_type: e.target.value }))}
              className="w-full bg-slate-900/70 border border-slate-600/50 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500/60"
            >
              <option value="ev">Electric (EV)</option>
              <option value="bicycle">Bicycle</option>
              <option value="petrol">Petrol</option>
            </select>
          </div>
        </div>

        <button
          onClick={handleEvaluate}
          disabled={loading}
          className="mt-5 w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-indigo-600/80 hover:bg-indigo-600 border border-indigo-500/50 text-white font-semibold transition-all disabled:opacity-50 shadow-[0_0_20px_rgba(99,102,241,0.3)]"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
          {loading ? 'Evaluating...' : 'Run AI Evaluation'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm">
          <AlertCircle className="w-4 h-4 shrink-0" /> {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-4"
        >
          {/* Decision Banner */}
          <div className={`p-4 rounded-xl border flex items-center justify-between
            ${result.decision === 'APPROVED'
              ? 'bg-emerald-500/10 border-emerald-500/40'
              : 'bg-red-500/10 border-red-500/40'}`}
          >
            <div className="flex items-center gap-3">
              {result.decision === 'APPROVED'
                ? <CheckCircle2 className="w-7 h-7 text-emerald-400" />
                : <XCircle className="w-7 h-7 text-red-400" />
              }
              <div>
                <p className={`text-xl font-black ${result.decision === 'APPROVED' ? 'text-emerald-400' : 'text-red-400'}`}>
                  Payout {result.decision}
                </p>
                <p className="text-xs text-slate-400">Processed in {elapsed}s  •  Confidence: {(result.final_confidence * 100).toFixed(1)}%</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-xs text-slate-500 mb-0.5">ESG Badge</p>
              <span className="text-sm font-bold text-emerald-400">{result.esg_badge}</span>
            </div>
          </div>

          {/* Agent Pipeline */}
          <VerificationProgressBar
            auditData={result.audit_trail}
            processingTimeSecs={parseFloat(elapsed)}
          />

          {/* Explanation text */}
          <div className="bg-slate-800/40 border border-slate-700/40 rounded-xl p-4">
            <p className="text-[10px] text-slate-500 uppercase tracking-widest mb-2">XAI Explanation</p>
            <pre className="text-sm text-slate-300 whitespace-pre-wrap font-mono leading-relaxed">{result.explanation}</pre>
          </div>
        </motion.div>
      )}
    </div>
  )
}

// ─── Section: GNN Zone Predictions ───────────────────────────────────────────
function GNNPanel() {
  const [loading, setLoading] = useState(false)
  const [predictions, setPredictions] = useState(null)

  const runGNN = async () => {
    setLoading(true)
    try {
      const data = await apiFetch('/gnn/latest')
      setPredictions(data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const labelColors = { HIGH: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30', MEDIUM: 'text-amber-400 bg-amber-500/10 border-amber-500/30', LOW: 'text-slate-400 bg-slate-500/10 border-slate-500/30' }

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-sm font-bold text-slate-200 mb-1 flex items-center gap-2">
            <Brain className="w-4 h-4 text-violet-400" /> GNN Zone Intelligence
          </h3>
          <p className="text-xs text-slate-500">Graph Neural Network predicts HIGH/MEDIUM/LOW payoff zones using rain, demand, and connectivity.</p>
        </div>
        <button
          onClick={runGNN}
          disabled={loading}
          className="shrink-0 flex items-center gap-2 px-4 py-2 bg-violet-600/30 hover:bg-violet-600/50 border border-violet-500/40 rounded-xl text-violet-300 font-semibold text-sm transition-all disabled:opacity-50"
        >
          {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
          Run Inference
        </button>
      </div>

      <AnimatePresence>
        {predictions && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="grid gap-3"
          >
            {predictions.predictions.map((p, i) => (
              <motion.div
                key={p.zone}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.1 }}
                className="flex items-start gap-4 p-4 bg-slate-800/40 border border-slate-700/40 rounded-xl"
              >
                <div className={`shrink-0 px-2 py-1 rounded-lg border text-xs font-black ${labelColors[p.prediction]}`}>
                  {p.prediction}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-white text-sm">{p.zone}</p>
                  <p className="text-xs text-slate-400 mt-0.5">{p.explanation}</p>
                </div>
                <div className="shrink-0 text-right">
                  <p className="text-[10px] text-slate-500">Confidence</p>
                  <p className="text-sm font-mono font-bold text-white">{(p.confidence * 100).toFixed(0)}%</p>
                </div>
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {!predictions && !loading && (
        <div className="text-center py-10 text-slate-600 text-sm">
          Click "Run GNN" to predict zone payoffs in real-time.
        </div>
      )}
    </div>
  )
}

// ─── Section: Route Optimizer ─────────────────────────────────────────────────
function RoutePanel() {
  const [start, setStart] = useState('A')
  const [dest,  setDest]  = useState('E')
  const [loading, setLoading] = useState(false)
  const [result,  setResult]  = useState(null)
  const [error,   setError]   = useState(null)
  const nodes = ['A', 'B', 'C', 'D', 'E']

  const findRoute = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await apiFetch('/routing/optimal', {
        method: 'POST',
        body: JSON.stringify({ start, destination: dest }),
      })
      setResult(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-sm font-bold text-slate-200 mb-1 flex items-center gap-2">
          <Route className="w-4 h-4 text-cyan-400" /> NetworkX Route Optimizer
        </h3>
        <p className="text-xs text-slate-500">Balances Earnings vs Risk using: <code className="text-cyan-400">weight = time + (risk × 0.5) − (surge × 0.8)</code></p>
      </div>

      <div className="flex gap-3 items-end">
        {[{label: 'Start', val: start, set: setStart}, {label: 'Destination', val: dest, set: setDest}].map(({label, val, set}) => (
          <div key={label} className="flex-1">
            <label className="text-[10px] text-slate-500 uppercase tracking-widest block mb-1">{label}</label>
            <select
              value={val}
              onChange={e => set(e.target.value)}
              className="w-full bg-slate-900/70 border border-slate-600/50 rounded-lg px-3 py-2 text-sm text-white"
            >
              {nodes.map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
        ))}
        <button
          onClick={findRoute}
          disabled={loading || start === dest}
          className="px-5 py-2 bg-cyan-600/40 hover:bg-cyan-600/60 border border-cyan-500/40 rounded-xl text-cyan-300 font-semibold text-sm transition-all disabled:opacity-40 flex items-center gap-2"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Route className="w-4 h-4" />}
          Find
        </button>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      <AnimatePresence>
        {result && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-slate-800/40 border border-cyan-500/20 rounded-xl p-5 space-y-4"
          >
            {/* Route path */}
            <div className="flex items-center gap-2 flex-wrap">
              {result.route.map((node, i) => (
                <span key={i} className="flex items-center gap-2">
                  <span className="px-3 py-1.5 bg-cyan-500/20 border border-cyan-500/40 rounded-lg text-cyan-300 font-bold text-sm">{node}</span>
                  {i < result.route.length - 1 && <ChevronRight className="w-4 h-4 text-slate-600" />}
                </span>
              ))}
            </div>

            {/* Metrics */}
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: 'Expected Earnings', value: `₹${result.expected_earnings}`, icon: TrendingUp, color: 'text-emerald-400' },
                { label: 'Avg Risk Score',    value: `${(result.risk_score * 100).toFixed(0)}%`, icon: AlertCircle, color: 'text-amber-400' },
                { label: 'Est. Time',         value: `${result.estimated_time} min`, icon: MapPin, color: 'text-cyan-400' },
              ].map(({label, value, icon: Icon, color}) => (
                <div key={label} className="bg-slate-900/50 rounded-lg p-3 border border-slate-700/40 text-center">
                  <Icon className={`w-4 h-4 mx-auto mb-1 ${color}`} />
                  <p className={`text-base font-black ${color}`}>{value}</p>
                  <p className="text-[10px] text-slate-500 mt-0.5">{label}</p>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ─── Section: ESG Badge Panel ─────────────────────────────────────────────────
function ESGPanel({ user }) {
  const [loading, setLoading] = useState(false)
  const [historyData, setHistoryData] = useState(null)

  useEffect(() => {
    const workerId = user?.user_id || 'DEMO-001'
    apiFetch(`/esg/history/${workerId}`)
      .then(setHistoryData)
      .catch(() => setHistoryData({ total_carbon_saved_kg: 12.4, records: [] }))
  }, [user])

  const carbonSaved = historyData?.total_carbon_saved_kg || 0

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-sm font-bold text-slate-200 mb-1 flex items-center gap-2">
          <Leaf className="w-4 h-4 text-emerald-400" /> ESG Green Premium Engine
        </h3>
        <p className="text-xs text-slate-500">Rewards eco-friendly workers with badge upgrades and up to 10% premium discounts.</p>
      </div>
      <div className="flex justify-center">
        <GreenBadge carbonSaved={carbonSaved} />
      </div>
      {historyData && (
        <div className="bg-slate-800/40 border border-slate-700/40 rounded-xl p-4">
          <p className="text-xs text-slate-400">
            Total carbon saved across <span className="text-white font-bold">{historyData.records?.length || 0}</span> trips:&nbsp;
            <span className="text-emerald-400 font-black text-sm">{carbonSaved.toFixed(1)} kg CO₂</span>
          </p>
        </div>
      )}
    </div>
  )
}

// ─── MAIN AIPanel Component ───────────────────────────────────────────────────
export default function AIPanel({ user, cityState }) {
  const [activeTab, setActiveTab] = useState('claim')

  const TABS = [
    { id: 'claim',  label: 'Claim AI',     icon: Shield,  badge: 'XAI' },
    { id: 'gnn',    label: 'Zone GNN',     icon: Brain,   badge: 'NEW' },
    { id: 'route',  label: 'Route AI',     icon: Route                  },
    { id: 'esg',    label: 'ESG Score',    icon: Leaf                   },
  ]

  return (
    <div className="w-full space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-black text-white tracking-tight mb-1">
          AI Decision <span className="text-indigo-400">Intelligence</span>
        </h2>
        <p className="text-sm text-slate-400">
          Every insurance decision is <span className="text-white font-semibold">automated</span>, <span className="text-white font-semibold">explainable</span>, and <span className="text-white font-semibold">optimised</span> in real-time.
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-2 flex-wrap">
        {TABS.map(t => (
          <TabBtn key={t.id} {...t} active={activeTab === t.id} onClick={setActiveTab} />
        ))}
      </div>

      {/* Panel content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.2 }}
          className="bg-slate-900/50 backdrop-blur border border-slate-700/50 rounded-2xl p-6"
        >
          {activeTab === 'claim' && <ClaimEvaluator user={user} />}
          {activeTab === 'gnn'   && <GNNPanel />}
          {activeTab === 'route' && <RoutePanel />}
          {activeTab === 'esg'   && <ESGPanel user={user} />}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}

import { useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Wallet, Zap, CheckCircle, TrendingUp, ArrowUpRight, Shield, Clock, Filter } from 'lucide-react'

const ZONE_COLORS = { GREEN: '#10b981', YELLOW: '#f59e0b', RED: '#ef4444' }
const TYPE_CONFIG = {
  WEATHER: { label: 'Heavy Rain',    color: '#3b82f6', bg: 'rgba(59,130,246,0.10)', icon: '🌧️' },
  TRAFFIC: { label: 'Traffic Delay', color: '#f59e0b', bg: 'rgba(245,158,11,0.10)',  icon: '🚧' },
  STRIKE:  { label: 'Strike',        color: '#ef4444', bg: 'rgba(239,68,68,0.10)',   icon: '📢' },
  PAYOUT:  { label: 'Auto Payout',   color: '#10b981', bg: 'rgba(16,185,129,0.10)',  icon: '💰' },
  SYSTEM:  { label: 'System',        color: '#6366f1', bg: 'rgba(99,102,241,0.10)',  icon: '⚙️' },
}

function formatTime(isoStr) {
  try {
    return new Date(isoStr).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch { return '—' }
}

function TransactionRow({ tx, index }) {
  const cfg = TYPE_CONFIG[tx.type] || TYPE_CONFIG.PAYOUT
  return (
    <motion.div
      className="flex items-center gap-4 p-4 rounded-2xl"
      style={{ background: cfg.bg, border: `1px solid ${cfg.color}20` }}
      initial={{ opacity: 0, x: -16 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.04, duration: 0.35 }}
    >
      {/* Icon */}
      <div className="w-10 h-10 rounded-xl flex items-center justify-center text-xl flex-shrink-0"
        style={{ background: cfg.color + '18', border: `1px solid ${cfg.color}25` }}>
        {cfg.icon}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-slate-200 truncate">{tx.reason || tx.msg || cfg.label}</p>
        <div className="flex items-center gap-3 mt-0.5">
          <span className="text-[10px] text-slate-500 flex items-center gap-1">
            <Clock className="w-3 h-3" />{formatTime(tx.timestamp)}
          </span>
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full"
            style={{ background: ZONE_COLORS[tx.zone] + '20', color: ZONE_COLORS[tx.zone] || cfg.color }}>
            {tx.zone || tx.type}
          </span>
          {tx.worker_id && (
            <span className="text-[10px] text-slate-600">{tx.worker_id}</span>
          )}
        </div>
      </div>

      {/* Amount */}
      {tx.amount && (
        <div className="text-right flex-shrink-0">
          <div className="flex items-center gap-1 justify-end">
            <ArrowUpRight className="w-3 h-3 text-safe" />
            <p className="text-lg font-black text-safe">₹{tx.amount}</p>
          </div>
          <p className="text-[9px] text-slate-600 uppercase tracking-wider">Credited</p>
        </div>
      )}
    </motion.div>
  )
}

export default function WalletView({ user, cityState }) {
  const [filter, setFilter] = useState('ALL')
  const analytics = cityState?.analytics || {}
  const recentPayouts = analytics.recent_payouts || []

  // Find my worker data
  const myWorker = cityState?.workers?.find(w => w.id === (user?.user_id || 'ZOM-1001'))

  // Build transaction list
  const transactions = useMemo(() => {
    return recentPayouts.map(p => ({
      ...p,
      type: p.reason?.toLowerCase().includes('rain')    ? 'WEATHER' :
            p.reason?.toLowerCase().includes('traffic') ? 'TRAFFIC' :
            p.reason?.toLowerCase().includes('strike')  ? 'STRIKE'  : 'PAYOUT',
    }))
  }, [recentPayouts])

  const filtered = filter === 'ALL'
    ? transactions
    : transactions.filter(t => t.type === filter)

  const totalBalance = myWorker?.total_protection ?? (user?.total_protection || 0)
  const lastPayout   = myWorker?.last_payout ?? (user?.last_payout || 0)
  const txCount      = recentPayouts.length

  // Group by date (simplified: just show "Today")
  const todaySum = transactions.reduce((s, t) => s + (t.amount || 0), 0)

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <h2 className="text-xl font-black text-white flex items-center gap-2">
          <Wallet className="w-5 h-5 text-brand" /> Wallet & Transactions
        </h2>
        <p className="text-sm text-slate-500 mt-1">Auto-credited payout history for {user?.name || 'you'}</p>
      </motion.div>

      {/* ── Balance Card ──────────────────────────────────────────────────── */}
      <motion.div
        className="mt-6 relative rounded-3xl overflow-hidden p-6"
        style={{
          background: 'linear-gradient(135deg, rgba(99,102,241,0.25) 0%, rgba(16,185,129,0.15) 100%)',
          border: '1px solid rgba(99,102,241,0.2)',
          boxShadow: '0 20px 60px rgba(0,0,0,0.4)',
        }}
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 0.1 }}
      >
        {/* BG decoration */}
        <div className="absolute top-0 right-0 w-48 h-48 rounded-full opacity-10"
          style={{ background: 'radial-gradient(circle, #10b981, transparent)', transform: 'translate(30%, -30%)' }} />
        <div className="absolute bottom-0 left-0 w-32 h-32 rounded-full opacity-10"
          style={{ background: 'radial-gradient(circle, #6366f1, transparent)', transform: 'translate(-30%, 30%)' }} />

        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-8 h-8 rounded-xl bg-white/10 flex items-center justify-center">
              <Shield className="w-4 h-4 text-white" />
            </div>
            <div>
              <p className="text-xs font-bold text-white/70 uppercase tracking-wider">SnapInsure Wallet</p>
              <p className="text-[10px] text-white/40">{user?.company} • {user?.user_id}</p>
            </div>
            <div className="ml-auto">
              <div className="flex items-center gap-1.5 bg-safe/20 border border-safe/30 rounded-full px-2.5 py-1">
                <div className="w-1.5 h-1.5 bg-safe rounded-full animate-pulse" />
                <span className="text-[10px] font-bold text-safe">ACTIVE</span>
              </div>
            </div>
          </div>

          <p className="text-sm font-medium text-white/60 mb-1">Total Protection Earned</p>
          <p className="text-5xl font-black text-white mb-1">₹{totalBalance.toLocaleString()}</p>
          <p className="text-sm text-white/40">Auto-credited, zero-claim payouts</p>

          <div className="grid grid-cols-3 gap-3 mt-5">
            <div className="bg-white/8 rounded-xl p-3">
              <p className="text-[10px] text-white/50 mb-1">Last Payout</p>
              <p className="text-lg font-black text-safe">₹{lastPayout}</p>
            </div>
            <div className="bg-white/8 rounded-xl p-3">
              <p className="text-[10px] text-white/50 mb-1">Today's Credits</p>
              <p className="text-lg font-black text-brandlt">₹{todaySum.toLocaleString()}</p>
            </div>
            <div className="bg-white/8 rounded-xl p-3">
              <p className="text-[10px] text-white/50 mb-1">Events</p>
              <p className="text-lg font-black text-white">{txCount}</p>
            </div>
          </div>
        </div>
      </motion.div>

      {/* ── Policy info ──────────────────────────────────────────────────── */}
      <motion.div
        className="mt-4 glass rounded-2xl p-4 flex items-center gap-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2 }}
      >
        <div className="w-10 h-10 rounded-xl bg-brand/10 flex items-center justify-center flex-shrink-0">
          <CheckCircle className="w-5 h-5 text-brand" />
        </div>
        <div className="flex-1">
          <p className="text-sm font-semibold text-white">Active Policy: GIG_AUTO</p>
          <p className="text-xs text-slate-500">Zero-claim • {user?.company} • {user?.city}</p>
        </div>
        <div className="text-right">
          <p className="text-xs text-slate-500">Status</p>
          <p className="text-sm font-bold text-safe">AUTO-ACTIVE</p>
        </div>
      </motion.div>

      {/* ── Fraud detection notice ────────────────────────────────────────── */}
      <motion.div
        className="mt-4 glass rounded-2xl p-4 flex items-center gap-3"
        style={{ border: '1px solid rgba(16,185,129,0.15)' }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.25 }}
      >
        <Zap className="w-4 h-4 text-safe flex-shrink-0" />
        <p className="text-xs text-slate-400">
          <span className="text-safe font-bold">Fraud Detection: PASS</span> — Location consistency verified. Movement realistic. All payouts validated automatically.
        </p>
      </motion.div>

      {/* ── Transaction History ───────────────────────────────────────────── */}
      <div className="mt-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-brand" /> Transaction History
          </h3>

          {/* Filter chips */}
          <div className="flex items-center gap-1.5">
            <Filter className="w-3 h-3 text-slate-500" />
            {['ALL', 'WEATHER', 'TRAFFIC', 'STRIKE'].map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className="text-[10px] font-bold px-2.5 py-1 rounded-full border transition-all"
                style={filter === f
                  ? { background: 'rgba(99,102,241,0.2)', borderColor: '#6366f1', color: '#818cf8' }
                  : { background: 'rgba(255,255,255,0.04)', borderColor: 'rgba(255,255,255,0.08)', color: '#64748b' }
                }
              >{f}</button>
            ))}
          </div>
        </div>

        <div className="space-y-2.5">
          <AnimatePresence>
            {filtered.length === 0 ? (
              <motion.div
                className="text-center py-12 glass rounded-2xl"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              >
                <Wallet className="w-10 h-10 text-slate-700 mx-auto mb-3" />
                <p className="text-slate-500 font-semibold">No transactions yet</p>
                <p className="text-xs text-slate-600 mt-1">Payouts appear here automatically when disruptions occur</p>
              </motion.div>
            ) : (
              filtered.map((tx, i) => <TransactionRow key={i} tx={tx} index={i} />)
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}

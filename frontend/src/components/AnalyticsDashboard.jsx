import { useMemo } from 'react'
import { motion } from 'framer-motion'
import { AreaChart, Area, BarChart, Bar, XAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { BarChart3, Zap, Activity, Users, TrendingUp, AlertTriangle, CheckCircle, Shield } from 'lucide-react'

const ZONE_COLORS   = { GREEN: '#10b981', YELLOW: '#f59e0b', RED: '#ef4444' }
const COMPANY_COLORS = { Zomato: '#E23744', Swiggy: '#FC8019', Uber: '#ffffff', Blinkit: '#F8C200' }

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="glass rounded-xl px-3 py-2 text-xs border border-white/10">
      <p className="text-slate-400 mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color || p.fill }} className="font-bold">
          {p.name}: {p.name?.includes('₹') || p.dataKey === 'amount' ? `₹${p.value}` : p.value}
        </p>
      ))}
    </div>
  )
}

function StatCard({ label, value, sub, icon: Icon, color = '#6366f1', delay = 0 }) {
  return (
    <motion.div
      className="glass rounded-2xl p-5 relative overflow-hidden"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
    >
      <div className="absolute top-0 right-0 w-24 h-24 rounded-full opacity-5"
        style={{ background: color, filter: 'blur(20px)', transform: 'translate(30%, -30%)' }} />
      <div className="flex items-start justify-between mb-3">
        <div className="w-9 h-9 rounded-xl flex items-center justify-center"
          style={{ background: color + '18', border: `1px solid ${color}25` }}>
          <Icon className="w-4 h-4" style={{ color }} />
        </div>
      </div>
      <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">{label}</p>
      <p className="text-3xl font-black text-white">{value}</p>
      {sub && <p className="text-xs text-slate-500 mt-0.5">{sub}</p>}
    </motion.div>
  )
}

export default function AnalyticsDashboard({ cityState }) {
  const zones   = cityState?.zones   || []
  const workers = cityState?.workers || []
  const analytics = cityState?.analytics || {}
  const recentPayouts = analytics.recent_payouts || []

  // ── Derived stats ──────────────────────────────────────────────────────────
  const totalPayout  = analytics.total_payout_today ?? 0
  const greenCount   = analytics.green_zones  ?? zones.filter(z => z.state === 'GREEN').length
  const yellowCount  = analytics.yellow_zones ?? zones.filter(z => z.state === 'YELLOW').length
  const redCount     = analytics.red_zones    ?? zones.filter(z => z.state === 'RED').length
  const avgRisk      = analytics.avg_risk ?? (zones.reduce((s, z) => s + (z.risk_score || 0), 0) / (zones.length || 1))
  const workersProtected = analytics.workers_protected ?? workers.length

  // ── Zone distribution for pie chart ───────────────────────────────────────
  const pieData = [
    { name: 'GREEN',  value: greenCount,  color: '#10b981' },
    { name: 'YELLOW', value: yellowCount, color: '#f59e0b' },
    { name: 'RED',    value: redCount,    color: '#ef4444' },
  ].filter(d => d.value > 0)

  // ── Worker stats table data ───────────────────────────────────────────────
  const workerRows = useMemo(() => workers.map(w => ({
    ...w,
    riskPct: zones.find(z => z.id === w.zone_id)?.risk_score ?? 0,
  })).sort((a, b) => b.riskPct - a.riskPct), [workers, zones])

  // ── Payout chart data ─────────────────────────────────────────────────────
  const payoutChartData = recentPayouts.slice(0, 8).reverse().map((p, i) => ({
    name: `#${i + 1}`,
    amount: p.amount,
    company: p.company,
  }))

  // ── Zone risk heatmap ─────────────────────────────────────────────────────
  const zoneRiskData = zones.map(z => ({
    name: z.name.split(' ')[0],
    risk: Math.round(z.risk_score * 100),
    fill: ZONE_COLORS[z.state] || '#10b981',
  }))

  // ── Company breakdown ─────────────────────────────────────────────────────
  const companyStats = useMemo(() => {
    const map = {}
    workers.forEach(w => {
      if (!map[w.company]) map[w.company] = { company: w.company, workers: 0, total_protection: 0, red: 0 }
      map[w.company].workers++
      map[w.company].total_protection += w.total_protection
      if (w.zone_state === 'RED') map[w.company].red++
    })
    return Object.values(map)
  }, [workers])

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <h2 className="text-xl font-black text-white flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-brand" /> Analytics Dashboard
        </h2>
        <p className="text-sm text-slate-500 mt-1">Real-time city-wide insurance intelligence</p>
      </motion.div>

      {/* ── KPI Cards ──────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Payouts Today" value={`₹${totalPayout.toLocaleString()}`} sub="Zero-claim, auto-credited" icon={Zap} color="#10b981" delay={0} />
        <StatCard label="Workers Protected" value={workersProtected} sub="Active policies" icon={Shield} color="#6366f1" delay={0.05} />
        <StatCard label="Active Disruptions" value={analytics.active_disruptions ?? 0} sub="Live incidents" icon={AlertTriangle} color="#ef4444" delay={0.1} />
        <StatCard label="Avg City Risk"
          value={`${(avgRisk * 100).toFixed(0)}%`}
          sub={avgRisk > 0.7 ? '🔴 Critical' : avgRisk > 0.4 ? '🟡 Moderate' : '🟢 Safe'}
          icon={Activity} color={avgRisk > 0.7 ? '#ef4444' : avgRisk > 0.4 ? '#f59e0b' : '#10b981'} delay={0.15} />
      </div>

      {/* ── Zone grid stats ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Zone distribution pie */}
        <motion.div className="glass rounded-2xl p-5" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }}>
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-4">Zone Distribution</p>
          <div className="flex items-center justify-center">
            <PieChart width={160} height={160}>
              <Pie data={pieData} cx="50%" cy="50%" innerRadius={45} outerRadius={70} paddingAngle={3} dataKey="value">
                {pieData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
              </Pie>
            </PieChart>
          </div>
          <div className="flex justify-center gap-4 mt-2">
            {pieData.map(d => (
              <div key={d.name} className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full" style={{ background: d.color }} />
                <span className="text-[10px] text-slate-400">{d.name}: {d.value}</span>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Zone risk barring */}
        <motion.div className="glass rounded-2xl p-5 lg:col-span-2" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.25 }}>
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-4">Risk Heatmap by Zone</p>
          <div className="h-36">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={zoneRiskData} margin={{ top: 0, right: 0, bottom: 0, left: -24 }}>
                <XAxis dataKey="name" tick={{ fontSize: 9, fill: '#475569' }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="risk" name="Risk %" radius={[4, 4, 0, 0]}>
                  {zoneRiskData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </motion.div>
      </div>

      {/* ── Payout history ───────────────────────────────────────────────────── */}
      {payoutChartData.length > 0 && (
        <motion.div className="glass rounded-2xl p-5" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}>
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-4 flex items-center gap-2">
            <Zap className="w-3 h-3 text-safe" /> Recent Auto-Payouts
          </p>
          <div className="h-32">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={payoutChartData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                <defs>
                  <linearGradient id="payGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="name" tick={{ fontSize: 9, fill: '#475569' }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="amount" name="₹ Payout" stroke="#10b981" strokeWidth={2} fill="url(#payGrad)" dot={{ fill: '#10b981', r: 3, strokeWidth: 0 }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Payout list */}
          <div className="mt-4 space-y-2 max-h-48 overflow-y-auto custom-scrollbar">
            {recentPayouts.slice(0, 8).map((p, i) => (
              <motion.div key={i}
                className="flex items-center gap-3 p-2.5 rounded-xl"
                style={{ background: 'rgba(16,185,129,0.05)', border: '1px solid rgba(16,185,129,0.12)' }}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
              >
                <div className="w-7 h-7 rounded-lg bg-safe/10 flex items-center justify-center flex-shrink-0">
                  <CheckCircle className="w-3.5 h-3.5 text-safe" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-semibold text-slate-200 truncate">{p.name} ({p.company})</p>
                  <p className="text-[10px] text-slate-500 truncate">{p.reason}</p>
                </div>
                <div className="text-right flex-shrink-0">
                  <p className="text-sm font-black text-safe">₹{p.amount}</p>
                  <p className="text-[9px] text-slate-600">{p.zone} zone</p>
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>
      )}

      {/* ── Company breakdown ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {companyStats.map((c, i) => (
          <motion.div key={c.company} className="glass rounded-2xl p-4"
            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 + i * 0.07 }}>
            <div className="w-8 h-8 rounded-lg mb-3 flex items-center justify-center"
              style={{ background: (COMPANY_COLORS[c.company] || '#6366f1') + '18' }}>
              <span className="text-lg">{c.company === 'Zomato' ? '🍕' : c.company === 'Swiggy' ? '🛵' : c.company === 'Uber' ? '🚗' : '⚡'}</span>
            </div>
            <p className="text-xs font-bold text-white">{c.company}</p>
            <p className="text-[10px] text-slate-500 mt-0.5">{c.workers} workers</p>
            <div className="mt-2 flex items-center gap-1.5">
              {c.red > 0 && <span className="text-[9px] font-bold text-danger">{c.red} in RED</span>}
              {c.red === 0 && <span className="text-[9px] font-bold text-safe">All safe</span>}
            </div>
            <p className="text-[10px] text-slate-500 mt-1">₹{c.total_protection.toLocaleString()} total</p>
          </motion.div>
        ))}
      </div>

      {/* ── Worker table ──────────────────────────────────────────────────── */}
      <motion.div className="glass rounded-2xl overflow-hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }}>
        <div className="p-4 border-b border-white/7 flex items-center gap-2">
          <Users className="w-4 h-4 text-brand" />
          <p className="text-sm font-bold text-white">All Workers</p>
          <span className="text-[10px] text-slate-500 ml-auto">Sorted by risk</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/5">
                {['Worker', 'Company', 'Zone', 'Status', 'Risk', 'Last Payout', 'Total Protected'].map(h => (
                  <th key={h} className="text-left px-4 py-2.5 text-[10px] font-bold uppercase tracking-wider text-slate-500">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {workerRows.map((w, i) => (
                <motion.tr key={w.id}
                  className="border-b border-white/4 hover:bg-white/3 transition-colors"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.4 + i * 0.025 }}
                >
                  <td className="px-4 py-2.5">
                    <p className="font-semibold text-slate-200">{w.name}</p>
                    <p className="text-[10px] text-slate-600">{w.id}</p>
                  </td>
                  <td className="px-4 py-2.5 text-slate-400">{w.company}</td>
                  <td className="px-4 py-2.5 text-slate-400">{w.zone_id}</td>
                  <td className="px-4 py-2.5">
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold"
                      style={{ background: ZONE_COLORS[w.zone_state] + '20', color: ZONE_COLORS[w.zone_state] }}>
                      {w.zone_state}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 rounded-full bg-white/8 overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${w.riskPct * 100}%`, background: ZONE_COLORS[w.zone_state] }} />
                      </div>
                      <span className="text-[10px] text-slate-400">{(w.riskPct * 100).toFixed(0)}%</span>
                    </div>
                  </td>
                  <td className="px-4 py-2.5 font-bold text-safe">₹{w.last_payout}</td>
                  <td className="px-4 py-2.5 font-semibold text-slate-300">₹{w.total_protection.toLocaleString()}</td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>
    </div>
  )
}

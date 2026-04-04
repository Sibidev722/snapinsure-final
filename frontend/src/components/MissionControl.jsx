import { useState, useCallback, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Map, { Marker, Source, Layer, NavigationControl } from 'react-map-gl/mapbox'
import 'mapbox-gl/dist/mapbox-gl.css'
import { 
  CloudRain, Car, Megaphone, Zap, Activity, MapPin, CheckCircle, 
  Wallet, Shield, Server, RefreshCw, Layers
} from 'lucide-react'

// Constants
const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || ''
const SIM_API = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

const ZONE_COLORS = { GREEN: '#10b981', YELLOW: '#f59e0b', RED: '#ef4444' }
const SCENARIOS = [
  { id: 'demand',  label: 'Demand Drop',   icon: <Layers className="w-4 h-4"/>,  color: '#ef4444' },
  { id: 'traffic', label: 'Traffic Delay', icon: <Car className="w-4 h-4"/>,     color: '#f59e0b' },
  { id: 'rain',    label: 'Heavy Rain',    icon: <CloudRain className="w-4 h-4"/>,color: '#3b82f6' },
  { id: 'clear',   label: 'System Clear',  icon: <CheckCircle className="w-4 h-4"/>,color: '#10b981' },
]

// GeoJSON generation for glowing zones
function makeCircleGeoJSON(lat, lon, radiusKm = 1.2, points = 32) {
  const coords = []
  for (let i = 0; i <= points; i++) {
    const angle = (i / points) * 2 * Math.PI
    const dLat = (radiusKm / 111) * Math.sin(angle)
    const dLon = (radiusKm / (111 * Math.cos((lat * Math.PI) / 180))) * Math.cos(angle)
    coords.push([lon + dLon, lat + dLat])
  }
  return { type: 'Feature', geometry: { type: 'Polygon', coordinates: [coords] } }
}

function buildZoneGeoJSON(zones) {
  return {
    type: 'FeatureCollection',
    features: (zones || []).map(z => ({
      ...makeCircleGeoJSON(z.lat, z.lon, z.state === 'RED' ? 1.6 : 1.2),
      properties: { id: z.id, name: z.name, state: z.state, risk: z.risk_score },
    })),
  }
}

// ─── Subcomponents ─────────────────────────────────────────────────────────

function TickerItem({ event }) {
  const typeColors = { WEATHER: '#3b82f6', TRAFFIC: '#f59e0b', STRIKE: '#ef4444', PAYOUT: '#10b981', SYSTEM: '#6366f1' }
  return (
    <div className="flex items-center gap-3 px-6 py-2 border-r border-white/5 shrink-0 bg-white/2 hover:bg-white/5 transition-colors">
      <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: typeColors[event.type] || '#6366f1' }} />
      <span className="text-[11px] font-black uppercase tracking-widest" style={{ color: typeColors[event.type] || '#6366f1' }}>{event.type}</span>
      <span className="text-[12px] text-slate-300 font-mono">{event.msg}</span>
      <span className="text-[10px] text-slate-500 font-mono ml-4">{event.time}</span>
    </div>
  )
}

function PayoutFlash({ payout, onComplete }) {
  useEffect(() => {
    const timer = setTimeout(onComplete, 4000)
    return () => clearTimeout(timer)
  }, [onComplete])

  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.9, y: 30 }} 
      animate={{ opacity: 1, scale: 1, y: 0 }} 
      exit={{ opacity: 0, scale: 1.05, y: -20 }}
      className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none"
    >
      <div className="absolute inset-0 bg-safe/10 backdrop-blur-sm" />
      <div className="relative glass border border-safe/40 rounded-3xl p-12 text-center shadow-[0_0_100px_rgba(16,185,129,0.3)] max-w-lg w-full">
        <div className="w-24 h-24 rounded-full bg-safe/20 flex items-center justify-center mx-auto mb-6 shadow-[0_0_40px_rgba(16,185,129,0.5)]">
          <Zap className="w-12 h-12 text-safe" />
        </div>
        <p className="text-sm font-bold uppercase tracking-[0.2em] text-safe mb-2">Claim Automated</p>
        <p className="text-7xl font-black text-white mb-4 tracking-tighter">₹{payout.amount}</p>
        <p className="text-xl text-safe/80 font-medium">{payout.reason}</p>
        <div className="mt-6 inline-flex items-center gap-2 bg-safe/10 border border-safe/20 px-4 py-2 rounded-lg font-mono text-xs text-safe">
          <Server className="w-3.5 h-3.5" /> Blockchain transaction verified
        </div>
      </div>
    </motion.div>
  )
}

// ─── Main Component ────────────────────────────────────────────────────────

export default function MissionControl({ cityState, user, onLogout }) {
  const [viewport, setViewport] = useState({ latitude: 13.047, longitude: 80.225, zoom: 11.5 })
  const [simLoading, setSimLoading] = useState(null)
  const [recentEvents, setRecentEvents] = useState([])
  const [activePayoutFlash, setActivePayoutFlash] = useState(null)
  
  const userId = user?.user_id || 'ZOM-1001'
  const zones = cityState?.zones || []
  const workers = cityState?.workers || []
  const analytics = cityState?.analytics || {}
  const myWorker = workers.find(w => w.id === userId)
  const myZone = zones.find(z => z.id === myWorker?.zone_id)
  
  const seenPayoutIds = useRef(new Set())
  const seenEventIds = useRef(new Set())

  // Event parsing loop
  useEffect(() => {
    // Process stream events
    if (cityState?.events?.length) {
      const newEvents = []
      
      cityState.events.forEach(ev => {
        const evId = `${ev.type}-${ev.timestamp}-${ev.amount || ''}`
        
        // Push to ticker
        if (!seenEventIds.current.has(evId)) {
          seenEventIds.current.add(evId)
          newEvents.push({
            ...ev,
            time: new Date(ev.timestamp || Date.now()).toLocaleTimeString()
          })
          
          // Flash if payout
          if (ev.type === 'PAYOUT' && ev.amount && !seenPayoutIds.current.has(evId)) {
            seenPayoutIds.current.add(evId)
            setTimeout(() => {
              setActivePayoutFlash({ amount: ev.amount, reason: ev.msg })
            }, 300) // slight delay for drama
          }
        }
      })
      
      if (newEvents.length > 0) {
        setRecentEvents(prev => [...newEvents, ...prev].slice(0, 30))
      }
    }

    // Process analytic payouts (fallback)
    if (cityState?.analytics?.recent_payouts?.length) {
      cityState.analytics.recent_payouts.forEach(p => {
        const tId = `PAYOUT-${p.timestamp}-${p.amount}`
        if (!seenPayoutIds.current.has(tId)) {
          seenPayoutIds.current.add(tId)
          setTimeout(() => {
            setActivePayoutFlash({ amount: p.amount, reason: p.reason })
          }, 300)
        }
      })
    }
  }, [cityState?.timestamp])

  const runSimulation = async (id) => {
    if (simLoading) return
    setSimLoading(id)
    try {
      const token = localStorage.getItem('snapinsure_token')
      await fetch(`${SIM_API}/sim/trigger`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ event_type: id }),
      })
    } catch (_) {}
    setTimeout(() => setSimLoading(null), 1500)
  }

  // ─── Rendering ───────────────────────────────────────────

  const zoneGeoJSON = buildZoneGeoJSON(zones)
  const fillColorExpr = [
    'match', ['get', 'state'],
    'RED',    ZONE_COLORS.RED,
    'YELLOW', ZONE_COLORS.YELLOW,
    'GREEN',  ZONE_COLORS.GREEN,
    '#10b981'
  ]

  const activeShift = myWorker?.shift
  const earningsTarget = activeShift?.expected_income || 0
  const currentEarnings = activeShift?.current_earnings || 0
  const earningsPct = earningsTarget ? Math.min((currentEarnings / earningsTarget) * 100, 100) : 0

  return (
    <div className="w-full h-screen bg-[#0B0F14] text-slate-200 overflow-hidden flex flex-col font-sans selection:bg-brand/30">
      
      <AnimatePresence>
        {activePayoutFlash && (
          <PayoutFlash payout={activePayoutFlash} onComplete={() => setActivePayoutFlash(null)} />
        )}
      </AnimatePresence>

      {/* ── Top Ticker ── */}
      <div className="h-10 border-b border-white/5 flex items-stretch bg-card/60 backdrop-blur-md relative z-20 shrink-0">
        <div className="px-6 flex items-center justify-center border-r border-white/5 bg-brand/10 shrink-0">
          <Activity className="w-4 h-4 text-brand animate-pulse mr-2" />
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-brand">Central Feed</span>
        </div>
        <div className="flex-1 overflow-hidden relative flex">
          {recentEvents.length === 0 ? (
            <div className="flex items-center px-6 text-xs font-mono text-slate-500">Monitoring grid...</div>
          ) : (
            <div className="ticker-scroll">
              {recentEvents.map((ev, i) => <TickerItem key={i} event={ev} />)}
              {/* Duplicate for infinite effect */}
              {recentEvents.map((ev, i) => <TickerItem key={`dup-${i}`} event={ev} />)}
            </div>
          )}
        </div>
        <div className="px-6 flex items-center border-l border-white/5 shrink-0 hover:bg-white/5 cursor-pointer transition-colors" onClick={onLogout}>
          <Shield className="w-4 h-4 text-slate-400 mr-2" />
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">{user?.name} (LOGOUT)</span>
        </div>
      </div>

      {/* ── Main Workspace ── */}
      <div className="flex-1 grid grid-cols-12 relative overflow-hidden">
        
        {/* Left: Mapbox Radar */}
        <div className="col-span-12 lg:col-span-8 xl:col-span-9 relative h-full bg-[#0B0F14]">
          <Map
            {...viewport}
            onMove={e => setViewport(e.viewState)}
            mapStyle="mapbox://styles/mapbox/dark-v11"
            mapboxAccessToken={MAPBOX_TOKEN}
            style={{ width: '100%', height: '100%' }}
            interactiveLayerIds={['zone-fill']}
          >
            <NavigationControl position="top-right" showCompass={false} />
            
            {zones.length > 0 && (
              <Source id="zones" type="geojson" data={zoneGeoJSON}>
                <Layer
                  id="zone-fill"
                  type="fill"
                  paint={{
                    'fill-color': fillColorExpr,
                    'fill-opacity': ['case', ['==', ['get', 'state'], 'RED'], 0.15, ['==', ['get', 'state'], 'YELLOW'], 0.08, 0.02],
                  }}
                />
                <Layer
                  id="zone-border"
                  type="line"
                  paint={{
                    'line-color': fillColorExpr,
                    'line-width': ['case', ['==', ['get', 'state'], 'RED'], 2, 1],
                    'line-opacity': ['case', ['==', ['get', 'state'], 'RED'], 0.8, 0.3],
                  }}
                />
              </Source>
            )}

            {workers.map(w => (
              <Marker key={w.id} latitude={w.lat} longitude={w.lon}>
                <div className="relative pointer-events-none">
                  {w.id === userId && (
                    <motion.div 
                      className="absolute -inset-4 rounded-full border border-brand/50 bg-brand/10"
                      animate={{ scale: [1, 1.5, 1], opacity: [0.5, 0, 0.5] }}
                      transition={{ duration: 2, repeat: Infinity }}
                    />
                  )}
                  <div className={`w-3 h-3 rounded-full border border-surface shadow-[0_0_10px_currentColor] ${w.zone_state === 'RED' ? 'text-danger bg-danger' : w.zone_state === 'YELLOW' ? 'text-warn bg-warn' : 'text-safe bg-safe'}`} />
                </div>
              </Marker>
            ))}
          </Map>
          
          {/* Map Overlay Stats */}
          <div className="absolute top-6 left-6 pointer-events-none hidden md:block">
            <h1 className="text-3xl font-black text-white mix-blend-overlay tracking-tighter shadow-black/50 drop-shadow-xl">
              Chennai <span className="opacity-50">Grid</span>
            </h1>
            <div className="flex gap-2 mt-2">
              <span className="glass px-3 py-1 rounded-md text-[10px] font-bold text-safe border-safe/20 shadow-glow-safe">{analytics.green_zones || 0} SECURE</span>
              <span className="glass px-3 py-1 rounded-md text-[10px] font-bold text-warn border-warn/20 shadow-glow-warn">{analytics.yellow_zones || 0} DELAYED</span>
              <span className="glass px-3 py-1 rounded-md text-[10px] font-bold text-danger border-danger/20 shadow-[0_0_15px_rgba(239,68,68,0.4)]">{analytics.red_zones || 0} BLOCKED</span>
            </div>
          </div>
        </div>

        {/* Right: Telemetry Sidebar */}
        <div className="col-span-12 lg:col-span-4 xl:col-span-3 border-l border-white/5 bg-card/60 backdrop-blur-xl flex flex-col h-full z-10 shadow-[-20px_0_40px_rgba(0,0,0,0.5)]">
          <div className="flex-1 overflow-y-auto no-scrollbar p-6 space-y-6">
            
            {/* Identity & Core Wallet */}
            <div>
              <p className="text-[10px] font-mono text-brand uppercase tracking-widest mb-2 flex items-center gap-2">
                <MapPin className="w-3 h-3" /> Agent Uplink
              </p>
              <div className="glass border border-brand/20 rounded-2xl p-6 relative overflow-hidden shadow-glow-brand group">
                <div className="absolute -right-10 -top-10 w-32 h-32 bg-brand/20 blur-3xl opacity-50 group-hover:opacity-100 transition-opacity" />
                <h2 className="text-sm font-semibold text-slate-300">Protected Balance</h2>
                <div className="text-5xl font-black tracking-tighter text-white mt-2 mb-1 flex items-baseline gap-1">
                  <span className="text-2xl text-brand">₹</span>
                  {(myWorker?.total_protection || 0).toLocaleString()}
                </div>
                {myWorker?.last_payout > 0 && (
                  <p className="text-[11px] font-mono text-safe bg-safe/10 inline-block px-2 py-0.5 rounded shadow-glow-safe border border-safe/20">
                    +₹{myWorker.last_payout} last sync
                  </p>
                )}
              </div>
            </div>

            {/* AI Zone Intelligence */}
            <div>
               <p className="text-[10px] font-mono text-slate-500 uppercase tracking-widest mb-2 flex items-center gap-2">
                <Server className="w-3 h-3" /> Zone Intelligence
              </p>
              <div className="glass border border-white/10 rounded-2xl p-5 shadow-card">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <p className="text-xs text-slate-400">Current Vector</p>
                    <p className="text-lg font-bold text-white">{myZone?.name || 'Scanning...'}</p>
                  </div>
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center font-bold text-xl shadow-[0_0_20px_currentColor] border border-white/10 ${myZone?.state === 'RED' ? 'bg-danger/20 text-danger' : myZone?.state === 'YELLOW' ? 'bg-warn/20 text-warn' : 'bg-safe/20 text-safe'}`}>
                    {myZone?.state === 'RED' ? '🔴' : myZone?.state === 'YELLOW' ? '🟡' : '🟢'}
                  </div>
                </div>
                
                {myZone && (
                  <div className="grid grid-cols-2 gap-3 mt-4 pt-4 border-t border-white/5">
                    <div className="bg-[#0B0F14] rounded-lg p-3 border border-white/5">
                       <p className="text-[9px] uppercase tracking-wider text-slate-500 mb-1">Grid Demand</p>
                       <p className={`text-base font-mono font-bold ${myZone.orders_per_minute < myZone.baseline_orders * 0.7 ? 'text-danger animate-pulse' : 'text-safe'}`}>
                         {myZone.orders_per_minute} <span className="text-[9px] text-slate-600">req/m</span>
                       </p>
                    </div>
                    <div className="bg-[#0B0F14] rounded-lg p-3 border border-white/5">
                       <p className="text-[9px] uppercase tracking-wider text-slate-500 mb-1">Delay Factor</p>
                       <p className={`text-base font-mono font-bold ${myZone.delay_factor > 1.2 ? 'text-warn' : 'text-slate-300'}`}>
                         {myZone.delay_factor}x
                       </p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Shift Tracker */}
            {activeShift && (
              <div>
                <p className="text-[10px] font-mono text-slate-500 uppercase tracking-widest mb-2 flex items-center gap-2">
                  <Shield className="w-3 h-3" /> Shift Telemetry
                </p>
                <div className="glass border border-white/10 rounded-2xl p-5 shadow-card relative overflow-hidden">
                  {activeShift.compensated && <div className="absolute inset-0 bg-safe/5" />}
                  <div className="flex justify-between items-end mb-3">
                    <div>
                      <p className="text-[10px] uppercase font-bold text-brand tracking-wider">{activeShift.name}</p>
                      <p className="text-xl font-black text-white">₹{currentEarnings.toFixed(0)} <span className="text-[10px] font-normal text-slate-500">/ ₹{earningsTarget}</span></p>
                    </div>
                    {activeShift.compensated ? (
                      <span className="tag bg-safe/20 text-safe border-safe/30 shadow-glow-safe">PROTECTED</span>
                    ) : (
                      <span className="tag bg-white/5 text-slate-400 border-white/10">EXPOSED</span>
                    )}
                  </div>
                  <div className="h-1.5 w-full bg-[#0B0F14] rounded-full overflow-hidden border border-white/5">
                      <motion.div 
                        className={`h-full rounded-full ${activeShift.compensated ? 'bg-safe' : 'bg-brand'}`}
                        initial={{ width: 0 }}
                        animate={{ width: `${earningsPct}%` }}
                        transition={{ duration: 1 }}
                      />
                  </div>
                </div>
              </div>
            )}

            {/* Simulation Control Room */}
            <div>
               <p className="text-[10px] font-mono text-warn uppercase tracking-widest mb-2 flex items-center gap-2">
                <Zap className="w-3 h-3" /> Grid Control Override
              </p>
              <div className="grid grid-cols-2 gap-3">
                {SCENARIOS.map(s => (
                  <button key={s.id} onClick={() => runSimulation(s.id)} disabled={!!simLoading}
                    className="glass border border-white/10 hover:border-white/30 rounded-xl p-3 flex flex-col items-center justify-center gap-2 group transition-all text-center relative overflow-hidden active:scale-95 disabled:opacity-50">
                    {simLoading === s.id && <div className="absolute inset-0 bg-white/10 animate-pulse" />}
                    <div className="w-8 h-8 rounded-full bg-[#0B0F14] flex items-center justify-center shadow-inner group-hover:scale-110 transition-transform" style={{ color: s.color }}>
                      {simLoading === s.id ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : s.icon}
                    </div>
                    <span className="text-[10px] font-bold text-slate-300">{s.label}</span>
                  </button>
                ))}
              </div>
            </div>

          </div>
        </div>

      </div>

      {/* ── Bottom River ── (Financial Event Stream) */}
      <div className="h-28 border-t border-white/5 bg-card/80 backdrop-blur-3xl shrink-0 relative flex flex-col justify-center px-6 overflow-hidden z-30">
        <div className="absolute left-0 top-0 bottom-0 w-24 bg-gradient-to-r from-card/80 to-transparent z-10 pointer-events-none" />
        <div className="absolute right-0 top-0 bottom-0 w-24 bg-gradient-to-l from-card/80 to-transparent z-10 pointer-events-none" />
        
        <p className="text-[9px] font-mono text-safe uppercase tracking-[0.3em] absolute top-3 left-6 z-20">Live Contract Executions</p>
        
        <div className="flex gap-4 items-center overflow-x-auto no-scrollbar pt-4 snap-x">
          <AnimatePresence>
            {cityState?.analytics?.recent_payouts?.slice(0, 10).map((p, i) => (
              <motion.div key={`${p.timestamp}-${p.amount}-${i}`}
                initial={{ opacity: 0, x: 50, scale: 0.9 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                className="shrink-0 snap-start bg-[#0B0F14] border border-safe/20 rounded-xl p-3 w-72 shadow-glow-safe flex items-center gap-3 relative overflow-hidden group">
                <div className="absolute top-0 left-0 w-1 h-full bg-safe group-hover:w-full group-hover:opacity-10 transition-all duration-500" />
                <div className="w-10 h-10 rounded-lg bg-safe/10 flex items-center justify-center flex-shrink-0 border border-safe/20">
                  <Zap className="w-5 h-5 text-safe" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex justify-between items-baseline">
                    <p className="text-base font-black text-white leading-none">₹{p.amount}</p>
                    <span className="text-[9px] font-mono text-safe">{new Date(p.timestamp).toLocaleTimeString()}</span>
                  </div>
                  <p className="text-[10px] text-slate-400 truncate mt-1">{p.name || 'Worker'} • {p.reason}</p>
                </div>
              </motion.div>
            ))}
            {(!cityState?.analytics?.recent_payouts || cityState.analytics.recent_payouts.length === 0) && (
              <div className="text-xs text-slate-600 font-mono italic px-4">Waiting for parameter triggers...</div>
            )}
          </AnimatePresence>
        </div>
      </div>

    </div>
  )
}

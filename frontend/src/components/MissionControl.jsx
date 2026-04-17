import { useState, useCallback, useEffect, useRef } from 'react'
import Map, { Marker, Source, Layer, NavigationControl } from 'react-map-gl/mapbox'
import 'mapbox-gl/dist/mapbox-gl.css'
import {
  Shield, Activity, Navigation, Network, Zap, ShieldAlert,
  CloudRain, Truck, Megaphone, TrendingDown, Sun, RefreshCw,
  CheckCircle, XCircle, AlertTriangle, Leaf, Clock
} from 'lucide-react'
import { useSimulationStore } from '../store/useSimulationStore'
import DecisionAuditModal from './DecisionAuditModal'
import AIExplainabilityPanel from './AIExplainabilityPanel'
import LiveIntelligenceFeed from './LiveIntelligenceFeed'
import AdminOverridePanel from './AdminOverridePanel'
import AnimatedNumber from './AnimatedNumber'
import { useOptimizedTelemetry } from '../hooks/useOptimizedTelemetry'

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || ''
const SIM_API      = import.meta.env.VITE_BACKEND_URL  || 'http://localhost:8000'

const COLORS = {
  NAVY: '#0a0f18', PANEL: '#121826', TEXT: '#e2e8f0', MUTED: '#64748b',
  SAFE: '#10b981', WARN: '#f59e0b', DANGER: '#ef4444'
}

const SIM_EVENTS = [
  { id: 'rain',    label: 'Heavy Rain',   icon: CloudRain,    color: '#3b82f6' },
  { id: 'traffic', label: 'Traffic Jam',  icon: Truck,        color: '#f59e0b' },
  { id: 'strike',  label: 'Strike',       icon: Megaphone,    color: '#ef4444' },
  { id: 'demand',  label: 'Demand Drop',  icon: TrendingDown, color: '#8b5cf6' },
  { id: 'clear',   label: 'Clear All',    icon: Sun,          color: '#10b981' },
]

// ── GeoJSON helpers ───────────────────────────────────────────────────────────
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
      ...makeCircleGeoJSON(z.lat, z.lon, 1.4),
      properties: { id: z.id, name: z.name, state: z.state, risk: z.risk_score },
    })),
  }
}

// ── Status Indicator ──────────────────────────────────────────────────────────
function StatusIndicator({ label, active }) {
  return (
    <div className="flex items-center gap-2 border-r border-[#1e293b] pr-4 last:border-0 last:pr-0">
      <div className={`w-2 h-2 rounded-full ${active ? 'bg-[#10b981] animate-pulse' : 'bg-[#ef4444]'}`} />
      <span className="text-[10px] font-medium text-[#94a3b8] uppercase tracking-wider">{label}</span>
    </div>
  )
}

// ── Agent Badge ───────────────────────────────────────────────────────────────
function AgentBadge({ agent }) {
  const decisionColor = {
    PASS:   { bg: 'bg-[#10b981]/10', text: 'text-[#10b981]', border: 'border-[#10b981]/30', icon: CheckCircle },
    REVIEW: { bg: 'bg-[#f59e0b]/10', text: 'text-[#f59e0b]', border: 'border-[#f59e0b]/30', icon: AlertTriangle },
    FAIL:   { bg: 'bg-[#ef4444]/10', text: 'text-[#ef4444]', border: 'border-[#ef4444]/30', icon: XCircle },
  }[agent.decision] || { bg: 'bg-[#64748b]/10', text: 'text-[#94a3b8]', border: 'border-[#64748b]/30', icon: AlertTriangle }

  const Icon = decisionColor.icon
  return (
    <div className={`p-2.5 rounded border ${decisionColor.bg} ${decisionColor.border}`}>
      <div className="flex justify-between items-start mb-1.5">
        <div className="flex items-center gap-1.5">
          <span className="text-sm">{agent.icon}</span>
          <span className="text-[10px] font-bold text-[#e2e8f0] uppercase tracking-wide">{agent.agent}</span>
        </div>
        <div className={`flex items-center gap-1 ${decisionColor.text}`}>
          <Icon className="w-3 h-3" />
          <span className="text-[9px] font-bold">{agent.decision}</span>
        </div>
      </div>
      <p className="text-[9px] text-[#64748b] leading-relaxed">{agent.reason}</p>
      <div className="flex justify-between mt-1.5 pt-1.5 border-t border-[#1e293b]/60">
        <span className="text-[9px] text-[#94a3b8] font-mono">score: {agent.score?.toFixed(3)}</span>
        <span className="text-[9px] text-[#94a3b8] font-mono">conf: {((agent.confidence || 0) * 100).toFixed(0)}%</span>
      </div>
    </div>
  )
}

// ── ESG Block ─────────────────────────────────────────────────────────────────
function ESGBlock({ esg }) {
  if (!esg) return null
  const score = esg.composite || 0
  const color = score > 0.65 ? '#10b981' : score > 0.4 ? '#f59e0b' : '#ef4444'
  return (
    <div className="border border-[#1e293b] rounded bg-[#0a0f18] p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <Leaf className="w-3 h-3 text-[#10b981]" />
          <span className="text-[10px] font-bold text-[#64748b] uppercase tracking-wider">ESG Score</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono font-bold" style={{ color }}>{(score * 100).toFixed(0)}/100</span>
          <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: color + '20', color }}>{esg.label}</span>
        </div>
      </div>
      <div className="h-1 w-full bg-[#1e293b] rounded-sm overflow-hidden mb-2">
        <div className="h-full rounded-sm transition-all duration-700" style={{ width: `${score * 100}%`, background: color }} />
      </div>
      <div className="grid grid-cols-3 gap-2 mt-2">
        {[
          { label: 'Environ.', val: esg.breakdown?.environmental },
          { label: 'Social',   val: esg.breakdown?.social },
          { label: 'Govern.',  val: esg.breakdown?.governance },
        ].map(({ label, val }) => (
          <div key={label} className="text-center">
            <p className="text-[8px] text-[#64748b] uppercase tracking-wider">{label}</p>
            <p className="text-[10px] font-mono text-[#94a3b8]">{val != null ? (val * 100).toFixed(0) : '--'}</p>
          </div>
        ))}
      </div>
      {esg.premium_impact !== 'neutral' && (
        <p className="text-[9px] mt-2 pt-2 border-t border-[#1e293b]" style={{ color: esg.premium_impact === 'discount' ? '#10b981' : '#ef4444' }}>
          {esg.premium_impact === 'discount' ? '▼' : '▲'} {esg.premium_pct?.toFixed(1)}% premium {esg.premium_impact}
        </p>
      )}
    </div>
  )
}

// ── Main UI Component ─────────────────────────────────────────────────────────
export default function MissionControl({ cityState, user, onLogout }) {
  const [viewport, setViewport]           = useState({ latitude: 13.047, longitude: 80.225, zoom: 11.5 })
  const [selectedZone, setSelectedZone]   = useState(null)
  const [zoneIntel, setZoneIntel]         = useState(null)
  const [intelLoading, setIntelLoading]   = useState(false)
  const [gnnPredictions, setGnnPredictions] = useState([])
  const [auditEvent, setAuditEvent]       = useState(null)
  const [opsPanelOpen, setOpsPanelOpen]   = useState(false)
  const [simLoading, setSimLoading]       = useState(null)
  const [simMessage, setSimMessage]       = useState(null)
  const [lastUpdated, setLastUpdated]     = useState(new Date())

  const zonesRaw = cityState?.zones  || []
  const zones    = useOptimizedTelemetry(zonesRaw, 300)
  const workers  = cityState?.workers || []
  const payouts  = cityState?.analytics?.recent_payouts || []

  // Fetch GNN predictions on mount and refresh
  useEffect(() => {
    const fetchGnn = async () => {
      try {
        const res = await fetch(`${SIM_API}/gnn/latest`)
        if (res.ok) {
          const d = await res.json()
          setGnnPredictions(d.predictions || [])
          setLastUpdated(new Date())
        }
      } catch (_) {}
    }
    fetchGnn()
    const iv = setInterval(fetchGnn, 60_000)
    return () => clearInterval(iv)
  }, [])

  // Fetch zone intelligence when zone selected
  const fetchZoneIntelligence = useCallback(async (zoneId) => {
    setIntelLoading(true)
    setZoneIntel(null)
    try {
      const res = await fetch(`${SIM_API}/intelligence/${zoneId}`)
      if (res.ok) {
        const data = await res.json()
        setZoneIntel(data)
      }
    } catch (e) {
      console.error('Zone intelligence fetch failed:', e)
    } finally {
      setIntelLoading(false)
    }
  }, [])

  const handleZoneClick = useCallback((zone) => {
    setSelectedZone(zone)
    fetchZoneIntelligence(zone.id)
  }, [fetchZoneIntelligence])

  // Run simulation trigger
  const runSimulation = async (eventId) => {
    setSimLoading(eventId)
    setSimMessage(null)
    try {
      const res = await fetch(`${SIM_API}/sim/trigger`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ event_type: eventId }),
      })
      const data = await res.json()
      setSimMessage({ ok: res.ok, text: data.message || (res.ok ? 'Triggered!' : 'Failed') })
      // Refresh zone intel if one is selected
      if (selectedZone) setTimeout(() => fetchZoneIntelligence(selectedZone.id), 1200)
    } catch (e) {
      setSimMessage({ ok: false, text: 'Network error' })
    } finally {
      setSimLoading(null)
      setTimeout(() => setSimMessage(null), 4000)
    }
  }

  const zoneGeoJSON    = buildZoneGeoJSON(zones)
  const fillColorExpr  = ['match', ['get', 'state'], 'RED', COLORS.DANGER, 'YELLOW', COLORS.WARN, 'GREEN', COLORS.SAFE, '#10b981']

  // Use zoneIntel data when available, fall back to selectedZone
  const displayZone    = zoneIntel || selectedZone
  const activeGnnData  = selectedZone ? gnnPredictions.find(p => p.zone === selectedZone.id) : null
  const activeZoneData = zoneIntel?.signals || null

  return (
    <div className="w-full h-screen bg-[#0a0f18] text-[#e2e8f0] flex flex-col font-sans overflow-hidden">

      {/* ── TOP BAR ── */}
      <div className="h-12 bg-[#121826] border-b border-[#1e293b] flex items-center justify-between px-6 shrink-0 shadow-sm z-20">
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 bg-[#1e293b] rounded flex items-center justify-center">
            <Shield className="w-3.5 h-3.5 text-[#e2e8f0]" />
          </div>
          <span className="text-xs font-bold tracking-widest text-[#e2e8f0] uppercase">SnapInsure OS</span>
        </div>
        <div className="flex items-center gap-4">
          <StatusIndicator label="API: Active"    active={true} />
          <StatusIndicator label="GNN: Running"   active={true} />
          <StatusIndicator label="Agents: Synced" active={true} />
          <div className="flex items-center gap-1 text-[9px] text-[#475569] font-mono ml-2">
            <Clock className="w-3 h-3" />
            <span>Updated {lastUpdated.toLocaleTimeString()}</span>
          </div>
          <button
            onClick={() => setOpsPanelOpen(true)}
            className="ml-2 flex items-center gap-1.5 px-3 py-1.5 bg-[#1e293b] hover:bg-[#334155] text-[#cbd5e1] border border-[#334155] rounded text-[10px] font-bold uppercase tracking-wider transition-colors"
          >
            <ShieldAlert className="w-3 h-3 text-[#f59e0b]" /> Ops Queue
          </button>
        </div>
      </div>

      {/* ── MAIN LAYOUT ── */}
      <div className="flex-1 flex overflow-hidden">

        {/* LEFT PANEL: MAP */}
        <div className="flex-1 relative bg-[#0a0f18]">
          <Map
            {...viewport}
            onMove={e => setViewport(e.viewState)}
            mapStyle="mapbox://styles/mapbox/dark-v11"
            mapboxAccessToken={MAPBOX_TOKEN}
            style={{ width: '100%', height: '100%' }}
            interactiveLayerIds={['zone-fill']}
            onClick={e => {
              const f = e.features?.[0]
              if (f?.layer?.id === 'zone-fill') {
                const zId = f.properties?.id
                const z   = zones.find(x => x.id === zId)
                if (z) handleZoneClick(z)
              } else {
                setSelectedZone(null)
                setZoneIntel(null)
              }
            }}
          >
            <NavigationControl position="bottom-right" showCompass={false} />

            {zones.length > 0 && (
              <Source id="zones" type="geojson" data={zoneGeoJSON}>
                <Layer id="zone-fill" type="fill"
                  paint={{
                    'fill-color':   fillColorExpr,
                    'fill-opacity': ['case', ['==', ['get', 'state'], 'RED'], 0.25, ['==', ['get', 'state'], 'YELLOW'], 0.15, 0.08],
                  }}
                />
                <Layer id="zone-border" type="line"
                  paint={{
                    'line-color':   fillColorExpr,
                    'line-width':   ['case', ['==', ['get', 'state'], 'RED'], 2, 1],
                    'line-opacity': 0.8,
                  }}
                />
              </Source>
            )}

            {workers.map(w => (
              <Marker key={w.id} latitude={w.lat} longitude={w.lon}>
                <div className={`w-2.5 h-2.5 rounded-full border border-[#0a0f18] transition-colors duration-300 ease-in-out
                  ${w.zone_state === 'RED' ? 'bg-[#ef4444]' : w.zone_state === 'YELLOW' ? 'bg-[#f59e0b]' : 'bg-[#10b981]'}`} />
              </Marker>
            ))}
          </Map>

          {/* Spatial Grid Label */}
          <div className="absolute top-4 left-4 bg-[#121826]/90 backdrop-blur border border-[#1e293b] p-3 rounded-md shadow-lg pointer-events-none">
            <h1 className="text-sm font-bold text-white uppercase tracking-wider">Spatial Grid</h1>
            <p className="text-[10px] text-[#94a3b8] mt-0.5">Click zone polygons for deep telemetry.</p>
          </div>

          {/* ── SIMULATION CONTROL BAR ── */}
          <div className="absolute top-4 left-1/2 -translate-x-1/2 flex items-center gap-2 bg-[#121826]/95 backdrop-blur border border-[#1e293b] px-3 py-2 rounded-lg shadow-xl z-10">
            <span className="text-[9px] font-bold uppercase tracking-widest text-[#475569] mr-1">Simulate</span>
            {SIM_EVENTS.map(ev => {
              const Icon = ev.icon
              const isLoading = simLoading === ev.id
              return (
                <button
                  key={ev.id}
                  onClick={() => runSimulation(ev.id)}
                  disabled={!!simLoading}
                  title={ev.label}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded text-[10px] font-bold uppercase tracking-wide border transition-all disabled:opacity-50"
                  style={{
                    background: `${ev.color}15`,
                    borderColor: `${ev.color}40`,
                    color: ev.color,
                  }}
                >
                  {isLoading
                    ? <RefreshCw className="w-3 h-3 animate-spin" />
                    : <Icon className="w-3 h-3" />
                  }
                  <span className="hidden sm:inline">{ev.label}</span>
                </button>
              )
            })}
            {simMessage && (
              <span className={`text-[9px] font-mono ml-1 ${simMessage.ok ? 'text-[#10b981]' : 'text-[#ef4444]'}`}>
                {simMessage.text}
              </span>
            )}
          </div>

          {/* OSINT Live Feed Overlay */}
          <div className="absolute bottom-6 left-6 pointer-events-none">
            <LiveIntelligenceFeed />
          </div>
        </div>

        {/* RIGHT PANEL: INSPECTOR */}
        <div className="w-[420px] bg-[#121826] border-l border-[#1e293b] flex flex-col overflow-hidden z-10 shadow-[-10px_0_30px_rgba(0,0,0,0.5)]">

          <div className="p-5 overflow-y-auto no-scrollbar flex-1">
            {!selectedZone ? (
              <div className="h-full flex flex-col justify-center items-center text-center text-[#64748b]">
                <Navigation className="w-8 h-8 mb-3 opacity-20" />
                <p className="text-xs uppercase tracking-widest font-medium">No Node Selected</p>
                <p className="text-[10px] mt-2 max-w-[200px]">Select a hexagonal grid node from the map to inspect GNN inference telemetry.</p>
              </div>
            ) : intelLoading ? (
              <div className="h-full flex flex-col justify-center items-center text-center text-[#64748b]">
                <RefreshCw className="w-6 h-6 mb-3 animate-spin opacity-40" />
                <p className="text-[10px] uppercase tracking-widest">Loading intelligence...</p>
              </div>
            ) : (
              <div className="space-y-5 animate-in fade-in duration-200">

                {/* ── Zone Header ── */}
                <div className="flex items-start justify-between pb-4 border-b border-[#1e293b]">
                  <div>
                    <p className="text-[10px] uppercase text-[#64748b] tracking-wider mb-1">Sector Identification</p>
                    <h2 className="text-xl font-bold text-[#e2e8f0]">{displayZone?.zone_name || selectedZone.name}</h2>
                    <p className="text-[9px] font-mono text-[#94a3b8] mt-0.5">ID: {selectedZone.id}</p>
                    {zoneIntel?.last_updated && (
                      <p className="text-[9px] text-[#475569] mt-1 font-mono">
                        ⏱ {new Date(zoneIntel.last_updated).toLocaleTimeString()}
                      </p>
                    )}
                  </div>
                  <div className={`px-2.5 py-1 rounded text-[10px] font-bold tracking-widest uppercase border transition-colors duration-300
                    ${(displayZone?.state || selectedZone.state) === 'RED'    ? 'bg-[#ef4444]/10 text-[#ef4444] border-[#ef4444]/30' :
                      (displayZone?.state || selectedZone.state) === 'YELLOW' ? 'bg-[#f59e0b]/10 text-[#f59e0b] border-[#f59e0b]/30' :
                      'bg-[#10b981]/10 text-[#10b981] border-[#10b981]/30'}`}>
                    {displayZone?.state || selectedZone.state}
                  </div>
                </div>

                {/* ── Risk Bars ── */}
                <div className="space-y-4 pb-4 border-b border-[#1e293b]">
                  <div>
                    <div className="flex justify-between items-end mb-1.5">
                      <p className="text-xs font-semibold text-[#e2e8f0]">Current Base Risk</p>
                      <AnimatedNumber value={zoneIntel?.risk_score ?? selectedZone.risk_score ?? 0} className="text-[11px] font-mono font-bold text-[#94a3b8]" />
                    </div>
                    <div className="h-1.5 w-full bg-[#1e293b] overflow-hidden rounded-sm">
                      <div className="h-full bg-[#3b82f6] transition-all duration-700 ease-in-out"
                        style={{ width: `${((zoneIntel?.risk_score ?? selectedZone.risk_score) || 0) * 100}%` }} />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between items-end mb-1.5">
                      <p className="text-xs font-semibold text-[#e2e8f0] flex items-center gap-1.5">
                        <Activity className="w-3 h-3 text-[#f59e0b]" /> Predictive Horizon (t+30m)
                      </p>
                      <span className="text-[11px] font-mono font-bold text-[#f59e0b]">
                        {zoneIntel?.predicted_risk_30m ? `${(zoneIntel.predicted_risk_30m * 100).toFixed(0)}%` : '+12%'}
                      </span>
                    </div>
                    <div className="h-1.5 w-full bg-[#1e293b] overflow-hidden rounded-sm">
                      <div className="h-full bg-[#f59e0b] transition-all duration-700 ease-in-out"
                        style={{ width: `${Math.min((zoneIntel?.predicted_risk_30m || (selectedZone.risk_score + 0.12)) * 100, 100)}%` }} />
                    </div>
                    <p className="text-[9px] text-[#64748b] mt-1.5">
                      {zoneIntel?.gnn?.explanation || 'Model anticipates compounding congestion from adjacent nodes.'}
                    </p>
                  </div>
                </div>

                {/* ── XAI Explanation ── */}
                {zoneIntel?.explanation && (
                  <div className="bg-[#0a0f18] border border-[#1e293b] p-3 rounded-lg relative overflow-hidden">
                    <div className="absolute top-0 left-0 w-1 h-full bg-[#3b82f6]" />
                    <p className="text-[10px] font-bold text-[#64748b] uppercase tracking-widest mb-1.5 ml-2">AI Interpretation</p>
                    <p className="text-[11px] text-[#cbd5e1] leading-relaxed font-mono ml-2">"{zoneIntel.explanation}"</p>
                  </div>
                )}

                {/* ── Feature Attribution (AI Explainability) ── */}
                <div className="pb-4 border-b border-[#1e293b]">
                  <AIExplainabilityPanel zoneData={activeZoneData} gnnData={zoneIntel?.gnn ? { xai: { ...zoneIntel.gnn?.xai, explanation: zoneIntel.explanation } } : activeGnnData} />
                </div>

                {/* ── ESG Score ── */}
                {zoneIntel?.esg && (
                  <div className="pb-4 border-b border-[#1e293b]">
                    <p className="text-[10px] uppercase text-[#64748b] tracking-wider mb-2 flex items-center gap-1.5">
                      <Leaf className="w-3 h-3 text-[#10b981]" /> ESG Intelligence
                    </p>
                    <ESGBlock esg={zoneIntel.esg} />
                  </div>
                )}

                {/* ── Multi-Agent Decisions ── */}
                {zoneIntel?.agents?.length > 0 && (
                  <div className="pb-4 border-b border-[#1e293b]">
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-[10px] uppercase text-[#64748b] tracking-wider flex items-center gap-1.5">
                        <Network className="w-3 h-3" /> Agent Consensus
                      </p>
                      {zoneIntel.consensus && (
                        <span className={`text-[9px] font-bold px-2 py-0.5 rounded border ${
                          zoneIntel.consensus.decision === 'PASS'   ? 'bg-[#10b981]/10 text-[#10b981] border-[#10b981]/30' :
                          zoneIntel.consensus.decision === 'REVIEW' ? 'bg-[#f59e0b]/10 text-[#f59e0b] border-[#f59e0b]/30' :
                          'bg-[#ef4444]/10 text-[#ef4444] border-[#ef4444]/30'
                        }`}>
                          {zoneIntel.consensus.decision} · {zoneIntel.consensus.score?.toFixed(3)}
                        </span>
                      )}
                    </div>
                    <div className="space-y-2">
                      {zoneIntel.agents.map((agent, i) => <AgentBadge key={i} agent={agent} />)}
                    </div>
                  </div>
                )}

                {/* ── Payout Status ── */}
                {zoneIntel?.payout && (
                  <div className={`p-3 rounded border ${zoneIntel.payout.triggered ? 'bg-[#ef4444]/8 border-[#ef4444]/30' : 'bg-[#10b981]/8 border-[#10b981]/20'}`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <Zap className={`w-3.5 h-3.5 ${zoneIntel.payout.triggered ? 'text-[#ef4444]' : 'text-[#10b981]'}`} />
                        <span className="text-[10px] font-bold uppercase tracking-wider text-[#e2e8f0]">
                          {zoneIntel.payout.triggered ? 'Auto-Payout Triggered' : 'No Payout Active'}
                        </span>
                      </div>
                      {zoneIntel.payout.triggered && (
                        <span className="text-[13px] font-black text-[#ef4444]">₹{zoneIntel.payout.amount}</span>
                      )}
                    </div>
                    {zoneIntel?.premium && (
                      <p className="text-[9px] text-[#64748b] mt-1.5 font-mono">
                        Dynamic premium: ₹{zoneIntel.premium.dynamic}/hr
                        {' '}({zoneIntel.premium.esg_impact} applied)
                      </p>
                    )}
                  </div>
                )}

                {/* ── Graph Neighbor Influence ── */}
                <div>
                  <p className="text-[10px] uppercase text-[#64748b] tracking-wider mb-2 flex items-center gap-1.5">
                    <Network className="w-3 h-3" /> Graph Neighbor Influence
                  </p>
                  <div className="border border-[#1e293b] rounded bg-[#0a0f18] divide-y divide-[#1e293b]">
                    {!(zoneIntel?.gnn?.xai?.top_neighbors || activeGnnData?.xai?.top_neighbors) ? (
                      <div className="p-4 text-[10px] text-[#64748b] font-mono text-center">Graph inference calculating...</div>
                    ) : (
                      (zoneIntel?.gnn?.xai?.top_neighbors || activeGnnData?.xai?.top_neighbors).map((n, i) => (
                        <div key={i} className="flex items-center justify-between p-2">
                          <span className="text-[10px] text-[#94a3b8] font-mono">{n.node_id}</span>
                          <div className="flex gap-4">
                            <span className="text-[9px] text-[#64748b]"><span className="text-[#94a3b8] font-mono">rank:</span> {n.rank}</span>
                            <span className="text-[9px] text-[#64748b]"><span className="text-[#94a3b8] font-mono">attn:</span> {n.attention?.toFixed(3)}</span>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>

              </div>
            )}
          </div>

          {/* Transaction Audit Log */}
          <div className="h-56 bg-[#0a0f18] border-t border-[#1e293b] flex flex-col">
            <div className="px-5 py-2.5 border-b border-[#1e293b] flex justify-between items-center bg-[#121826]">
              <span className="text-[9px] font-bold uppercase tracking-widest text-[#64748b]">Transaction Record</span>
              <span className="text-[9px] text-[#cbd5e1] font-mono">COUNT: {payouts.length}</span>
            </div>
            <div className="flex-1 overflow-y-auto no-scrollbar">
              {payouts.length === 0 ? (
                <div className="p-4 text-[10px] text-[#64748b] font-mono">No recent transactions recorded.</div>
              ) : (
                <table className="w-full text-left border-collapse">
                  <tbody>
                    {payouts.slice(0, 15).map((p, i) => {
                      const isDanger = p.decision === 'FAIL' || p.decision === 'REJECTED' || p.decision === 'ESCALATED'
                      const color = p.override_applied ? 'text-[#3b82f6]' : (isDanger ? 'text-[#ef4444]' : 'text-[#10b981]')
                      return (
                        <tr key={i} onClick={() => setAuditEvent(p)}
                          className="hover:bg-[#1e293b]/50 cursor-pointer transition-colors duration-200 border-b border-[#1e293b] last:border-0">
                          <td className="py-2.5 px-5 text-[10px] font-mono text-[#94a3b8] whitespace-nowrap">
                            {new Date(p.timestamp).toLocaleTimeString()}
                          </td>
                          <td className="py-2.5 px-2 text-[10px] text-[#cbd5e1] truncate max-w-[120px]">{p.name || 'Agent'}</td>
                          <td className="py-2.5 px-5 text-right font-mono text-[11px] font-bold">
                            <span className={color}>₹{p.amount}</span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      </div>

      <DecisionAuditModal
        isOpen={!!auditEvent}
        onClose={() => setAuditEvent(null)}
        eventData={auditEvent}
        adminId={user?.user_id || 'ADMIN'}
      />
      <AdminOverridePanel
        isOpen={opsPanelOpen}
        onClose={() => setOpsPanelOpen(false)}
        adminId={user?.user_id || 'ADMIN-101'}
      />
    </div>
  )
}

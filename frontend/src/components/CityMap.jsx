import { useState, useCallback, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Map, { Marker, Source, Layer, Popup, NavigationControl } from 'react-map-gl/mapbox'
import 'mapbox-gl/dist/mapbox-gl.css'
import { CloudRain, Car, Megaphone, RefreshCw, Zap, Activity, MapPin, Shield, CheckCircle } from 'lucide-react'

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || ''
const SIM_API = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

const ZONE_COLORS = { GREEN: '#10b981', YELLOW: '#f59e0b', RED: '#ef4444' }
const COMPANY_EMOJI = { Zomato: '🍕', Swiggy: '🛵', Uber: '🚗', Blinkit: '⚡' }

const DISRUPTIONS = [
  { id: 'rain',    label: 'Heavy Rain',   icon: CloudRain,  color: '#3b82f6', bg: 'rgba(59,130,246,0.12)' },
  { id: 'traffic', label: 'Traffic Jam',  icon: Car,        color: '#f59e0b', bg: 'rgba(245,158,11,0.12)' },
  { id: 'strike',  label: 'Strike',       icon: Megaphone,  color: '#ef4444', bg: 'rgba(239,68,68,0.12)' },
  { id: 'clear',   label: 'All Clear',    icon: CheckCircle,color: '#10b981', bg: 'rgba(16,185,129,0.12)' },
]

// Build a circle polygon (GeoJSON) around a lat/lon with ~radius_km
function makeCircleGeoJSON(lat, lon, radiusKm = 1.0, points = 32) {
  const coords = []
  for (let i = 0; i <= points; i++) {
    const angle = (i / points) * 2 * Math.PI
    // 1 degree lat ≈ 111km, 1 degree lon ≈ 111km * cos(lat)
    const dLat = (radiusKm / 111) * Math.sin(angle)
    const dLon = (radiusKm / (111 * Math.cos((lat * Math.PI) / 180))) * Math.cos(angle)
    coords.push([lon + dLon, lat + dLat])
  }
  return { type: 'Feature', geometry: { type: 'Polygon', coordinates: [coords] } }
}

// Build a FeatureCollection from zone list
function buildZoneGeoJSON(zones) {
  return {
    type: 'FeatureCollection',
    features: (zones || []).map(z => ({
      ...makeCircleGeoJSON(z.lat, z.lon, 1.2),
      properties: { id: z.id, name: z.name, state: z.state, risk: z.risk_score },
    })),
  }
}

// Live event ticker item
function TickerItem({ event }) {
  const typeColors = { WEATHER: '#3b82f6', TRAFFIC: '#f59e0b', STRIKE: '#ef4444', PAYOUT: '#10b981', SYSTEM: '#6366f1' }
  return (
    <motion.div
      className="flex items-center gap-2 px-3 py-1.5 rounded-lg shrink-0"
      style={{ background: 'rgba(255,255,255,0.04)', borderLeft: `2px solid ${typeColors[event.type] || '#6366f1'}` }}
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: typeColors[event.type] || '#6366f1' }}>{event.type}</span>
      <span className="text-[11px] text-slate-300 max-w-xs truncate">{event.msg}</span>
    </motion.div>
  )
}

export default function CityMap({ cityState, user, wsConnected }) {
  const [viewport, setViewport] = useState({ latitude: 13.047, longitude: 80.225, zoom: 11.5 })
  const [selectedZone, setSelectedZone] = useState(null)
  const [triggering, setTriggering] = useState(null)
  const [recentEvents, setRecentEvents] = useState([])
  const tickerRef = useRef(null)

  const zones   = cityState?.zones   || []
  const workers = cityState?.workers || []
  const events  = cityState?.events  || []

  // Accumulate events for ticker
  useEffect(() => {
    if (events.length > 0) {
      setRecentEvents(prev => [...events, ...prev].slice(0, 20))
    }
  }, [cityState?.timestamp])

  // Build GeoJSON for zone fill + borders
  const zoneGeoJSON = buildZoneGeoJSON(zones)

  // Fill paint expression
  const fillColorExpr = [
    'match', ['get', 'state'],
    'RED',    ZONE_COLORS.RED,
    'YELLOW', ZONE_COLORS.YELLOW,
    'GREEN',  ZONE_COLORS.GREEN,
    '#10b981'
  ]

  const handleTrigger = useCallback(async (id) => {
    setTriggering(id)
    try {
      const token = localStorage.getItem('snapinsure_token')
      await fetch(`${SIM_API}/sim/trigger`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ event_type: id }),
      })
    } catch (_) {}
    setTimeout(() => setTriggering(null), 1500)
  }, [])

  const myWorker = user ? workers.find(w => w.id === (user.user_id || 'ZOM-1001')) : null

  return (
    <div className="relative w-full h-[calc(100vh-112px)] flex flex-col">

      {/* ── Live event ticker ──────────────────────────────────────────── */}
      <div className="flex-shrink-0 border-b border-white/5 bg-card/70 px-4 py-2 overflow-hidden">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 flex-shrink-0">
            <Activity className="w-3.5 h-3.5 text-brand animate-pulse" />
            <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500">LIVE FEED</span>
          </div>
          <div ref={tickerRef} className="flex items-center gap-2 overflow-x-auto no-scrollbar">
            <AnimatePresence>
              {recentEvents.slice(0, 6).map((ev, i) => (
                <TickerItem key={`${ev.timestamp}-${i}`} event={ev} />
              ))}
              {recentEvents.length === 0 && (
                <span className="text-[11px] text-slate-600 animate-pulse">Monitoring city…</span>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>

      {/* ── Main area: map + control panel ─────────────────────────────── */}
      <div className="flex-1 flex overflow-hidden">

        {/* MAP */}
        <div className="flex-1 relative">
          <Map
            {...viewport}
            onMove={e => setViewport(e.viewState)}
            mapStyle="mapbox://styles/mapbox/dark-v11"
            mapboxAccessToken={MAPBOX_TOKEN}
            style={{ width: '100%', height: '100%' }}
            onClick={() => setSelectedZone(null)}
          >
            <NavigationControl position="bottom-right" />

            {/* Zone fill polygons */}
            {zones.length > 0 && (
              <Source id="zones" type="geojson" data={zoneGeoJSON}>
                <Layer
                  id="zone-fill"
                  type="fill"
                  paint={{
                    'fill-color': fillColorExpr,
                    'fill-opacity': [
                      'case',
                      ['==', ['get', 'state'], 'RED'],    0.28,
                      ['==', ['get', 'state'], 'YELLOW'], 0.20,
                      0.12
                    ],
                  }}
                />
                <Layer
                  id="zone-border"
                  type="line"
                  paint={{
                    'line-color': fillColorExpr,
                    'line-width': 1.5,
                    'line-opacity': 0.6,
                  }}
                />
              </Source>
            )}

            {/* Zone label markers (clickable) */}
            {zones.map(zone => (
              <Marker
                key={zone.id}
                latitude={zone.lat}
                longitude={zone.lon}
                onClick={e => { e.originalEvent.stopPropagation(); setSelectedZone(zone) }}
              >
                <motion.div
                  className="zone-label cursor-pointer select-none"
                  animate={{ scale: zone.state === 'RED' ? [1, 1.08, 1] : 1 }}
                  transition={{ duration: 1.5, repeat: zone.state === 'RED' ? Infinity : 0 }}
                  style={{
                    background: `${ZONE_COLORS[zone.state]}22`,
                    border: `1.5px solid ${ZONE_COLORS[zone.state]}`,
                    borderRadius: '8px',
                    padding: '4px 8px',
                    backdropFilter: 'blur(8px)',
                    boxShadow: zone.state === 'RED' ? `0 0 14px ${ZONE_COLORS[zone.state]}50` : 'none',
                  }}
                >
                  <p className="text-[10px] font-black uppercase" style={{ color: ZONE_COLORS[zone.state] }}>{zone.id}</p>
                  <p className="text-[9px] text-white/60 leading-tight">{zone.name}</p>
                </motion.div>
              </Marker>
            ))}

            {/* Zone popup on click */}
            {selectedZone && (
              <Popup
                latitude={selectedZone.lat}
                longitude={selectedZone.lon}
                onClose={() => setSelectedZone(null)}
                closeButton={true}
                anchor="bottom"
                style={{ padding: 0 }}
              >
                <div className="p-3 rounded-xl min-w-[160px]"
                  style={{ background: '#161b27', border: `1px solid ${ZONE_COLORS[selectedZone.state]}40` }}>
                  <p className="text-xs font-black text-white mb-1">{selectedZone.name} ({selectedZone.id})</p>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                      style={{ background: `${ZONE_COLORS[selectedZone.state]}22`, color: ZONE_COLORS[selectedZone.state] }}>
                      {selectedZone.state}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400">Risk: <span className="font-bold text-white">{(selectedZone.risk_score * 100).toFixed(0)}%</span></p>
                  <p className="text-[11px] text-slate-400">Workers in zone: <span className="font-bold text-white">
                    {workers.filter(w => w.zone_id === selectedZone.id).length}
                  </span></p>
                </div>
              </Popup>
            )}

            {/* Worker markers */}
            {workers.map(worker => (
              <Marker
                key={worker.id}
                latitude={worker.lat}
                longitude={worker.lon}
              >
                <div className="relative" title={`${worker.name} (${worker.company})`}>
                  {/* My worker has special highlight */}
                  {myWorker?.id === worker.id && (
                    <div className="absolute -inset-2 rounded-full border-2 border-brand/60 animate-ping opacity-50" />
                  )}
                  <div
                    className="w-6 h-6 rounded-full flex items-center justify-center text-sm border-2 border-white/20 shadow-lg"
                    style={{
                      background: ZONE_COLORS[worker.zone_state] + '33',
                      borderColor: myWorker?.id === worker.id ? '#6366f1' : ZONE_COLORS[worker.zone_state] + '80',
                      boxShadow: `0 0 8px ${ZONE_COLORS[worker.zone_state]}60`,
                    }}
                  >
                    <span style={{ fontSize: '10px' }}>{COMPANY_EMOJI[worker.company] || '📦'}</span>
                  </div>
                </div>
              </Marker>
            ))}
          </Map>

          {/* Map overlay: WS status */}
          <div className="absolute top-3 left-3 glass px-3 py-1.5 rounded-full flex items-center gap-2 pointer-events-none">
            <MapPin className="w-3 h-3 text-brandlt" />
            <span className="text-[10px] font-bold text-slate-300 uppercase tracking-widest">Chennai Live Map</span>
            <span className={`w-1.5 h-1.5 rounded-full ${wsConnected ? 'bg-safe animate-pulse' : 'bg-slate-600'}`} />
          </div>

          {/* Zone legend */}
          <div className="absolute bottom-10 left-3 glass rounded-xl p-3 pointer-events-none">
            <p className="text-[9px] font-bold text-slate-500 uppercase tracking-wider mb-2">Zone Status</p>
            {Object.entries(ZONE_COLORS).map(([state, color]) => (
              <div key={state} className="flex items-center gap-2 mb-1">
                <div className="w-3 h-3 rounded-full" style={{ background: color }} />
                <span className="text-[10px] text-slate-400">{state}</span>
              </div>
            ))}
          </div>
        </div>

        {/* ── Control Panel ───────────────────────────────────────────── */}
        <div className="w-72 flex-shrink-0 border-l border-white/7 bg-card/80 overflow-y-auto flex flex-col gap-0">

          {/* Simulation Control */}
          <div className="p-4 border-b border-white/7">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-3 flex items-center gap-2">
              <Zap className="w-3 h-3 text-brand" />
              Simulation Control
            </p>
            <div className="grid grid-cols-2 gap-2">
              {DISRUPTIONS.map(d => {
                const Icon = d.icon
                const isLoading = triggering === d.id
                return (
                  <motion.button
                    key={d.id}
                    onClick={() => handleTrigger(d.id)}
                    disabled={!!triggering}
                    className="flex flex-col items-center gap-2 p-3 rounded-xl border border-white/8 hover:border-white/16 transition-all text-center disabled:opacity-60"
                    style={{ background: isLoading ? d.bg : 'rgba(255,255,255,0.03)' }}
                    whileTap={{ scale: 0.95 }}
                  >
                    {isLoading ? (
                      <RefreshCw className="w-4 h-4 animate-spin" style={{ color: d.color }} />
                    ) : (
                      <Icon className="w-4 h-4" style={{ color: d.color }} />
                    )}
                    <span className="text-[10px] font-semibold text-slate-300">{d.label}</span>
                  </motion.button>
                )
              })}
            </div>
          </div>

          {/* Zone Summary */}
          <div className="p-4 border-b border-white/7">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-3">Zone Overview</p>
            <div className="space-y-2">
              {zones.map(z => (
                <motion.div
                  key={z.id}
                  className="flex items-center gap-3 p-2.5 rounded-xl cursor-pointer transition-all"
                  style={{
                    background: selectedZone?.id === z.id ? `${ZONE_COLORS[z.state]}15` : 'rgba(255,255,255,0.03)',
                    border: `1px solid ${selectedZone?.id === z.id ? ZONE_COLORS[z.state] + '40' : 'rgba(255,255,255,0.06)'}`,
                  }}
                  onClick={() => { setSelectedZone(z); setViewport(v => ({ ...v, latitude: z.lat, longitude: z.lon, zoom: 13 })) }}
                  animate={{ opacity: 1 }}
                >
                  <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: ZONE_COLORS[z.state], boxShadow: `0 0 6px ${ZONE_COLORS[z.state]}60` }} />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold text-slate-300 truncate">{z.name}</p>
                    <p className="text-[10px] text-slate-600">{z.id} • Risk {(z.risk_score * 100).toFixed(0)}%</p>
                  </div>
                  <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-md" style={{ background: `${ZONE_COLORS[z.state]}20`, color: ZONE_COLORS[z.state] }}>
                    {z.state}
                  </span>
                </motion.div>
              ))}
            </div>
          </div>

          {/* Worker positions */}
          <div className="p-4">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-3">Workers ({workers.length})</p>
            <div className="space-y-1.5 max-h-64 overflow-y-auto custom-scrollbar">
              {workers.map(w => (
                <div key={w.id}
                  className="flex items-center gap-2.5 p-2 rounded-lg"
                  style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.05)' }}>
                  <span className="text-base leading-none">{COMPANY_EMOJI[w.company] || '📦'}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] font-semibold text-slate-200 truncate">{w.name}</p>
                    <p className="text-[9px] text-slate-600">{w.zone_id} • ₹{w.last_payout} last</p>
                  </div>
                  <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: ZONE_COLORS[w.zone_state] }} />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

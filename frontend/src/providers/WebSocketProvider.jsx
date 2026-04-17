import { useEffect, useRef } from 'react'
import { useSimulationStore } from '../store/useSimulationStore'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/city'

export default function WebSocketProvider({ children }) {
  const wsRef = useRef(null)
  const reconnectTimerRef = useRef(null)

  const { 
    setWsConnected, 
    setCityState, 
    addEarning, 
    addDisruption, 
    addClaim, 
    addLiveEvent,
    setActiveClaim
  } = useSimulationStore()

  useEffect(() => {
    const connectWs = () => {
      if (wsRef.current?.readyState === WebSocket.OPEN) return
      
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('[WS] Connected to Live Simulator')
        setWsConnected(true)
        clearTimeout(reconnectTimerRef.current)
      }

      ws.onmessage = (e) => {
        try {
          const payload = JSON.parse(e.data)

          // Route the events directly into Zustand based on their explicit types
          if (payload.type === 'city_update') {
            setCityState(payload) // Initial sync
          } 
          else if (payload.type === 'new_earning') {
            addEarning(payload.data)
            addLiveEvent({
                type: 'PAYOUT',
                msg: `₹${payload.data.earnings} earned by ${payload.data.worker_name} in ${payload.data.zone}`,
                timestamp: payload.data.timestamp,
                amount: payload.data.earnings
            })
          } 
          else if (payload.type === 'disruption_update') {
            addDisruption(payload.data)
            addLiveEvent({
                type: payload.data.event_type,
                msg: `⚠️ ${(payload.data.severity || 'moderate').toUpperCase()} Disruption spotted in ${payload.data.zone_name}`,
                timestamp: payload.data.timestamp
            })
          }
          else if (payload.type === 'new_claim' || payload.type === 'claim_update') {
            addClaim(payload.data)
            setActiveClaim(payload.data)
            addLiveEvent({
                type: 'SYSTEM',
                msg: `Claim ${payload.data.claim_id || ''} ${payload.data.status} for ${payload.data.worker_name || 'Worker'}`,
                timestamp: payload.data.timestamp || Date.now(),
            })
            // Auto clear progress bar after 6 seconds if status suggests it's done
            if (['processing', 'approved', 'paid'].includes(payload.data.status)) {
               setTimeout(() => {
                 useSimulationStore.getState().setActiveClaim(null);
               }, 6000);
            }
          }
          // Intelligence: NLP Event Updates (Strikes, Protests, etc.)
          else if (payload.type === 'event_update') {
            addLiveEvent({
                type: 'STRIKE',
                msg: `📢 INTEL: ${payload.data.title} detected in ${payload.data.zone_id}`,
                timestamp: payload.data.timestamp,
                zone_id: payload.data.zone_id
            })
          }
          // Intelligence: Weather Alerts (Rain, Floods, etc.)
          else if (payload.type === 'weather_update') {
            addLiveEvent({
                type: 'WEATHER',
                msg: `☁️ WEATHER: ${(payload.data.description || 'Unknown').toUpperCase()} in ${payload.data.city} (Risk: ${payload.data.risk})`,
                timestamp: payload.data.timestamp,
                zone: payload.data.risk
            })
          }
          // Intelligence: ESG/Green Rewards
          else if (payload.type === 'esg_update') {
            addLiveEvent({
                type: 'SYSTEM',
                msg: `🌱 ESG: ${payload.data.worker_name} earned +${payload.data.carbon_saved}kg carbon savings!`,
                timestamp: payload.data.timestamp
            })
          }
          // Generic Notifications (e.g., from old synchronous triggers)
          else if (payload.type === 'NOTIFICATION' && payload.payload) {
             addLiveEvent(payload.payload)
          }


        } catch (err) {
          console.error('[WS] Error parsing message', err)
        }
      }

      ws.onerror = (error) => {
        console.error('[WS] Error', error)
        setWsConnected(false)
      }

      ws.onclose = () => {
        console.warn('[WS] Disconnected, attempting reconnect in 3s...')
        setWsConnected(false)
        reconnectTimerRef.current = setTimeout(connectWs, 3000)
      }
    }

    connectWs()

    return () => {
      wsRef.current?.close()
      clearTimeout(reconnectTimerRef.current)
    }
  }, [setWsConnected, setCityState, addEarning, addDisruption, addClaim, addLiveEvent, setActiveClaim])

  return children
}

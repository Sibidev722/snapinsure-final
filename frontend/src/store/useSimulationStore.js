import { create } from 'zustand'

export const useSimulationStore = create((set) => ({
  wsConnected: false,
  setWsConnected: (status) => set({ wsConnected: status }),

  // Full City State (Fallback / Initial Sync)
  cityState: null,
  setCityState: (state) => set({ cityState: state }),

  // Micro DB Streams
  earnings: [],
  disruptions: [],
  claims: [],

  // Max number of events to retain in memory to prevent crashes
  MAX_EVENTS: 50,

  addEarning: (earning) => set((state) => ({
    earnings: [earning, ...state.earnings].slice(0, state.MAX_EVENTS)
  })),

  addDisruption: (disruption) => set((state) => ({
    disruptions: [disruption, ...state.disruptions].slice(0, state.MAX_EVENTS)
  })),

  addClaim: (claim) => set((state) => ({
    claims: [claim, ...state.claims].slice(0, state.MAX_EVENTS)
  })),

  // Feature: Active Claim Progress Bar Tracking
  activeClaim: null,
  setActiveClaim: (claim) => set({ activeClaim: claim }),

  // ── Intelligence Audit Feed ──────────────────────────────────────────
  liveEventsFeed: [],
  addLiveEvent: (eventRaw) => set((state) => {
    // Advanced Deduplication: Use explicit ID or a unique hash of type+zone+timestamp
    const evId = eventRaw.id || `${eventRaw.type}-${eventRaw.zone_id || 'global'}-${eventRaw.timestamp || Date.now()}`
    
    // Prevent double-renders of the same intelligence signal
    if (state.liveEventsFeed.some(e => e.id === evId)) return state
    
    return {
      liveEventsFeed: [
        { ...eventRaw, id: evId, receivedAt: Date.now() }, 
        ...state.liveEventsFeed
      ].slice(0, state.MAX_EVENTS)
    }
  }),
}))


import { useState, useEffect, useRef } from 'react';

/**
 * useOptimizedTelemetry
 * Applies debouncing and state diffing to prevent aggressive React re-renders 
 * on high-frequency websocket streams.
 * 
 * @param {any} liveData - The fast-updating raw data stream.
 * @param {number} delay - Debounce duration in ms (default 300).
 * @returns {any} The stable, debounced data state.
 */
export function useOptimizedTelemetry(liveData, delay = 300) {
  const [debouncedData, setDebouncedData] = useState(liveData);
  const dataRef = useRef(liveData);

  useEffect(() => {
    // Basic Diffing (Optional depth check could be added)
    // If exact same object reference or primitive, skip.
    if (liveData === dataRef.current) return;
    
    // For arrays or objects, a shallow stringify diff prevents identical 
    // payloads from causing virtual DOM reconciliation on every tick.
    try {
      if (JSON.stringify(liveData) === JSON.stringify(dataRef.current)) {
        return; 
      }
    } catch(e) {
      // Circular or huge payloads fall back to debouncing
    }
    
    const handler = setTimeout(() => {
      setDebouncedData(liveData);
      dataRef.current = liveData;
    }, delay);

    return () => clearTimeout(handler);
  }, [liveData, delay]);

  return debouncedData;
}

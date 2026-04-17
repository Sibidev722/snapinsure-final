import React, { useState, useEffect, useRef } from 'react';

/**
 * AnimatedNumber
 * Smoothly interpolates numeric values without triggering massive React component
 * tree re-renders, preventing UI flickering on high-frequency real-time updates.
 */
export default function AnimatedNumber({ 
  value, 
  format = (v) => v.toFixed(2), 
  duration = 400, 
  className = "" 
}) {
  const [displayValue, setDisplayValue] = useState(value);
  // Keep track of the current animating state to avoid jittering
  const valueRef = useRef(value);

  useEffect(() => {
    if (value === valueRef.current) return;
    
    let startTimestamp;
    const startValue = displayValue;
    const change = value - startValue;
    
    // Ease-out function for smooth deceleration
    const easeOutQuart = (t) => 1 - Math.pow(1 - t, 4);

    const animate = (timestamp) => {
      if (!startTimestamp) startTimestamp = timestamp;
      const progress = Math.min((timestamp - startTimestamp) / duration, 1);
      
      const currentVal = startValue + (change * easeOutQuart(progress));
      setDisplayValue(currentVal);
      
      if (progress < 1) {
        requestAnimationFrame(animate);
      } else {
        setDisplayValue(value);
        valueRef.current = value;
      }
    };
    
    const animationId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationId);
  }, [value, duration]); // Intentionally not including displayValue 

  return <span className={className}>{format(displayValue)}</span>;
}

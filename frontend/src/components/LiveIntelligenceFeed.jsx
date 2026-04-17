import React, { useState, useEffect } from 'react';
import { Rss, ExternalLink } from 'lucide-react';

const SIM_API = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

export default function LiveIntelligenceFeed() {
  const [feed, setFeed] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(new Date());

  const fetchIntelligence = async () => {
    try {
      const response = await fetch(`${SIM_API}/zone-state/intelligence`);
      if (response.ok) {
        const data = await response.json();
        setFeed(data.feed || []);
        setLastUpdated(new Date());
      }
    } catch (e) {
      console.error("Failed to fetch live intelligence", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIntelligence();
    // Poll every 5 minutes (300,000ms)
    const interval = setInterval(fetchIntelligence, 300000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="w-[380px] h-[340px] bg-[#121826] border border-[#1e293b] rounded flex flex-col shadow-2xl pointer-events-auto">
      
      {/* ── Terminal Header ── */}
      <div className="px-4 py-2 border-b border-[#1e293b] flex items-center justify-between bg-[#0a0f18] shrink-0">
        <div className="flex items-center gap-2">
          <Rss className="w-3.5 h-3.5 text-[#3b82f6]" />
          <h3 className="text-[10px] font-bold text-[#e2e8f0] uppercase tracking-widest">
            OSINT Intelligence Feed
          </h3>
        </div>
        <div className="flex items-center gap-2 text-[9px] font-mono text-[#64748b]">
          <span className="w-2 h-2 bg-[#10b981] rounded-full" />
          <span>GDELT SYNC</span>
          <span>•</span>
          <span>{lastUpdated.toLocaleTimeString()}</span>
        </div>
      </div>

      {/* ── Feed List ── */}
      <div className="flex-1 overflow-y-auto no-scrollbar bg-[#0a0f18]">
        {loading && feed.length === 0 ? (
          <div className="flex items-center justify-center h-full text-[10px] text-[#64748b] font-mono uppercase tracking-widest animate-pulse">
            Establishing Satellite Uplink...
          </div>
        ) : feed.length === 0 ? (
          <div className="flex items-center justify-center h-full text-[10px] text-[#64748b] font-mono uppercase tracking-widest text-center px-4">
            Awaiting geoeconomic disruption events...
          </div>
        ) : (
          <div className="divide-y divide-[#1e293b]">
            {feed.map((item, i) => {
              const isDanger = item.tone === 'NEGATIVE';
              const isSafe = item.tone === 'POSITIVE';
              const color = isDanger ? 'text-[#ef4444]' : isSafe ? 'text-[#10b981]' : 'text-[#f59e0b]';
              const bg = isDanger ? 'bg-[#ef4444]/10' : isSafe ? 'bg-[#10b981]/10' : 'bg-[#f59e0b]/10';
              
              return (
                <div key={i} className="p-3 hover:bg-[#1e293b]/50 transition-colors flex flex-col gap-2">
                  <div className="flex justify-between items-start">
                    
                    {/* Timestamp & Icon */}
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] bg-[#121826] border border-[#1e293b] w-6 h-6 flex items-center justify-center rounded">
                        {item.icon}
                      </span>
                      <span className="text-[9px] font-mono text-[#94a3b8]">
                        {item.timestamp ? new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'LIVE'}
                      </span>
                    </div>

                    {/* Tone Badge */}
                    <div className="flex flex-col items-end">
                      <span className={`text-[8px] font-black uppercase tracking-widest px-2 py-0.5 rounded border ${color} ${bg} border-current opacity-80`}>
                        {item.tone}
                      </span>
                    </div>
                  </div>
                  
                  {/* Headline */}
                  <a href={item.url || '#'} target="_blank" rel="noreferrer" className="block group">
                    <h4 className="text-[11px] font-medium text-[#e2e8f0] leading-snug group-hover:text-[#3b82f6] transition-colors">
                      {item.title}
                    </h4>
                  </a>
                  
                  {/* Footer Metrics */}
                  <div className="flex items-center justify-between mt-1 pt-1 border-t border-[#1e293b]/50">
                    <span className="text-[9px] font-mono text-[#64748b]">SYS-SRC: {item.source.toUpperCase()}</span>
                    <div className="flex items-center gap-1.5">
                      <span className="text-[9px] text-[#64748b] uppercase tracking-wider">Impact:</span>
                      <span className={`text-[10px] font-black font-mono ${color}`}>
                        {(item.impact_score * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

    </div>
  );
}

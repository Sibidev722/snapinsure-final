import React, { useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, Cell } from 'recharts';
import { Database, Network, Fingerprint } from 'lucide-react';

export default function AIExplainabilityPanel({ zoneData, gnnData }) {
  // 1. Parse and sort metric data
  const chartData = useMemo(() => {
    // If we have actual GNN Explainer data (XAI payload)
    if (gnnData?.xai?.top_features) {
      return gnnData.xai.top_features.map((f) => ({
        name: f.label || f.name,
        key: f.name,
        score: f.importance || 0,
        desc: `GNN Importance: ${(f.importance * 100).toFixed(1)}%. Factor ${f.direction > 0 ? 'amplifies' : 'mitigates'} risk.`
      })).sort((a, b) => b.score - a.score);
    }
    
    // Fallback to raw heuristic signals if GNN is initializing
    if (!zoneData) return [];
    
    const raw = [
      { name: 'Weather',   key: 'weather',   score: zoneData.weather?.score || 0,    desc: 'Meteorological disruption multiplier based on live APIs.' },
      { name: 'Traffic',   key: 'traffic',   score: zoneData.traffic?.score || 0,    desc: 'OSRM routing delay and congestion density.' },
      { name: 'Demand',    key: 'demand',    score: zoneData.demand?.score || 0,     desc: 'Spike in active delivery requests relative to baseline.' },
      { name: 'News/NLP',  key: 'disruption',score: zoneData.disruption?.score || 0, desc: 'Social unrest parsed from real-time global news APIs.' },
    ];
    raw.sort((a, b) => b.score - a.score);
    return raw;
  }, [zoneData, gnnData]);

  // 2. Generate Narrative Explanation
  const explanation = useMemo(() => {
    if (gnnData?.xai?.explanation) {
      return gnnData.xai.explanation;
    }
    
    if (chartData.length === 0 || chartData[0].score < 0.1) {
      return "Current telemetry indicates stable baseline conditions across the sector. No significant anomalies detected by the Graph Attention Network.";
    }

    const topFactor = chartData[0];
    const secondFactor = chartData[1];

    if (topFactor.score > 0.6) {
      if (secondFactor.score > 0.4) {
        return `Algorithm detected elevated risk primarily driven by an anomalous surge in ${topFactor.name.toLowerCase()} combined with structural impacts from ${secondFactor.name.toLowerCase()}.`;
      }
      return `Critical risk deviation solely attributed to extreme ${topFactor.name.toLowerCase()} conditions dominating the attention matrix.`;
    }

    return `Moderate localized turbulence detected, primarily influenced by ${topFactor.name.toLowerCase()} vectors.`;
  }, [chartData, gnnData]);

  if (!zoneData) return null;

  const topFactorName = chartData.length > 0 ? chartData[0].name : '';

  // Custom Tooltip component for Recharts
  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-[#121826] border border-[#1e293b] p-3 rounded shadow-xl max-w-[200px]">
          <p className="text-[11px] font-bold text-[#e2e8f0] uppercase tracking-wider mb-1">{data.name}</p>
          <p className="text-[10px] text-[#94a3b8] leading-relaxed mb-2">{data.desc}</p>
          <p className="text-[10px] font-mono text-[#3b82f6]">Weight: {data.score.toFixed(3)}</p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-6">
      {/* ── Narrative Box ── */}
      <div className="bg-[#121826] border border-[#1e293b] p-4 rounded-lg relative overflow-hidden">
        <div className="absolute top-0 left-0 w-1 h-full bg-[#3b82f6]" />
        <h3 className="text-[10px] font-bold text-[#64748b] uppercase tracking-widest mb-1.5 flex items-center gap-1.5">
          <Fingerprint className="w-3 h-3 text-[#3b82f6]" /> AI Interpretation
        </h3>
        <p className="text-[11px] text-[#cbd5e1] leading-relaxed font-mono">
          "{explanation}"
        </p>
      </div>

      {/* ── Feature Importance Bar Chart ── */}
      <div>
        <h3 className="text-[10px] font-bold text-[#64748b] uppercase tracking-widest mb-3 flex items-center gap-1.5">
          <Database className="w-3 h-3" /> Feature Weight Attribution
        </h3>
        <div className="h-[140px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ top: 0, right: 10, left: 0, bottom: 0 }}
            >
              <XAxis 
                type="number" 
                domain={[0, 1]} 
                hide 
              />
              <YAxis 
                type="category" 
                dataKey="name" 
                width={70} 
                axisLine={false} 
                tickLine={false} 
                tick={{ fill: '#64748b', fontSize: 10, fontWeight: 500 }} 
              />
              <RechartsTooltip 
                content={<CustomTooltip />} 
                cursor={{ fill: '#1e293b', opacity: 0.4 }}
              />
              {/* Smooth constrained animation driven by Recharts natively */}
              <Bar 
                dataKey="score" 
                radius={[0, 4, 4, 0]} 
                barSize={16} 
                isAnimationActive={true}
                animationDuration={800}
                animationEasing="ease-out"
              >
                {chartData.map((entry, index) => (
                  <Cell 
                    key={`cell-${index}`} 
                    fill={entry.name === topFactorName && entry.score > 0.2 ? '#ef4444' : '#1e293b'} 
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

    </div>
  );
}

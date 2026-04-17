import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, ShieldAlert, CheckCircle, ChevronDown, ChevronUp, BrainCircuit, Shield } from 'lucide-react';

// Sub-component for individual Agent Cards
function AgentCard({ agentName, score, confidence, reason }) {
  const [expanded, setExpanded] = useState(false);
  const [animatedScore, setAnimatedScore] = useState(0);

  // Smooth score animation on mount or update
  useEffect(() => {
    let startTime;
    const duration = 1000; // 1 second animation
    const easeOutQuart = t => 1 - Math.pow(1 - t, 4);
    
    const animate = (time) => {
      if (!startTime) startTime = time;
      const progress = (time - startTime) / duration;
      
      if (progress < 1) {
        setAnimatedScore(score * easeOutQuart(progress));
        requestAnimationFrame(animate);
      } else {
        setAnimatedScore(score);
      }
    };
    
    requestAnimationFrame(animate);
  }, [score]);

  const isSafe = score > 0.7;
  const isWarn = score > 0.4 && score <= 0.7;

  return (
    <div className="bg-[#121826] border border-[#1e293b] rounded-xl overflow-hidden mb-3 shadow-[0_4px_20px_rgba(0,0,0,0.3)] transition-all hover:border-[#334155]">
      <div 
        className="p-4 cursor-pointer flex items-center justify-between"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <div className="shrink-0">
            {isSafe ? <CheckCircle className="w-5 h-5 text-[#10b981]" /> :
             isWarn ? <Activity className="w-5 h-5 text-[#f59e0b]" /> :
                      <ShieldAlert className="w-5 h-5 text-[#ef4444]" />}
          </div>
          <div>
            <h4 className="text-xs font-bold text-[#e2e8f0] uppercase tracking-widest">{agentName}</h4>
            <p className="text-[10px] text-[#64748b] font-mono mt-0.5">Confidence: {(confidence * 100).toFixed(1)}%</p>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          <div className="text-right">
            <p className="text-[9px] uppercase tracking-widest text-[#64748b] mb-0.5">Agent Score</p>
            <p className={`text-sm font-black font-mono ${isSafe ? 'text-[#10b981]' : isWarn ? 'text-[#f59e0b]' : 'text-[#ef4444]'}`}>
              {animatedScore.toFixed(3)}
            </p>
          </div>
          {expanded ? <ChevronUp className="w-4 h-4 text-[#64748b]" /> : <ChevronDown className="w-4 h-4 text-[#64748b]" />}
        </div>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: 'easeInOut' }}
          >
            <div className="px-4 pb-4 pt-1 border-t border-[#1e293b]">
              <p className="text-[11px] text-[#cbd5e1] bg-[#0a0f18] p-3 rounded border border-[#1e293b] leading-relaxed italic">
                "{reason}"
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function MultiAgentDecisionPanel({ agents, finalScore, finalDecision }) {
  if (!agents || agents.length === 0) return null;

  const isSafe = finalScore > 0.7;
  const isWarn = finalScore > 0.4 && finalScore <= 0.7;

  return (
    <div className="flex flex-col gap-6">
      
      {/* ── Individual Agents Section ── */}
      <div>
        <h3 className="text-[10px] font-bold text-[#64748b] uppercase tracking-widest mb-3 flex items-center gap-1.5">
          <BrainCircuit className="w-3 h-3 text-[#3b82f6]" /> Neural Consensus Agents
        </h3>
        {agents.map((agent, i) => (
          <AgentCard 
            key={i}
            agentName={agent.agent}
            score={agent.score}
            confidence={agent.confidence}
            reason={agent.reason}
          />
        ))}
      </div>

      {/* ── Final Weighted Consensus Section ── */}
      <div className="bg-gradient-to-br from-[#121826] to-[#0a0f18] border border-[#1e293b] rounded-xl p-5 shadow-[0_10px_30px_rgba(0,0,0,0.4)] relative overflow-hidden">
        
        {/* Subtle background glow based on decision */}
        <div className={`absolute -right-20 -top-20 w-48 h-48 rounded-full blur-[80px] opacity-20 pointer-events-none
          ${isSafe ? 'bg-[#10b981]' : isWarn ? 'bg-[#f59e0b]' : 'bg-[#ef4444]'}`} />

        <h3 className="text-[10px] font-bold text-[#64748b] uppercase tracking-widest mb-4 flex items-center gap-1.5 border-b border-[#1e293b] pb-2">
          <Shield className="w-3 h-3 text-[#cbd5e1]" /> Final Adjudication
        </h3>
        
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-[#94a3b8] uppercase tracking-widest mb-1">Weighted Consensus Score</p>
            <div className="flex items-baseline gap-2">
              <span className="text-4xl font-black font-mono text-[#e2e8f0]">
                {finalScore.toFixed(3)}
              </span>
              <span className="text-[10px] text-[#64748b] font-mono">/ 1.000</span>
            </div>
          </div>
          
          <div className="flex flex-col items-end">
            <p className="text-[9px] text-[#64748b] uppercase tracking-widest mb-1.5">Adjudicator Gate</p>
            <div className={`px-4 py-2 rounded-lg border flex items-center gap-2 shadow-lg
              ${isSafe ? 'bg-[#10b981]/10 border-[#10b981]/30 text-[#10b981]' : 
                isWarn ? 'bg-[#f59e0b]/10 border-[#f59e0b]/30 text-[#f59e0b]' : 
                'bg-[#ef4444]/10 border-[#ef4444]/30 text-[#ef4444]'}`}
            >
              <div className={`w-2 h-2 rounded-full animate-pulse ${isSafe ? 'bg-[#10b981]' : isWarn ? 'bg-[#f59e0b]' : 'bg-[#ef4444]'}`} />
              <span className="text-sm font-black tracking-widest uppercase">{finalDecision}</span>
            </div>
          </div>
        </div>

        {/* Confidence scale visualizer */}
        <div className="mt-5 w-full h-1.5 bg-[#1e293b] rounded-full overflow-hidden flex relative">
          <motion.div 
            className={`h-full ${isSafe ? 'bg-[#10b981]' : isWarn ? 'bg-[#f59e0b]' : 'bg-[#ef4444]'}`}
            initial={{ width: 0 }}
            animate={{ width: `${finalScore * 100}%` }}
            transition={{ duration: 1.2, ease: "easeOut" }}
          />
          {/* Threshold markers */}
          <div className="absolute top-0 bottom-0 left-[40%] w-[1px] bg-white/20" />
          <div className="absolute top-0 bottom-0 left-[70%] w-[1px] bg-white/20" />
        </div>
        <div className="flex justify-between mt-1 px-1">
          <span className="text-[8px] text-[#64748b] font-mono">0.0 (FAIL)</span>
          <span className="text-[8px] text-[#64748b] font-mono">0.4 (REVIEW)</span>
          <span className="text-[8px] text-[#64748b] font-mono">0.7 (PASS)</span>
          <span className="text-[8px] text-[#64748b] font-mono">1.0</span>
        </div>

      </div>
    </div>
  );
}

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, ShieldAlert, CheckCircle, Database, Shield, Zap, Server, Sliders, MessageSquare } from 'lucide-react';
import MultiAgentDecisionPanel from './MultiAgentDecisionPanel';

// SIM_API points to the backend URL
const SIM_API = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

export default function DecisionAuditModal({ isOpen, onClose, eventData, adminId = "ADMIN-101" }) {
  const [overrideReason, setOverrideReason] = useState("");
  const [overrideLoading, setOverrideLoading] = useState(false);
  const [overrideSuccess, setOverrideSuccess] = useState(false);
  const [overrideError, setOverrideError] = useState("");

  if (!isOpen || !eventData) return null;

  // Attempt to extract the audit trail either directly or from the event payload
  const trail = eventData.audit_trail || eventData.data?.audit_trail || eventData.data;

  // We only show the modal if we have a valid audit trail
  if (!trail || !trail.agents) return null;

  const adjResult = trail.agents.find(a => a.agent === 'AdjudicatorAgent');
  const envResult = trail.agents.find(a => a.agent === 'EnvironmentAgent');
  const isRejected = trail.decision === 'REJECTED' || trail.decision === 'FAIL';
  
  // Is this overridden?
  const isOverridden = trail.effective_decision === 'APPROVED_BY_OVERRIDE' || trail.override_applied;

  const handleOverride = async () => {
    if (overrideReason.length < 10) {
      setOverrideError("Reason must be at least 10 characters.");
      return;
    }
    
    setOverrideLoading(true);
    setOverrideError("");
    setOverrideSuccess(false);

    try {
      const response = await fetch(`${SIM_API}/override/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          claim_id: trail.worker_id + "-" + Date.now().toString().slice(-4), // Mock UUID since missing in raw trail
          decision: adjResult,
          admin_id: adminId,
          override_reason: overrideReason
        })
      });

      const data = await response.json();
      if (!response.ok) {
        setOverrideError(data.detail || data.reason || "Override failed.");
      } else {
        setOverrideSuccess(true);
        // We mutate locally for fast UI update, though optimally this comes from WS
        trail.override_applied = true;
        trail.effective_decision = 'APPROVED_BY_OVERRIDE';
      }
    } catch (e) {
      setOverrideError("Network error validating override.");
    } finally {
      setOverrideLoading(false);
    }
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6 pb-20">
        <motion.div 
          initial={{ opacity: 0 }} 
          animate={{ opacity: 1 }} 
          exit={{ opacity: 0 }} 
          className="absolute inset-0 bg-[#0B0F14]/80 backdrop-blur-md"
          onClick={onClose}
        />
        
        <motion.div
          initial={{ opacity: 0, y: 30, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 20, scale: 0.95 }}
          className="bg-card glass border border-white/10 shadow-2xl rounded-2xl w-full max-w-2xl max-h-[85vh] flex flex-col relative z-10 overflow-hidden"
        >
          {/* Header */}
          <div className="px-6 py-4 border-b border-white/5 flex items-center justify-between shrink-0 bg-white/5">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-surface/50 flex items-center justify-center border border-white/10">
                <Shield className="w-4 h-4 text-brand" />
              </div>
              <div>
                <h2 className="text-sm font-black text-white uppercase tracking-widest">XAI Decision Audit</h2>
                <p className="text-[10px] text-slate-400 font-mono">Worker: {trail.worker_id} • {new Date(trail.timestamp).toLocaleTimeString()}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              {isOverridden ? (
                <span className="bg-brand/20 text-brand border border-brand/30 px-3 py-1 rounded text-[10px] font-black tracking-widest uppercase">
                  Override Active
                </span>
              ) : (
                <span className={`px-3 py-1 rounded text-[10px] font-black tracking-widest uppercase border ${
                  trail.decision === 'APPROVED' ? 'bg-safe/20 text-safe border-safe/30' :
                  trail.decision === 'ESCALATED' ? 'bg-warn/20 text-warn border-warn/30' :
                  'bg-danger/20 text-danger border-danger/30'
                }`}>
                  {trail.decision}
                </span>
              )}
              <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors text-xl font-light">×</button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto no-scrollbar p-6 space-y-6">
            
            {/* Top Stat Row */}
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-[#0B0F14] border border-white/5 rounded-xl p-3">
                <p className="text-[9px] uppercase tracking-wider text-slate-500 mb-1 flex items-center gap-1"><Server className="w-3 h-3"/> Payout</p>
                <p className="text-xl font-black text-white font-mono">₹{trail.payout_request}</p>
              </div>
              <div className="bg-[#0B0F14] border border-white/5 rounded-xl p-3">
                <p className="text-[9px] uppercase tracking-wider text-slate-500 mb-1 flex items-center gap-1"><Sliders className="w-3 h-3"/> Confidence</p>
                <p className="text-xl font-black text-white font-mono">{(trail.final_confidence * 100).toFixed(1)}%</p>
              </div>
              <div className="bg-[#0B0F14] border border-white/5 rounded-xl p-3">
                <p className="text-[9px] uppercase tracking-wider text-slate-500 mb-1 flex items-center gap-1"><Zap className="w-3 h-3"/> Latency</p>
                <p className="text-xl font-black text-white font-mono">{trail.latency_ms}ms</p>
              </div>
            </div>

            {/* AI Agent Breakdown using new Panel */}
            <div className="mb-8">
              {adjResult?.agent_breakdown ? (
                <MultiAgentDecisionPanel 
                  agents={adjResult.agent_breakdown} 
                  finalScore={adjResult.final_score || trail.final_confidence || 0}
                  finalDecision={trail.decision}
                />
              ) : (
                <p className="text-xs text-slate-500 italic">No detailed breakdown found for this trace.</p>
              )}
            </div>

            {/* GNN Info */}
            {envResult && (
               <div>
                 <h3 className="text-[10px] font-mono uppercase tracking-widest text-slate-500 mb-3 border-b border-white/10 pb-2">Environment Risk Profiler</h3>
                 <div className="bg-[#0B0F14] border border-brand/20 p-4 rounded-xl">
                   <div className="flex justify-between items-start mb-2">
                     <p className="text-xs text-brand font-bold uppercase tracking-widest flex items-center gap-1.5">
                       <Database className="w-3 h-3" /> GNN Decision Log
                     </p>
                     <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${envResult.regime === 'HIGH' ? 'bg-danger/20 text-danger' : envResult.regime === 'MEDIUM' ? 'bg-warn/20 text-warn' : 'bg-safe/20 text-safe'}`}>
                       Regime: {envResult.regime}
                     </span>
                   </div>
                   <p className="text-[11px] text-slate-300 leading-relaxed font-mono">
                     {envResult.explanation}
                   </p>
                 </div>
               </div>
            )}

            {/* Overrides */}
            {isRejected && !isOverridden && (
              <div className="border border-danger/30 bg-danger/5 rounded-xl p-4 mt-6">
                <h3 className="text-[10px] font-black uppercase tracking-widest text-danger mb-2 flex items-center gap-2">
                  <ShieldAlert className="w-3 h-3" /> Human-in-the-Loop Override
                </h3>
                <p className="text-[10px] text-slate-400 mb-3">
                  This transaction was securely blocked by AI consensus. As an admin ({adminId}), you can override this block if you possess external verification ground-truth.
                </p>
                <div className="flex gap-2">
                  <input 
                    type="text" 
                    value={overrideReason}
                    onChange={(e) => setOverrideReason(e.target.value)}
                    placeholder="Provide detailed justification (min 10 chars)..."
                    className="flex-1 bg-surface border border-danger/20 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-danger/50"
                  />
                  <button 
                    onClick={handleOverride}
                    disabled={overrideLoading}
                    className="bg-danger hover:bg-danger/80 text-white font-bold uppercase tracking-wider text-[10px] px-4 py-2 rounded-lg transition-colors flex items-center gap-2"
                  >
                    {overrideLoading ? 'Processing...' : 'Execute Override'}
                  </button>
                </div>
                {overrideError && <p className="text-danger text-[10px] mt-2 font-bold">{overrideError}</p>}
                {overrideSuccess && <p className="text-safe text-[10px] mt-2 font-bold">Successfully overridden!</p>}
              </div>
            )}

            {isOverridden && (
              <div className="border border-brand/30 bg-brand/5 rounded-xl p-4 mt-6 flex items-start gap-3">
                <MessageSquare className="w-5 h-5 text-brand shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-[10px] font-black uppercase tracking-widest text-brand mb-1">
                    System Override Enforced
                  </h3>
                  <p className="text-[10px] text-slate-300">
                    A Human-in-the-Loop override was successfully applied, modifying the claim status to <span className="text-brand font-bold">APPROVED_BY_OVERRIDE</span>.
                  </p>
                </div>
              </div>
            )}
            
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}

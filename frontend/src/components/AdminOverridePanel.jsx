import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Shield, ShieldAlert, CheckCircle, Database, ChevronRight, X } from 'lucide-react';

const SIM_API = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

export default function AdminOverridePanel({ isOpen, onClose, adminId = "ADMIN-101" }) {
  const [queue, setQueue] = useState([]);
  const [auditLog, setAuditLog] = useState([]);
  const [loading, setLoading] = useState(true);
  
  const [selectedClaim, setSelectedClaim] = useState(null);
  const [overrideReason, setOverrideReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const fetchData = async () => {
    setLoading(true);
    try {
      const [queueRes, logRes] = await Promise.all([
        fetch(`${SIM_API}/evaluate-claim/rejected`),
        fetch(`${SIM_API}/override/all`)
      ]);
      if (queueRes.ok) {
        const qData = await queueRes.json();
        setQueue(qData.queue || []);
      }
      if (logRes.ok) {
        const lData = await logRes.json();
        setAuditLog(lData.overrides || []);
      }
    } catch (e) {
      console.error("Ops Fetch Error", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) fetchData();
  }, [isOpen]);

  const handleApplyOverride = async () => {
    if (overrideReason.length < 10) {
      setErrorMsg("Reason must be at least 10 characters.");
      return;
    }
    setSubmitting(true);
    setErrorMsg("");

    // Identify Adjudicator Agent decision from the selected claim trace
    const adjResult = selectedClaim.agents?.find(a => a.agent === 'AdjudicatorAgent') || { decision: 'FAIL' };

    try {
      const response = await fetch(`${SIM_API}/override/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          claim_id: selectedClaim.claim_id || selectedClaim._id,
          decision: adjResult,
          admin_id: adminId,
          override_reason: overrideReason
        })
      });

      const data = await response.json();
      if (!response.ok) {
        setErrorMsg(data.detail || data.reason || "Override failed.");
      } else {
        // Success
        setOverrideReason("");
        setSelectedClaim(null);
        fetchData(); // Refresh the queues
      }
    } catch (e) {
      setErrorMsg("Network error validating override.");
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-[#0B0F14]/90 backdrop-blur-md">
      <div className="w-full h-full max-w-7xl max-h-full bg-[#0a0f18] border border-[#1e293b] rounded-xl shadow-2xl flex flex-col overflow-hidden pointer-events-auto">
        
        {/* Header */}
        <div className="px-6 py-4 border-b border-[#1e293b] flex justify-between items-center bg-[#121826]">
          <div className="flex items-center gap-3">
            <Shield className="w-5 h-5 text-[#3b82f6]" />
            <h2 className="text-sm font-black text-white uppercase tracking-widest">Back-Office Operations</h2>
          </div>
          <button onClick={onClose} className="p-2 bg-[#1e293b] rounded hover:bg-[#334155] transition-colors">
            <X className="w-4 h-4 text-[#e2e8f0]" />
          </button>
        </div>

        <div className="flex-1 overflow-hidden flex divide-x divide-[#1e293b]">
          
          {/* 左 Side: Rejected Queue */}
          <div className="w-1/2 flex flex-col">
            <div className="px-6 py-3 border-b border-[#1e293b] bg-[#121826]/50">
              <h3 className="text-[10px] font-bold text-[#f59e0b] uppercase tracking-widest">Action Required: Disputed Anomalies</h3>
            </div>
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {loading ? (
                <p className="text-[10px] text-[#64748b] font-mono animate-pulse">Loading queue...</p>
              ) : queue.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-[#64748b] opacity-50">
                  <CheckCircle className="w-8 h-8 mb-3" />
                  <p className="text-xs font-bold uppercase tracking-wider">Queue Empty</p>
                </div>
              ) : (
                queue.map((claim, idx) => (
                  <div key={idx} className="bg-[#121826] border border-[#1e293b] rounded-lg p-4 flex flex-col gap-3 transition-colors hover:border-[#3b82f6]/50">
                    <div className="flex justify-between items-start">
                      <div>
                        <p className="text-xs font-mono text-[#94a3b8] mb-1">ID: {claim.worker_id}</p>
                        <p className="text-[11px] font-medium text-[#e2e8f0]">AI Decision: <span className="text-[#ef4444] font-bold">REJECTED</span></p>
                        <p className="text-[10px] text-[#64748b] mt-1">GNN Confidence: {(claim.final_confidence * 100).toFixed(1)}%</p>
                      </div>
                      <span className="text-[9px] font-mono text-[#64748b]">
                        {new Date(claim.timestamp).toLocaleString()}
                      </span>
                    </div>
                    <div className="flex justify-end mt-2">
                       <button 
                         onClick={() => setSelectedClaim(claim)}
                         className="flex items-center gap-2 bg-[#3b82f6]/10 hover:bg-[#3b82f6]/20 text-[#3b82f6] px-4 py-2 rounded text-[10px] font-black tracking-widest uppercase transition-colors border border-[#3b82f6]/30"
                       >
                         Review For Override <ChevronRight className="w-3 h-3" />
                       </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* 右 Side: Global Audit Log */}
          <div className="w-1/2 flex flex-col bg-[#0a0f18]">
            <div className="px-6 py-3 border-b border-[#1e293b] bg-[#121826]/50">
              <h3 className="text-[10px] font-bold text-[#64748b] uppercase tracking-widest">Global Override Audit Log</h3>
            </div>
            <div className="flex-1 overflow-y-auto w-full">
              <table className="w-full text-left border-collapse">
                <thead className="bg-[#121826] border-b border-[#1e293b] sticky top-0">
                  <tr>
                    <th className="py-3 px-6 text-[9px] font-black uppercase tracking-wider text-[#64748b]">Timestamp</th>
                    <th className="py-3 px-6 text-[9px] font-black uppercase tracking-wider text-[#64748b]">Claim ID</th>
                    <th className="py-3 px-6 text-[9px] font-black uppercase tracking-wider text-[#64748b]">Admin</th>
                    <th className="py-3 px-6 text-[9px] font-black uppercase tracking-wider text-[#64748b]">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1e293b]">
                  {loading ? (
                    <tr><td colSpan="4" className="py-4 text-center text-[10px] pb-4 font-mono text-[#64748b]">Loading log...</td></tr>
                  ) : auditLog.length === 0 ? (
                    <tr><td colSpan="4" className="py-8 text-center text-[10px] uppercase font-bold text-[#64748b] opacity-50">No overrides applied</td></tr>
                  ) : (
                    auditLog.map((log, i) => (
                      <tr key={i} className="hover:bg-[#1e293b]/30">
                        <td className="py-3 px-6 text-[10px] font-mono text-[#94a3b8]">{new Date(log.timestamp).toLocaleString([], { hour: '2-digit', minute:'2-digit', month:'short', day:'numeric' })}</td>
                        <td className="py-3 px-6 text-[10px] font-mono text-[#cbd5e1]">{log.claim_id.split('-')[0]}...</td>
                        <td className="py-3 px-6 text-[10px] font-mono text-[#cbd5e1]">{log.admin_id}</td>
                        <td className="py-3 px-6">
                           <span className="text-[9px] font-bold bg-[#10b981]/10 text-[#10b981] px-2 py-0.5 rounded uppercase tracking-wider">
                             F → PASS
                           </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

        </div>
      </div>

      {/* Confirmation Modal Overlay */}
      <AnimatePresence>
        {selectedClaim && (
          <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-[#0a0f18]/80 backdrop-blur">
             <motion.div 
               initial={{ opacity: 0, scale: 0.95, y: 10 }}
               animate={{ opacity: 1, scale: 1, y: 0 }}
               exit={{ opacity: 0, scale: 0.95, y: 10 }}
               className="w-full max-w-lg bg-[#121826] border border-[#f59e0b]/50 rounded-xl shadow-[0_0_40px_rgba(245,158,11,0.15)] overflow-hidden"
             >
               <div className="px-6 py-4 border-b border-[#1e293b] bg-[#f59e0b]/10 flex items-center gap-3">
                 <ShieldAlert className="w-5 h-5 text-[#f59e0b]" />
                 <h3 className="text-sm font-black text-[#f59e0b] uppercase tracking-widest">Execute Security Override</h3>
               </div>
               
               <div className="p-6 space-y-4">
                 <p className="text-[11px] text-[#cbd5e1] leading-relaxed">
                   You are about to manually override a neural consensus decision. The AI Engine flagged this claim with a confidence of <span className="font-mono text-[#ef4444] font-bold">{(selectedClaim.final_confidence * 100).toFixed(1)}%</span>.
                 </p>

                 <div>
                   <label className="text-[10px] font-black uppercase text-[#64748b] tracking-wider mb-2 block">
                     Authorization Justification (Min 10 Chars)
                   </label>
                   <textarea 
                     className="w-full h-24 bg-[#0a0f18] border border-[#1e293b] rounded p-3 text-xs text-[#e2e8f0] font-mono focus:border-[#3b82f6] focus:outline-none resize-none"
                     placeholder="e.g. Verified via external CCTV feed that disruption was legitimate."
                     value={overrideReason}
                     onChange={(e) => setOverrideReason(e.target.value)}
                   />
                   {errorMsg && <p className="text-[10px] font-bold text-[#ef4444] mt-2">{errorMsg}</p>}
                 </div>
               </div>

               <div className="px-6 py-4 bg-[#0a0f18] border-t border-[#1e293b] flex justify-end gap-3">
                 <button 
                   onClick={() => setSelectedClaim(null)} 
                   disabled={submitting}
                   className="px-4 py-2 rounded text-[10px] font-bold text-[#94a3b8] hover:text-white uppercase tracking-widest transition-colors"
                 >
                   Abort
                 </button>
                 <button 
                   onClick={handleApplyOverride}
                   disabled={submitting}
                   className="px-6 py-2 rounded text-[10px] font-black bg-[#f59e0b] hover:bg-[#d97706] text-[#0a0f18] uppercase tracking-widest transition-colors flex items-center gap-2"
                 >
                   {submitting ? "Processing..." : "Confirm Override"}
                 </button>
               </div>
             </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

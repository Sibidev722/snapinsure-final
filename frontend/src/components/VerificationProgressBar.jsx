import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, XCircle, MapPin, DollarSign, Shield, Loader2, ArrowRight } from 'lucide-react';

const agentConfig = {
  TelemetristAgent: {
    title: 'Telemetrist Check',
    icon: MapPin,
  },
  EconomistAgent: {
    title: 'Economist Check',
    icon: DollarSign,
  },
  AdjudicatorAgent: {
    title: 'Final Approval',
    icon: Shield,
  }
};

/**
 * VerificationProgressBar
 * Animates the Multi-Agent audit trail step by step.
 * 
 * @param {Object} auditData JSON matching the backend output
 * @param {Number} processingTimeSecs Duration to show for the final success message (fake or real delay time)
 */
export default function VerificationProgressBar({ auditData, processingTimeSecs = 1.2 }) {
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    if (!auditData || !auditData.agents) return;

    // Reset sequence if new data comes in
    setCurrentStep(0);

    const timeouts = [];
    // Animate each agent with a delay
    auditData.agents.forEach((agent, index) => {
      const timeout = setTimeout(() => {
        setCurrentStep((prev) => Math.max(prev, index + 1));
      }, (index + 1) * 800);
      timeouts.push(timeout);
    });

    // Final completion step
    const finalTimeout = setTimeout(() => {
      setCurrentStep(auditData.agents.length + 1);
    }, (auditData.agents.length + 1) * 800);
    timeouts.push(finalTimeout);

    return () => timeouts.forEach(clearTimeout);
  }, [auditData]);

  if (!auditData || !auditData.agents) {
    return null;
  }

  const { agents, decision } = auditData;
  const isComplete = currentStep > agents.length;
  const isApproved = decision === "APPROVED";

  return (
    <div className="w-full max-w-2xl mx-auto p-6 bg-slate-900/50 backdrop-blur-md rounded-xl border border-slate-700/50 shadow-2xl">
      <h3 className="text-xl font-semibold text-white mb-6 flex items-center gap-2">
        <Shield className="w-5 h-5 text-emerald-400" />
        Multi-Agent Verification Pipeline
      </h3>

      <div className="space-y-6 relative">
        {/* Connecting line pattern behind icons */}
        <div className="absolute top-0 bottom-0 left-6 w-0.5 bg-slate-800 -z-10" />

        <AnimatePresence>
          {agents.map((agentData, index) => {
            const config = agentConfig[agentData.agent] || { title: agentData.agent, icon: Shield };
            const IconGroup = config.icon;
            
            const isFinished = currentStep > index;
            const isProcessing = currentStep === index;
            const isWaiting = currentStep < index;

            const isPass = agentData.status === "PASS";
            const StatusIcon = isPass ? CheckCircle2 : XCircle;

            if (isWaiting) return null;

            return (
              <motion.div
                key={agentData.agent}
                initial={{ opacity: 0, y: 20, x: -10 }}
                animate={{ opacity: 1, y: 0, x: 0 }}
                transition={{ duration: 0.4 }}
                className="flex items-start gap-4 relative"
              >
                {/* Status Indicator / Icon Bubble */}
                <div className={`relative flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center -ml-1 border-4 border-slate-900 ${
                  isFinished 
                    ? (isPass ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-500')
                    : 'bg-indigo-500/20 text-indigo-400'
                }`}>
                  {isProcessing ? (
                     <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                     <IconGroup className="w-5 h-5" />
                  )}
                </div>

                {/* Content Box */}
                <div className={`flex-1 rounded-lg border p-4 ${
                  isFinished 
                    ? (isPass ? 'bg-emerald-500/5 border-emerald-500/20' : 'bg-red-500/5 border-red-500/20')
                    : 'bg-indigo-500/5 border-indigo-500/20'
                }`}>
                  <div className="flex justify-between items-center mb-2">
                    <span className="font-medium text-slate-200">
                      {config.title}
                    </span>
                    {isFinished && (
                      <span className={`text-xs font-bold px-2 py-1 rounded-full flex items-center gap-1 ${
                        isPass ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
                      }`}>
                        <StatusIcon className="w-3 h-3" />
                        {agentData.status}
                      </span>
                    )}
                  </div>
                  
                  {isProcessing ? (
                     <p className="text-sm text-slate-400 animate-pulse">Running calculations & validating...</p>
                  ) : (
                    <motion.div 
                      initial={{ opacity: 0 }} 
                      animate={{ opacity: 1 }} 
                      className="text-sm text-slate-300"
                    >
                      {agentData.reason}
                    </motion.div>
                  )}
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>

        {/* Final Decision Step */}
        <AnimatePresence>
          {isComplete && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.2, type: 'spring' }}
              className={`mt-8 p-4 rounded-xl flex items-center justify-between border ${
                isApproved 
                  ? 'bg-gradient-to-r from-emerald-500/20 to-teal-500/10 border-emerald-500/30' 
                  : 'bg-gradient-to-r from-red-500/20 to-rose-500/10 border-red-500/30'
              }`}
            >
              <div className="flex items-center gap-3">
                {isApproved ? (
                  <CheckCircle2 className="w-8 h-8 text-emerald-400" />
                ) : (
                  <XCircle className="w-8 h-8 text-red-400" />
                )}
                <div>
                  <h4 className={`text-lg font-bold ${isApproved ? 'text-emerald-400' : 'text-red-400'}`}>
                    {isApproved ? 'Payout Approved' : 'Payout Rejected'}
                  </h4>
                  <p className="text-sm text-slate-300">
                    {isApproved 
                      ? `Completed securely in ${processingTimeSecs.toFixed(2)} seconds.`
                      : 'Validation failed the multi-agent thresholds.'}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <span className="text-xs text-slate-400 uppercase tracking-widest block mb-1">Confidence</span>
                <span className="text-xl font-mono text-white">{(auditData.final_confidence * 100).toFixed(1)}%</span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

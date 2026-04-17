import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Leaf, Award, ShieldCheck, ChevronRight } from 'lucide-react';

/**
 * GreenBadge Component
 * Displays a worker's ESG score (Carbon Saved), current badge level, 
 * and progress towards the next milestone.
 * 
 * @param {Number} carbonSaved Amount of CO2 saved in kg
 */
export default function GreenBadge({ carbonSaved = 0 }) {
  // Define milestones and levels
  const MILESTONES = [
    { level: 'Bronze', threshold: 0, color: 'text-amber-600', bg: 'bg-amber-600/20' },
    { level: 'Silver', threshold: 5, color: 'text-slate-300', bg: 'bg-slate-300/20' },
    { level: 'Green Elite', threshold: 15, color: 'text-emerald-400', bg: 'bg-emerald-400/20' }
  ];

  // Determine current and next level
  let currentLevelIndex = 0;
  for (let i = MILESTONES.length - 1; i >= 0; i--) {
    if (carbonSaved >= MILESTONES[i].threshold) {
      currentLevelIndex = i;
      break;
    }
  }

  const currentLevel = MILESTONES[currentLevelIndex];
  const nextLevel = currentLevelIndex < MILESTONES.length - 1 ? MILESTONES[currentLevelIndex + 1] : null;

  // Calculate progress
  let progressPercent = 100;
  let remainingParams = null;
  
  if (nextLevel) {
    const range = nextLevel.threshold - currentLevel.threshold;
    const progressIntoLevel = carbonSaved - currentLevel.threshold;
    progressPercent = Math.min(100, Math.max(0, (progressIntoLevel / range) * 100));
    remainingParams = (nextLevel.threshold - carbonSaved).toFixed(1);
  }

  // "Low Risk Worker" unlock threshold (e.g., reaching Green Elite)
  const isLowRiskUnlocked = carbonSaved >= 15;

  return (
    <div className="w-full max-w-sm p-6 bg-slate-900/40 backdrop-blur-xl border border-emerald-500/30 rounded-2xl shadow-[0_0_20px_rgba(16,185,129,0.1)] relative overflow-hidden group">
      
      {/* Background glow */}
      <div className="absolute top-[-50%] left-[-50%] w-[200%] h-[200%] bg-emerald-500/5 blur-3xl rounded-full -z-10 group-hover:bg-emerald-500/10 transition-colors duration-700" />

      {/* Header & Icon */}
      <div className="flex justify-between items-start mb-6">
        <div>
          <h3 className="text-slate-400 text-sm font-medium uppercase tracking-wider mb-1">ESG Impact</h3>
          <div className="flex items-baseline gap-2">
            <span className="text-4xl font-bold text-white tracking-tight">{carbonSaved.toFixed(1)}</span>
            <span className="text-emerald-400 font-medium">kg CO₂ Saved</span>
          </div>
        </div>
        <div className={`p-3 rounded-xl border ${currentLevel.bg} border-white/5`}>
          <Leaf className={`w-8 h-8 ${currentLevel.color}`} />
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mb-6">
        <div className="flex justify-between text-sm mb-2 font-medium">
          <span className={`flex items-center gap-1 ${currentLevel.color}`}>
            <Award className="w-4 h-4" />
            {currentLevel.level} Badge
          </span>
          {nextLevel ? (
            <span className="text-slate-400 flex items-center gap-1">
              Next: {nextLevel.level} <ChevronRight className="w-3 h-3" />
            </span>
          ) : (
            <span className="text-emerald-400">Max Rank Achieved</span>
          )}
        </div>

        {/* Bar wrapper */}
        <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden relative border border-slate-700">
          <motion.div 
            initial={{ width: 0 }}
            animate={{ width: `${progressPercent}%` }}
            transition={{ duration: 1.5, ease: "easeOut" }}
            className={`absolute top-0 left-0 h-full bg-gradient-to-r from-emerald-600 to-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.5)]`}
          />
        </div>
        
        {nextLevel && (
          <p className="text-xs text-slate-500 mt-2 text-right">
            Save {remainingParams}kg more to rank up
          </p>
        )}
      </div>

      {/* Unlockable Low Risk Badge */}
      <div className="h-14">
        <AnimatePresence mode="wait">
          {isLowRiskUnlocked ? (
            <motion.div
              key="unlocked"
              initial={{ opacity: 0, scale: 0.8, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              transition={{ type: 'spring', bounce: 0.5, duration: 0.6 }}
              className="w-full bg-emerald-500/10 border border-emerald-500/50 rounded-xl p-3 flex items-center justify-center gap-3 relative overflow-hidden"
            >
              {/* Shimmer effect */}
              <motion.div 
                animate={{ x: ['-100%', '200%'] }}
                transition={{ duration: 2, repeat: Infinity, ease: 'linear', repeatDelay: 3 }}
                className="absolute inset-0 w-1/2 bg-gradient-to-r from-transparent via-white/10 to-transparent -skew-x-12"
              />
              <ShieldCheck className="text-emerald-400 w-5 h-5" />
              <span className="text-emerald-300 font-semibold tracking-wide">
                LOW RISK WORKER UNLOCKED
              </span>
            </motion.div>
          ) : (
            <motion.div
              key="locked"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="w-full bg-slate-800/50 border border-slate-700 border-dashed rounded-xl p-3 flex items-center justify-center gap-2 text-slate-500"
            >
              <ShieldCheck className="w-5 h-5 opacity-50" />
              <span className="text-sm font-medium">Reach 15kg for Premium Discount</span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

    </div>
  );
}

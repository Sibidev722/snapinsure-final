import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Shield, CheckCircle, AlertCircle, MapPin, Smartphone, Briefcase, Zap } from 'lucide-react'

const fadeUpVariants = {
  hidden: { opacity: 0, y: 24 },
  visible: (i) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.08, duration: 0.5, ease: [0.22, 1, 0.36, 1] },
  }),
}

const PLATFORMS = ['Zomato', 'Swiggy', 'Uber', 'Blinkit', 'Zepto']
const CITIES = ['Chennai', 'Bangalore', 'Hyderabad', 'Mumbai', 'Delhi']

export default function Login({ onLogin }) {
  const [phase, setPhase] = useState('form') // form | verifying | success | error
  const [errorMsg, setErrorMsg] = useState('')
  const [workerData, setWorkerData] = useState(null)
  
  const [phone, setPhone] = useState('')
  const [platform, setPlatform] = useState('')
  const [city, setCity] = useState('')
  const [workerId, setWorkerId] = useState('')

  const handlePlatformLogin = async (e) => {
    e.preventDefault()
    if (!phone || !platform || !city) {
      setErrorMsg('Please fill in Phone, Platform, and City.')
      setPhase('error')
      return
    }

    setPhase('verifying')

    try {
      const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
      const res = await fetch(`${backendUrl}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phone: phone,
          platform: platform,
          city: city,
          worker_id: workerId || undefined
        }),
      })

      const data = await res.json()

      if (!res.ok || !data.success) {
        throw new Error(data.detail || data.message || 'Login failed')
      }

      // Store JWT token locally
      localStorage.setItem('snapinsure_token', data.token)
      
      setWorkerData(data.user)
      setPhase('success')

      // Brief success display, then hand off
      setTimeout(() => onLogin(data.user, { name: data.user.platform, company: data.user.platform }), 1600)
    } catch (err) {
      setErrorMsg(err.message || 'Network error — is the backend running?')
      setPhase('error')
    }
  }

  const reset = () => {
    setPhase('form')
    setErrorMsg('')
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center relative overflow-hidden px-4 font-sans text-white">
      {/* Ambient background orbs */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <motion.div
          className="absolute -top-32 -left-32 w-[500px] h-[500px] rounded-full mix-blend-screen"
          style={{ background: 'radial-gradient(circle, rgba(99,102,241,0.15) 0%, transparent 70%)' }}
          animate={{ scale: [1, 1.1, 1], opacity: [0.6, 1, 0.6] }}
          transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
        />
        <motion.div
          className="absolute -bottom-32 -right-32 w-[400px] h-[400px] rounded-full mix-blend-screen"
          style={{ background: 'radial-gradient(circle, rgba(16,185,129,0.12) 0%, transparent 70%)' }}
          animate={{ scale: [1, 1.15, 1], opacity: [0.5, 0.9, 0.5] }}
          transition={{ duration: 10, repeat: Infinity, ease: 'easeInOut', delay: 2 }}
        />
        {/* Subtle grid */}
        <div className="absolute inset-0 opacity-[0.02]"
          style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.5) 1px, transparent 1px)', backgroundSize: '60px 60px' }}
        />
      </div>

      <div className="relative z-10 w-full max-w-md">
        {/* Header */}
        <motion.div
          className="text-center mb-8"
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        >
          <div className="flex justify-center mb-5">
            <div className="relative">
              <div className="w-14 h-14 rounded-2xl flex items-center justify-center"
                style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', boxShadow: '0 0 30px rgba(99,102,241,0.4)' }}>
                <Shield className="w-7 h-7 text-white" />
              </div>
              <div className="absolute -top-1 -right-1 w-4 h-4 bg-emerald-400 rounded-full flex items-center justify-center shadow-[0_0_10px_rgba(52,211,153,0.8)]">
                <Zap className="w-2.5 h-2.5 text-white" />
              </div>
            </div>
          </div>

          <h1 className="text-3xl font-black tracking-tight text-white mb-2">
            Snap<span className="text-indigo-400">Insure</span>
          </h1>
          <p className="text-gray-400 text-sm font-medium">
            Verified Gig Worker Access Only
          </p>
        </motion.div>

        {/* Card */}
        <AnimatePresence mode="wait">
          {phase === 'form' && (
            <motion.form
              key="form"
              onSubmit={handlePlatformLogin}
              className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-3xl p-7 shadow-2xl"
              initial={{ opacity: 0, y: 20, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -10, scale: 0.97 }}
              transition={{ duration: 0.4 }}
            >
              <div className="space-y-4">
                
                {/* Phone */}
                <motion.div custom={1} variants={fadeUpVariants} initial="hidden" animate="visible">
                  <label className="block text-xs font-semibold text-gray-400 mb-1.5 uppercase tracking-wider">Phone Number *</label>
                  <div className="relative">
                    <Smartphone className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                    <input type="tel" value={phone} onChange={e => setPhone(e.target.value)}
                      className="w-full bg-white/5 border border-white/10 rounded-xl py-3 pl-10 pr-4 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                      placeholder="e.g. 9876543210" required />
                  </div>
                </motion.div>

                {/* Platform */}
                <motion.div custom={2} variants={fadeUpVariants} initial="hidden" animate="visible">
                  <label className="block text-xs font-semibold text-gray-400 mb-1.5 uppercase tracking-wider">Platform *</label>
                  <div className="relative">
                    <Briefcase className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                    <select value={platform} onChange={e => setPlatform(e.target.value)} required
                      className="w-full bg-[#1c1c24] border border-white/10 rounded-xl py-3 pl-10 pr-4 text-sm text-white focus:outline-none focus:border-indigo-500 appearance-none transition-all">
                      <option value="" disabled>Select platform</option>
                      {PLATFORMS.map(p => <option key={p} value={p}>{p}</option>)}
                    </select>
                  </div>
                </motion.div>

                {/* City */}
                <motion.div custom={3} variants={fadeUpVariants} initial="hidden" animate="visible">
                  <label className="block text-xs font-semibold text-gray-400 mb-1.5 uppercase tracking-wider">City of Operation *</label>
                  <div className="relative">
                    <MapPin className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                    <select value={city} onChange={e => setCity(e.target.value)} required
                      className="w-full bg-[#1c1c24] border border-white/10 rounded-xl py-3 pl-10 pr-4 text-sm text-white focus:outline-none focus:border-indigo-500 appearance-none transition-all">
                      <option value="" disabled>Select city</option>
                      {CITIES.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>
                </motion.div>

                {/* Worker ID */}
                <motion.div custom={4} variants={fadeUpVariants} initial="hidden" animate="visible">
                  <label className="block text-xs font-semibold text-gray-400 mb-1.5 uppercase tracking-wider">Worker ID (Optional)</label>
                  <div className="relative">
                    <Shield className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                    <input type="text" value={workerId} onChange={e => setWorkerId(e.target.value)}
                      className="w-full bg-white/5 border border-white/10 rounded-xl py-3 pl-10 pr-4 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                      placeholder="e.g. ZOM123" />
                  </div>
                </motion.div>
                
              </div>

              <motion.button custom={5} variants={fadeUpVariants} initial="hidden" animate="visible"
                type="submit"
                className="mt-6 w-full py-3.5 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white font-bold text-sm shadow-[0_0_15px_rgba(99,102,241,0.4)] transition-all flex items-center justify-center gap-2"
              >
                Verify & Login
              </motion.button>
              
            </motion.form>
          )}

          {phase === 'verifying' && (
            <motion.div
              key="verifying"
              className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-3xl p-10 shadow-2xl flex flex-col items-center"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
            >
              {/* Spinner */}
              <div className="relative w-20 h-20 mb-6">
                <div className="absolute inset-0 rounded-full border-2 border-white/5" />
                <motion.div
                  className="absolute inset-0 rounded-full border-t-2 border-indigo-500"
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
                />
                <motion.div
                  className="absolute inset-2 rounded-full border-b-2 border-indigo-400/50"
                  animate={{ rotate: -360 }}
                  transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                />
                <div className="absolute inset-0 flex items-center justify-center">
                  <Shield className="w-6 h-6 text-indigo-400" />
                </div>
              </div>

              <h3 className="text-lg font-bold text-white mb-2">Verifying Database</h3>
              <p className="text-sm text-gray-400 mb-6 text-center leading-relaxed">
                Checking your {platform} status<br/> against registered gig workers...
              </p>
            </motion.div>
          )}

          {phase === 'success' && (
            <motion.div
              key="success"
              className="bg-emerald-900/20 backdrop-blur-xl border border-emerald-500/30 rounded-3xl p-10 shadow-[0_0_40px_rgba(16,185,129,0.15)] flex flex-col items-center"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ type: 'spring', stiffness: 200, damping: 20 }}
            >
              <motion.div
                className="w-20 h-20 rounded-full bg-emerald-500/20 border-2 border-emerald-500/40 flex items-center justify-center mb-5"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: 'spring', stiffness: 300, damping: 20, delay: 0.1 }}
              >
                <CheckCircle className="w-10 h-10 text-emerald-400" />
              </motion.div>
              <h3 className="text-xl font-bold text-white mb-2">Identity Verified!</h3>
              <p className="text-sm text-emerald-200/70 text-center mb-4">
                Welcome back, <span className="text-white font-semibold">{workerData?.name}</span>.
              </p>
              
              {/* Verified Badge */}
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 text-xs font-bold uppercase tracking-wide">
                <CheckCircle className="w-3.5 h-3.5" />
                Platform Verified
              </div>
            </motion.div>
          )}

          {phase === 'error' && (
            <motion.div
              key="error"
              className="bg-red-900/10 backdrop-blur-xl border border-red-500/20 rounded-3xl p-8 shadow-2xl"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
            >
              <div className="flex flex-col items-center mb-6">
                <div className="w-16 h-16 rounded-full bg-red-500/10 border border-red-500/30 flex items-center justify-center mb-4">
                  <AlertCircle className="w-8 h-8 text-red-400" />
                </div>
                <h3 className="text-lg font-bold text-white mb-2">Access Denied</h3>
                <p className="text-sm text-red-200/70 text-center">{errorMsg}</p>
              </div>
              <button onClick={reset} className="w-full py-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-white font-semibold text-sm transition-all">
                Try Again
              </button>
            </motion.div>
          )}
        </AnimatePresence>

      </div>
    </div>
  )
}

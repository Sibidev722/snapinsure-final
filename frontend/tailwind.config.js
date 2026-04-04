export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand:   '#6366f1', // indigo
        brandlt: '#818cf8',
        safe:    '#10b981', // emerald
        safelt:  '#34d399',
        warn:    '#f59e0b', // amber
        warnlt:  '#fbbf24',
        danger:  '#ef4444', 
        dangerlt:'#f87171',
        surface: '#0B0F14',
        card:    '#11161d',
        cardlt:  '#1e2535',
        border:  'rgba(255,255,255,0.07)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        'glow-brand':  '0 0 30px rgba(99,102,241,0.25)',
        'glow-safe':   '0 0 30px rgba(16,185,129,0.25)',
        'glow-warn':   '0 0 30px rgba(245,158,11,0.25)',
        'glow-danger': '0 0 40px rgba(239,68,68,0.3)',
        'card':        '0 4px 24px rgba(0,0,0,0.4)',
        'card-hover':  '0 8px 40px rgba(0,0,0,0.6)',
      },
      backgroundImage: {
        'gradient-brand': 'linear-gradient(135deg, #6366f1, #8b5cf6)',
        'gradient-safe':  'linear-gradient(135deg, #10b981, #059669)',
        'gradient-warn':  'linear-gradient(135deg, #f59e0b, #d97706)',
        'gradient-danger':'linear-gradient(135deg, #ef4444, #dc2626)',
        'gradient-card':  'linear-gradient(145deg, #161b27, #1e2535)',
        'gradient-mesh':  'radial-gradient(ellipse at 20% 50%, rgba(99,102,241,0.08) 0%, transparent 60%), radial-gradient(ellipse at 80% 20%, rgba(16,185,129,0.06) 0%, transparent 50%)',
      },
      animation: {
        'fade-up':     'fadeUp 0.5s ease-out both',
        'fade-in':     'fadeIn 0.4s ease-out both',
        'scale-in':    'scaleIn 0.3s ease-out both',
        'slide-right': 'slideRight 2s linear infinite',
        'pulse-slow':  'pulse 3s ease-in-out infinite',
        'spin-slow':   'spin 3s linear infinite',
        'bounce-soft': 'bounceSoft 2s ease-in-out infinite',
        'shimmer':     'shimmer 2s linear infinite',
        'flow':        'flow 6s ease-in-out infinite',
      },
      keyframes: {
        fadeUp:     { from: { opacity: '0', transform: 'translateY(20px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        fadeIn:     { from: { opacity: '0' }, to: { opacity: '1' } },
        scaleIn:    { from: { opacity: '0', transform: 'scale(0.93)' }, to: { opacity: '1', transform: 'scale(1)' } },
        slideRight: { '0%': { transform: 'translateX(-100%)' }, '100%': { transform: 'translateX(400%)' } },
        bounceSoft: { '0%,100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-6px)' } },
        shimmer:    { '0%': { backgroundPosition: '-200% 0' }, '100%': { backgroundPosition: '200% 0' } },
        flow:       { '0%,100%': { transform: 'translate(0,0) scale(1)' }, '33%': { transform: 'translate(20px,-15px) scale(1.04)' }, '66%': { transform: 'translate(-10px,10px) scale(0.97)' } },
      },
    },
  },
  plugins: [],
}

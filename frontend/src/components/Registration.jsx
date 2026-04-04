import { useState } from 'react'

export default function Registration({ onRegister }) {
  const [formData, setFormData] = useState({
    name: 'Alex Mercer',
    city: 'Cyber City',
    type: 'delivery',
    peak_hours: 6,
    avg_income: 180
  });
  const [loading, setLoading] = useState(false);

  // Auto submit for demo feel
  const handleSubmit = (e) => {
    e.preventDefault();
    setLoading(true);
    
    // Simulate API call to POST /users/register
    setTimeout(() => {
      // Fake response mimicking the backend ML pricing engine + policy creation
      const mockResponse = {
        user: { ...formData, id: 'usr_8x9a' },
        policy: {
          premium_paid: 12.50,
          avg_peak_income: formData.avg_income * 1.5,
          avg_normal_income: formData.avg_income * 1.0,
          working_hours: formData.peak_hours + 4
        },
        pricing_explanation: "Standard premium applied with safe routing discount."
      };
      
      onRegister(mockResponse);
      setLoading(false);
    }, 2500);
  };

  return (
    <div className="glass-panel rounded-2xl p-8 max-w-md mx-auto relative overflow-hidden transition-all duration-500 shadow-[0_20px_50px_rgba(0,0,0,0.5)] border-t border-slate-600/50">
      <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-brand to-safe shadow-[0_0_10px_rgba(56,189,248,0.8)]"></div>
      
      <h2 className="text-2xl font-bold mb-8 text-slate-100 text-center tracking-wide">Activate Protection</h2>
      
      {loading ? (
        <div className="flex flex-col items-center justify-center py-12 px-4 space-y-6">
          <div className="relative w-24 h-24">
            <div className="absolute inset-0 rounded-full border-t-4 border-brand animate-spin shadow-[0_0_15px_rgba(56,189,248,0.5)]"></div>
            <div className="absolute inset-2 rounded-full border-r-4 border-safe animate-[spin_1.5s_reverse_infinite] shadow-[0_0_15px_rgba(16,185,129,0.5)]"></div>
            <div className="absolute inset-4 flex items-center justify-center pointer-events-none">
                <span className="text-sm font-black text-slate-200 animate-pulse tracking-widest">AI</span>
            </div>
          </div>
          <p className="text-brand animate-pulse font-bold tracking-widest uppercase text-xs mt-4">Analyzing Risk Matrix...</p>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-5 animate-[slideIn_0.4s_ease-out]">
          <div>
            <label className="block text-[10px] text-brand font-bold uppercase tracking-widest mb-1.5 ml-1">Full Name</label>
            <input type="text" className="input-field" value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} />
          </div>
          <div>
            <label className="block text-[10px] text-brand font-bold uppercase tracking-widest mb-1.5 ml-1">Operating Zone</label>
            <input type="text" className="input-field" value={formData.city} onChange={e => setFormData({...formData, city: e.target.value})} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[10px] text-brand font-bold uppercase tracking-widest mb-1.5 ml-1">Peak Hours</label>
              <input type="number" className="input-field" value={formData.peak_hours} onChange={e => setFormData({...formData, peak_hours: Number(e.target.value)})} />
            </div>
            <div>
              <label className="block text-[10px] text-brand font-bold uppercase tracking-widest mb-1.5 ml-1">Avg Income (₹)</label>
              <input type="number" className="input-field" value={formData.avg_income} onChange={e => setFormData({...formData, avg_income: Number(e.target.value)})} />
            </div>
          </div>
          <button type="submit" className="primary-btn mt-8 text-sm tracking-widest shadow-lg">
            INITIALIZE FLIGHT DECK
          </button>
        </form>
      )}
    </div>
  );
}

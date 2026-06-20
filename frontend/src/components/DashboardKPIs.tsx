import { useState, useEffect } from 'react';

const API_URL = 'http://localhost:8000';

interface DashboardStats {
  total_resources: number;
  total_savings: number;
  current_spend: number;
}

export function DashboardKPIs() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/dashboard-stats`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      } else {
        const errText = await res.text();
        setError(`Error ${res.status}: ${errText}`);
      }
    } catch (err: any) {
      console.error("Failed to fetch dashboard stats", err);
      setError(err.message || String(err));
    } finally {
      setLoading(false);
    }
  };

  if (error) {
    return (
      <div style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', padding: '15px', borderRadius: '8px', marginBottom: '30px' }}>
        <strong>Failed to load KPIs:</strong> {error}
      </div>
    );
  }

  if (loading || !stats) {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '20px', marginBottom: '30px' }}>
        {[1, 2, 3].map(i => (
          <div key={i} className="card" style={{ height: '120px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div className="loading-spinner"></div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '20px', marginBottom: '30px' }}>
      {/* Current Spend */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
        <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '5px' }}>Current Monthly Spend</div>
        <div style={{ fontSize: '2.5rem', fontWeight: 700, color: '#ef4444' }}>
          ${stats.current_spend.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </div>
      </div>

      {/* Total Predicted Savings */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
        <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '5px' }}>Total Savings Found</div>
        <div style={{ fontSize: '2.5rem', fontWeight: 700, color: '#10b981' }}>
          ${stats.total_savings.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
        </div>
      </div>

      {/* Resources Scanned */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
        <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '5px' }}>Resources Analyzed</div>
        <div style={{ fontSize: '2.5rem', fontWeight: 700, color: 'var(--text-primary)' }}>
          {stats.total_resources.toLocaleString()}
        </div>
      </div>
    </div>
  );
}

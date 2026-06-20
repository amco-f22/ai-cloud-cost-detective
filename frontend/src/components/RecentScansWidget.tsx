import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

const API_URL = 'http://localhost:8000';

interface Analysis {
  id: number;
  region: string;
  resources_scanned: number;
  issues_found: number;
  estimated_savings: string;
  status: string;
  created_at: string;
}

export function RecentScansWidget() {
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchRecent();
  }, []);

  const fetchRecent = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/history/recent`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setAnalyses(data.analyses || []);
      }
    } catch (err) {
      console.error("Failed to fetch recent scans", err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '300px' }}>
        <div className="loading-spinner"></div>
      </div>
    );
  }

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
      <div className="card-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <span>🕒 Recent Scans</span>
        <Link to="/history" style={{ fontSize: '0.85rem', color: 'var(--accent-primary)', textDecoration: 'none' }}>View All →</Link>
      </div>

      {analyses.length === 0 ? (
        <div style={{ textAlign: 'center', color: 'var(--text-dim)', padding: '40px 0' }}>
          No scans run yet.
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
                <th style={{ padding: '10px 5px', fontWeight: 500 }}>Region</th>
                <th style={{ padding: '10px 5px', fontWeight: 500 }}>Date</th>
                <th style={{ padding: '10px 5px', fontWeight: 500 }}>Issues</th>
                <th style={{ padding: '10px 5px', fontWeight: 500 }}>Savings</th>
                <th style={{ padding: '10px 5px', fontWeight: 500 }}>Report</th>
              </tr>
            </thead>
            <tbody>
              {analyses.map(a => (
                <tr key={a.id} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '12px 5px', color: 'var(--text-primary)' }}>{a.region}</td>
                  <td style={{ padding: '12px 5px', color: 'var(--text-secondary)' }}>
                    {new Date(a.created_at).toLocaleDateString()}
                  </td>
                  <td style={{ padding: '12px 5px' }}>
                    {a.issues_found > 0 ? (
                      <span style={{ color: '#ef4444', fontWeight: 600 }}>{a.issues_found}</span>
                    ) : (
                      <span style={{ color: '#10b981' }}>0</span>
                    )}
                  </td>
                  <td style={{ padding: '12px 5px', color: '#10b981', fontWeight: 500 }}>
                    {a.estimated_savings || '-'}
                  </td>
                  <td style={{ padding: '12px 5px' }}>
                    <Link to={`/report/${a.id}`} className="btn-secondary" style={{ padding: '4px 10px', fontSize: '0.8rem', textDecoration: 'none' }}>
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

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

interface HistoryProps {
  token: string;
}

export default function History({ token }: HistoryProps) {
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    try {
      const res = await fetch(`${API_URL}/api/history`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setAnalyses(data.analyses || []);
      }
    } catch {
      // Silent fail
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  if (loading) {
    return (
      <div className="loading-container">
        <div className="loading-spinner"></div>
      </div>
    );
  }

  return (
    <div className="history-container">
      <h1 className="history-title">Analysis History</h1>

      {analyses.length === 0 ? (
        <div className="history-empty">
          <div className="history-empty-icon">📋</div>
          <div className="history-empty-text">
            No analyses yet. Go to the Dashboard to run your first scan.
          </div>
        </div>
      ) : (
        <div className="history-list">
          {analyses.map((a) => (
            <Link
              to={`/report/${a.id}`}
              key={a.id}
              className="history-item"
            >
              <div className="history-region">{a.region}</div>
              <div className="history-stats">
                <span className="history-stat">
                  <strong>{a.resources_scanned}</strong> resources
                </span>
                <span className="history-stat">
                  <strong>{a.issues_found}</strong> issues
                </span>
                <span className="history-stat">
                  💰 {a.estimated_savings || '—'}
                </span>
              </div>
              <span className={`history-status ${a.status}`}>
                {a.status}
              </span>
              <div className="history-date">{formatDate(a.created_at)}</div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

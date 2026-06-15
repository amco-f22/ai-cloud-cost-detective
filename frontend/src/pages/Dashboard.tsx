import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import ProgressTracker from '../components/ProgressTracker';

const API_URL = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000';

interface Region {
  name: string;
  endpoint: string;
}

interface ProgressStep {
  step: string;
  status: 'in_progress' | 'completed' | 'error';
  detail?: string;
}

interface DashboardProps {
  token: string;
}

export default function Dashboard({ token }: DashboardProps) {
  const [regions, setRegions] = useState<Region[]>([]);
  const [selectedRegion, setSelectedRegion] = useState('');
  const [awsStatus, setAwsStatus] = useState<{ connected: boolean; account?: string } | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [progressSteps, setProgressSteps] = useState<ProgressStep[]>([]);
  const [error, setError] = useState('');
  const wsRef = useRef<WebSocket | null>(null);
  const navigate = useNavigate();

  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  // Fetch AWS status and regions on mount
  useEffect(() => {
    fetchAwsStatus();
    fetchRegions();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  // Timer effect
  useEffect(() => {
    let interval: number | undefined;
    if (analyzing) {
      setElapsedSeconds(0);
      interval = window.setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);
    } else {
      if (interval !== undefined) clearInterval(interval);
    }
    return () => {
      if (interval !== undefined) clearInterval(interval);
    };
  }, [analyzing]);

  const fetchAwsStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/api/verify-aws`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setAwsStatus({ connected: true, account: data.account });
      } else {
        setAwsStatus({ connected: false });
      }
    } catch {
      setAwsStatus({ connected: false });
    }
  };

  const fetchRegions = async () => {
    try {
      const res = await fetch(`${API_URL}/api/regions`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setRegions(data.regions || []);
        // Default to us-east-1 if available
        const defaultRegion = data.regions?.find((r: Region) => r.name === 'us-east-1');
        if (defaultRegion) setSelectedRegion(defaultRegion.name);
        else if (data.regions?.length > 0) setSelectedRegion(data.regions[0].name);
      }
    } catch {
      setError('Failed to fetch AWS regions');
    }
  };

  const runAnalysis = async () => {
    if (!selectedRegion) return;
    setError('');
    setAnalyzing(true);
    setProgressSteps([]);

    try {
      const res = await fetch(`${API_URL}/api/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ region: selectedRegion }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || 'Analysis failed');
      }

      const analysisId = data.analysis_id;

      // Connect WebSocket for progress
      connectWebSocket(analysisId);
    } catch (err: any) {
      setError(err.message || 'Failed to start analysis');
      setAnalyzing(false);
    }
  };

  const connectWebSocket = (analysisId: number) => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    const ws = new WebSocket(`${WS_URL}/ws/progress/${analysisId}`);
    wsRef.current = ws;

    ws.onopen = () => {
      // Send a ping to keep connection alive
      const pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('ping');
        } else {
          clearInterval(pingInterval);
        }
      }, 5000);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        setProgressSteps((prev) => {
          // Update existing step or add new one
          const existingIndex = prev.findIndex((s) => s.step === data.step);
          if (existingIndex >= 0) {
            const updated = [...prev];
            updated[existingIndex] = {
              step: data.step,
              status: data.status,
              detail: data.detail,
            };
            return updated;
          }
          return [
            ...prev,
            {
              step: data.step,
              status: data.status,
              detail: data.detail,
            },
          ];
        });

        // Analysis complete — navigate to report
        if (data.step === 'Analysis complete' && data.status === 'completed') {
          setTimeout(() => {
            setAnalyzing(false);
            navigate(`/report/${data.analysis_id}`);
          }, 1500);
        }

        // Error
        if (data.status === 'error') {
          setError(data.detail || 'Analysis failed');
          setAnalyzing(false);
        }
      } catch {
        // Ignore non-JSON messages
      }
    };

    ws.onerror = () => {
      setError('WebSocket connection failed. Ensure the backend is running on port 8000.');
      setAnalyzing(false);
    };

    ws.onclose = () => {
      // Normal close, nothing to do
    };
  };

  return (
    <div>
      <div className="dashboard-header">
        <h1 className="dashboard-title">AWS Cost Detective Dashboard</h1>
        <p className="dashboard-desc">
          Select an AWS region to scan for cost optimization opportunities
        </p>
      </div>

      <div className="dashboard-grid">
        {/* AWS Status Card */}
        <div className="card">
          <div className="card-title">
            <span className="card-title-icon">☁️</span> AWS Connection
          </div>
          {awsStatus === null ? (
            <div className="aws-status">
              <div className="loading-spinner" style={{ width: 16, height: 16 }}></div>
              <span className="aws-status-text">Checking connection...</span>
            </div>
          ) : awsStatus.connected ? (
            <div className="aws-status">
              <div className="aws-status-dot"></div>
              <div>
                <div className="aws-status-text">Connected to AWS</div>
                <div className="aws-status-account">Account: {awsStatus.account}</div>
              </div>
            </div>
          ) : (
            <div className="aws-status">
              <div className="aws-status-dot disconnected"></div>
              <span className="aws-status-text">
                Not connected — run <code style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-secondary)' }}>aws configure</code> first
              </span>
            </div>
          )}
        </div>

        {/* Region Selection Card */}
        <div className="card">
          <div className="card-title">
            <span className="card-title-icon">🌍</span> Select Region
          </div>
          <select
            id="region-select"
            className="region-select"
            value={selectedRegion}
            onChange={(e) => setSelectedRegion(e.target.value)}
            disabled={analyzing}
          >
            <option value="">Choose a region...</option>
            {regions.map((r) => (
              <option key={r.name} value={r.name}>
                {r.name}
              </option>
            ))}
          </select>

          <button
            id="btn-run-analysis"
            className="btn-analyze"
            onClick={runAnalysis}
            disabled={!selectedRegion || analyzing || !awsStatus?.connected}
          >
            {analyzing ? (
              <>
                <div className="spinner"></div>
                Analyzing...
              </>
            ) : (
              <>🔍 Run Analysis</>
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="auth-error" style={{ marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      {/* Progress Tracker */}
      {analyzing && (
        <div style={{ textAlign: 'center', marginBottom: '1rem', color: 'var(--text-dim)', fontVariantNumeric: 'tabular-nums' }}>
          ⏱️ Analysis running: {Math.floor(elapsedSeconds / 60)}:{(elapsedSeconds % 60).toString().padStart(2, '0')}
        </div>
      )}
      <ProgressTracker steps={progressSteps} />
    </div>
  );
}

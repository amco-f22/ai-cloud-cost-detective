import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

const API_URL = 'http://localhost:8000';

interface Issue {
  title: string;
  resource_type: string;
  resource_id: string;
  resource_name: string;
  severity: 'high' | 'medium' | 'low';
  category: string;
  current_state: string;
  recommendation: string;
  fix_command: string;
  estimated_savings: string;
  additional_notes?: string;
}

interface AnalysisResult {
  summary: string;
  total_resources_scanned: number;
  total_issues_found: number;
  estimated_monthly_savings: string;
  issues: Issue[];
  additional_recommendations: string[];
}

interface ReportProps {
  token: string;
}

export default function Report({ token }: ReportProps) {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [analysis, setAnalysis] = useState<any>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  useEffect(() => {
    fetchAnalysis();
  }, [id]);

  const fetchAnalysis = async () => {
    try {
      const res = await fetch(`${API_URL}/api/analysis/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) throw new Error('Failed to fetch analysis');

      const data = await res.json();
      setAnalysis(data);
      setResult(data.analysis_result);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const copyCommand = (command: string, index: number) => {
    navigator.clipboard.writeText(command);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  if (loading) {
    return (
      <div className="loading-container">
        <div className="loading-spinner"></div>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="report-container">
        <button className="btn-back" onClick={() => navigate('/')}>
          ← Back to Dashboard
        </button>
        <div className="auth-error">{error || 'Analysis not found'}</div>
      </div>
    );
  }

  return (
    <div className="report-container">
      <button className="btn-back" onClick={() => navigate(-1)}>
        ← Back
      </button>

      <div className="report-header">
        <h1 className="report-title">Analysis Report</h1>
        <div className="report-meta">
          <span>Region: <strong>{analysis?.region}</strong></span>
          <span>•</span>
          <span>{analysis?.created_at ? new Date(analysis.created_at).toLocaleString() : ''}</span>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="report-summary">
        <div className="summary-card">
          <div className="summary-value resources">
            {result.total_resources_scanned}
          </div>
          <div className="summary-label">Resources Scanned</div>
        </div>
        <div className="summary-card">
          <div className="summary-value issues">
            {result.total_issues_found}
          </div>
          <div className="summary-label">Issues Found</div>
        </div>
        <div className="summary-card">
          <div className="summary-value savings">
            {result.estimated_monthly_savings.replace(/\/month/gi, '')}
          </div>
          <div className="summary-label">Estimated Monthly Savings</div>
        </div>
        {result.time_taken_seconds !== undefined && (
          <div className="summary-card">
            <div className="summary-value" style={{ color: 'var(--text-primary)' }}>
              {Math.floor(result.time_taken_seconds / 60)}m {result.time_taken_seconds % 60}s
            </div>
            <div className="summary-label">Analysis Time</div>
          </div>
        )}
      </div>

      {/* Summary Text */}
      {result.summary && (
        <div style={{ marginBottom: '2rem' }}>
          <h2 className="section-title">✨ AI Summary</h2>
          <div className="report-overview" style={{ marginBottom: 0 }}>
            {result.summary}
          </div>
        </div>
      )}

      {/* Issues */}
      <div className="report-issues">
        <h2 className="section-title">🎯 Issues & Recommendations</h2>
        {(result.issues || []).map((issue, index) => (
          <div className="issue-card" key={index}>
            <div className="issue-header">
              <div>
                <div className="issue-title">{issue.title}</div>
                <div className="issue-resource">
                  {issue.resource_type} • {issue.resource_name || issue.resource_id}
                </div>
              </div>
              <span className={`severity-badge ${issue.severity}`}>
                {issue.severity}
              </span>
            </div>

            <div className="issue-body">
              {issue.current_state && <p><strong>Current:</strong> {issue.current_state}</p>}
              <p>{issue.recommendation}</p>
            </div>

            {issue.estimated_savings && (
              <div className="issue-savings">
                💰 Estimated savings: {issue.estimated_savings}
              </div>
            )}

            {issue.fix_command && (
              <div className="issue-fix">
                <div className="issue-fix-label">Fix Command</div>
                <div className="issue-fix-code">
                  {issue.fix_command}
                  <button
                    className={`copy-btn ${copiedIndex === index ? 'copied' : ''}`}
                    onClick={() => copyCommand(issue.fix_command, index)}
                  >
                    {copiedIndex === index ? '✓ Copied' : 'Copy'}
                  </button>
                </div>
              </div>
            )}

            {issue.additional_notes && (
              <div className="issue-body" style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: 'var(--text-dim)' }}>
                {issue.additional_notes}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Additional Recommendations */}
      {result.additional_recommendations && result.additional_recommendations.length > 0 && (
        <div className="recommendations">
          <div className="recommendations-title">
            <span>💡</span> Additional Recommendations
          </div>
          {result.additional_recommendations.map((rec, index) => (
            <div className="recommendation-item" key={index}>
              {rec}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

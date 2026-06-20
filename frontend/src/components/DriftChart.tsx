import { useState, useEffect } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';

interface DriftData {
  date: string;
  actual_spend: number;
  predicted_spend: number;
}

export function DriftChart() {
  const [data, setData] = useState<DriftData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDriftData();
  }, []);

  const fetchDriftData = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch('http://localhost:8000/api/drift', {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });
      if (!res.ok) throw new Error('Failed to fetch drift data');
      
      const json = await res.json();
      setData(json);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="loading">Loading drift history...</div>;
  if (error) return null; // Hide quietly if no data/error
  if (data.length === 0) return null;

  const latestData = data[data.length - 1];
  const gap = latestData ? latestData.actual_spend - latestData.predicted_spend : 0;
  const isOverBudget = gap > 0;

  return (
    <div style={{ backgroundColor: 'var(--bg-secondary)', padding: '20px', borderRadius: '12px', marginBottom: '20px', border: '1px solid var(--border)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '15px' }}>
        <div>
          <h3 style={{ marginTop: 0, color: 'var(--text-primary)', marginBottom: '5px' }}>
            📈 Predicted vs Actual Spend Drift
          </h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', margin: 0 }}>
            Watch the gap close! This tracks our AI's predicted savings against your actual AWS billed spend.
          </p>
        </div>
        {latestData && (
          <div style={{
            backgroundColor: isOverBudget ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.1)',
            color: isOverBudget ? '#ef4444' : '#10b981',
            padding: '8px 12px',
            borderRadius: '20px',
            fontWeight: 600,
            fontSize: '0.9rem',
            border: `1px solid ${isOverBudget ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)'}`
          }}>
            {isOverBudget ? `🔴 +$${gap.toFixed(2)} Over Target` : `🟢 On Track (Gap: $${Math.abs(gap).toFixed(2)})`}
          </div>
        )}
      </div>

      <div style={{ width: '100%', height: 300 }}>
        <ResponsiveContainer>
          <AreaChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
            <defs>
              <linearGradient id="colorActual" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="colorPredicted" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis 
              dataKey="date" 
              stroke="var(--text-secondary)" 
              tick={{ fill: 'var(--text-secondary)' }}
              tickFormatter={(val) => {
                const d = new Date(val);
                return `${d.getMonth()+1}/${d.getDate()}`;
              }}
            />
            <YAxis 
              stroke="var(--text-secondary)" 
              tick={{ fill: 'var(--text-secondary)' }}
              tickFormatter={(val) => `$${val}`}
            />
            <Tooltip 
              contentStyle={{ backgroundColor: 'var(--bg-primary)', border: '1px solid var(--border)', borderRadius: '8px' }}
              itemStyle={{ color: 'var(--text-primary)' }}
            />
            <Legend wrapperStyle={{ paddingTop: '20px' }} />
            <Area 
              type="monotone" 
              dataKey="actual_spend" 
              name="Actual Billed Spend" 
              stroke="#ef4444" 
              fillOpacity={1}
              fill="url(#colorActual)"
              strokeWidth={3} 
              activeDot={{ r: 6 }} 
            />
            <Area 
              type="monotone" 
              dataKey="predicted_spend" 
              name="AI Predicted Spend" 
              stroke="#3b82f6" 
              fillOpacity={1}
              fill="url(#colorPredicted)"
              strokeWidth={3} 
              strokeDasharray="5 5" 
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

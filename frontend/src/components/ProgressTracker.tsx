interface ProgressStep {
  step: string;
  status: 'in_progress' | 'completed' | 'error';
  detail?: string;
}

interface ProgressTrackerProps {
  steps: ProgressStep[];
}

export default function ProgressTracker({ steps }: ProgressTrackerProps) {
  if (steps.length === 0) return null;

  return (
    <div className="progress-container">
      <div className="progress-card">
        <div className="progress-title">
          <span>⚡</span> Analysis Progress
        </div>
        <div className="progress-steps">
          {steps.map((s, index) => (
            <div
              key={index}
              className={`progress-step ${s.status}`}
              style={{ animationDelay: `${index * 0.1}s` }}
            >
              <div className="progress-step-icon">
                {s.status === 'completed' && '✓'}
                {s.status === 'in_progress' && '●'}
                {s.status === 'error' && '✕'}
              </div>
              <span className="progress-step-text">{s.step}</span>
              {s.detail && (
                <span className="progress-step-detail">{s.detail}</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

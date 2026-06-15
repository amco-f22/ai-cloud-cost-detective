import { Link, useLocation } from 'react-router-dom';

interface NavbarProps {
  email: string;
  onLogout: () => void;
}

export default function Navbar({ email, onLogout }: NavbarProps) {
  const location = useLocation();

  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <div className="navbar-logo">🔍</div>
        <div>
          <div className="navbar-title">Cloud Cost Detective</div>
          <div className="navbar-subtitle">AI-Powered AWS Optimization</div>
        </div>
      </div>

      <div className="navbar-links">
        <Link
          to="/"
          className={`navbar-link ${location.pathname === '/' ? 'active' : ''}`}
        >
          Dashboard
        </Link>
        <Link
          to="/history"
          className={`navbar-link ${location.pathname === '/history' ? 'active' : ''}`}
        >
          History
        </Link>
      </div>

      <div className="navbar-user">
        <span className="navbar-email">{email}</span>
        <button className="navbar-logout" onClick={onLogout}>
          Log Out
        </button>
      </div>
    </nav>
  );
}

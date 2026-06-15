import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import Login from './pages/Login';
import Signup from './pages/Signup';
import Dashboard from './pages/Dashboard';
import Report from './pages/Report';
import History from './pages/History';
import Navbar from './components/Navbar';
import './App.css';

function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [user, setUser] = useState<{ id: number; email: string } | null>(null);

  useEffect(() => {
    if (token) {
      const stored = localStorage.getItem('user');
      if (stored) {
        try {
          setUser(JSON.parse(stored));
        } catch {
          setUser(null);
        }
      }
    }
  }, [token]);

  const handleAuth = (newToken: string, userData: { id: number; email: string }) => {
    localStorage.setItem('token', newToken);
    localStorage.setItem('user', JSON.stringify(userData));
    setToken(newToken);
    setUser(userData);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setToken(null);
    setUser(null);
  };

  if (!token) {
    return (
      <Router>
        <div className="app">
          <Routes>
            <Route path="/signup" element={<Signup onAuth={handleAuth} />} />
            <Route path="*" element={<Login onAuth={handleAuth} />} />
          </Routes>
        </div>
      </Router>
    );
  }

  return (
    <Router>
      <div className="app">
        <Navbar email={user?.email || ''} onLogout={handleLogout} />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard token={token} />} />
            <Route path="/report/:id" element={<Report token={token} />} />
            <Route path="/history" element={<History token={token} />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;

import { Link, Outlet, useNavigate } from 'react-router-dom';

import { useAuth } from '../context/AuthContext.jsx';

export default function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate('/login', { replace: true });
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <Link to="/companies" className="app-title">
          SME Financial Health
        </Link>
        <div className="app-header-right">
          <span className="app-user">{user?.full_name}</span>
          <button type="button" className="button button-quiet" onClick={handleLogout}>
            Log out
          </button>
        </div>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
      <footer className="app-footer">
        FYP1 — monitoring and assessment. Distress simulation and explanation are planned
        for FYP2.
      </footer>
    </div>
  );
}

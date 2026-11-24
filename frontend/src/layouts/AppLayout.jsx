import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';

import Icon from '../components/Icon.jsx';
import ThemeToggle from '../components/ThemeToggle.jsx';
import { useAuth } from '../context/AuthContext.jsx';
import { BreadcrumbProvider, useBreadcrumbTrail } from '../context/BreadcrumbContext.jsx';
import { ROLE_LABELS, useOrganisation } from '../context/OrganisationContext.jsx';

function initialsOf(name) {
  return (name || '?')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('');
}

function Breadcrumbs() {
  const crumbs = useBreadcrumbTrail();
  if (crumbs.length === 0) return null;
  return (
    <nav aria-label="Breadcrumb">
      <ol className="crumbs">
        {crumbs.map((crumb, index) => {
          const isCurrent = index === crumbs.length - 1;
          return (
            <li key={`${index}-${crumb.label}`}>
              {isCurrent || !crumb.to ? (
                <span className="crumb" aria-current={isCurrent ? 'page' : undefined}>
                  {crumb.label}
                </span>
              ) : (
                <Link className="crumb" to={crumb.to}>
                  {crumb.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

const NAVIGATION = [
  { to: '/overview', label: 'Financial Overview', icon: 'overview', adminOnly: true },
  { to: '/data', label: 'Financial Data', icon: 'upload', match: /\/data$/ },
  { to: '/analysis', label: 'Financial Analysis', icon: 'analysis', match: /\/dashboard$/, adminOnly: true },
  { to: '/history', label: 'Financial History', icon: 'history' },
  { to: '/settings', label: 'Company Settings', icon: 'building', adminOnly: true },
];

/** The sections of the app, for the one organisation the account monitors. */
function MainNavigation() {
  const { pathname } = useLocation();
  const { isAdmin } = useOrganisation();
  // A Finance Clerk sees only the pages for maintaining the financial data.
  const items = NAVIGATION.filter((item) => isAdmin || !item.adminOnly);
  return (
    <nav className="app-nav" aria-label="Main">
      <ul>
        {items.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              className={({ isActive }) =>
                `app-nav-link${isActive || item.match?.test(pathname) ? ' is-active' : ''}`
              }
              aria-current={
                pathname === item.to || item.match?.test(pathname) ? 'page' : undefined
              }
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export default function AppLayout() {
  const { user, logout } = useAuth();
  const { organisation, role, home } = useOrganisation();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate('/login', { replace: true });
  }

  return (
    <BreadcrumbProvider>
      <div className="app-shell">
        <header className="app-header">
          <Link to={home} className="app-title">
            SME Financial Health
          </Link>
          <Breadcrumbs />
          <div className="app-header-right">
            {organisation && (
              <span className="org-chip" title="The organisation this account monitors">
                {organisation.name}
              </span>
            )}
            <ThemeToggle />
            <span className="app-user">
              <span className="avatar" aria-hidden="true">
                {initialsOf(user?.full_name)}
              </span>
              <span className="app-user-name">
                {user?.full_name}
                {role && <span className="app-user-role">{ROLE_LABELS[role]}</span>}
              </span>
            </span>
            <button type="button" className="button button-small button-quiet" onClick={handleLogout}>
              <Icon name="logout" />
              Log out
            </button>
          </div>
        </header>
        {organisation && <MainNavigation />}
        <main className="app-main">
          <Outlet />
        </main>
        <footer className="app-footer">
          FYP1 — monitoring and assessment. Distress simulation and explanation are planned
          for FYP2.
        </footer>
      </div>
    </BreadcrumbProvider>
  );
}

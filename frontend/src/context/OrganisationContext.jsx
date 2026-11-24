import { createContext, useContext } from 'react';
import { Link, Navigate, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

import { api } from '../services/apiClient.js';

const OrganisationContext = createContext(null);

/**
 * The account's one organisation (SME).
 *
 * Pages take the company from here instead of from the URL, so there is no
 * company identifier in any address to change, and the server still checks
 * ownership on every request.
 */
export function OrganisationProvider({ children }) {
  const query = useQuery({ queryKey: ['organisation'], queryFn: api.getOrganisation });
  return <OrganisationContext.Provider value={query}>{children}</OrganisationContext.Provider>;
}

/** The organisation query: { data: { status, organisation, candidates }, ... }. */
export function useOrganisationQuery() {
  return useContext(OrganisationContext);
}

export const ROLE_LABELS = { admin: 'CEO / Admin', clerk: 'Finance Clerk' };

/** The ready organisation and the user's role in it. */
export function useOrganisation() {
  const query = useContext(OrganisationContext);
  const organisation = query?.data?.organisation;
  const role = query?.data?.role ?? null;
  return {
    organisation,
    companyId: organisation ? String(organisation.id) : undefined,
    role,
    isAdmin: role === 'admin',
    // Where each role starts, and the first breadcrumb on every page.
    home: role === 'admin' ? '/overview' : '/data',
    homeCrumb:
      role === 'admin'
        ? { label: 'Financial Overview', to: '/overview' }
        : { label: 'Financial History', to: '/history' },
  };
}

/**
 * A page only the CEO / Admin may see. The API refuses these requests for a
 * Finance Clerk as well; this keeps the interface honest about it.
 */
export function AdminOnly({ children }) {
  const { isAdmin } = useOrganisation();
  if (isAdmin) return children;
  return (
    <div className="page">
      <section className="card access-denied" role="alert">
        <h1>Not available for your role</h1>
        <p className="muted">
          The financial health dashboard, scores, analysis and company settings are
          confidential and limited to the CEO / Admin. As a Finance Clerk you can import trial
          balances, enter and correct financial records, and manage reporting periods.
        </p>
        <Link className="button" to="/data">
          Go to Financial Data
        </Link>
      </section>
    </div>
  );
}

/**
 * Sends an account without an organisation to the one-time setup, and an
 * account with one away from it.
 */
export function OrganisationGate({ children }) {
  const query = useOrganisationQuery();
  const location = useLocation();
  const onSetup = location.pathname === '/setup';

  if (query.isLoading) return <div className="centred-message">Loading…</div>;
  if (query.isError) {
    return <div className="page"><p className="alert alert-error">{query.error.message}</p></div>;
  }
  const ready = query.data.status === 'ready';
  if (!ready && !onSetup) return <Navigate to="/setup" replace />;
  if (ready && onSetup) return <Navigate to="/" replace />;
  return children;
}

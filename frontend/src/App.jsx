import { Navigate, Route, Routes, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

import AppLayout from './layouts/AppLayout.jsx';
import ProtectedRoute from './components/ProtectedRoute.jsx';
import {
  AdminOnly,
  OrganisationGate,
  OrganisationProvider,
  useOrganisation,
} from './context/OrganisationContext.jsx';
import AuthPage from './pages/AuthPage.jsx';
import CompanyDetailPage from './pages/CompanyDetailPage.jsx';
import CompanySettingsPage from './pages/CompanySettingsPage.jsx';
import DashboardPage from './pages/DashboardPage.jsx';
import FinancialDataPage from './pages/FinancialDataPage.jsx';
import JoinPage from './pages/JoinPage.jsx';
import OverviewPage from './pages/OverviewPage.jsx';
import SetupPage from './pages/SetupPage.jsx';
import { api } from './services/apiClient.js';

/**
 * "Financial Data" and "Financial Analysis" in the navigation open the
 * latest period by date. With nothing to open, they lead to the history
 * page, where a period can be created.
 */
function LatestAssessedRedirect() {
  const overview = useQuery({ queryKey: ['overview'], queryFn: api.getOverview });
  if (overview.isLoading) return <div className="centred-message">Loading…</div>;
  const id = overview.data?.latest_assessed_period_id;
  return <Navigate to={id ? `/periods/${id}/dashboard` : '/history'} replace />;
}

/** The latest period by date, from the periods list (open to both roles). */
function LatestPeriodDataRedirect() {
  const { companyId } = useOrganisation();
  const periods = useQuery({
    queryKey: ['periods', companyId],
    queryFn: () => api.listPeriods(companyId),
  });
  if (periods.isLoading) return <div className="centred-message">Loading…</div>;
  const latest = [...(periods.data || [])].sort((a, b) =>
    a.period_end === b.period_end
      ? b.period_start.localeCompare(a.period_start)
      : b.period_end.localeCompare(a.period_end),
  )[0];
  return <Navigate to={latest ? `/periods/${latest.id}/data` : '/history'} replace />;
}

/** Each role starts where its work is. */
function RoleHome() {
  const { home } = useOrganisation();
  return <Navigate to={home} replace />;
}

/** Old /companies/... addresses (bookmarks) lead to the same pages. */
function LegacyCompanyRedirect() {
  const { periodId, page } = useParams();
  if (periodId && (page === 'data' || page === 'dashboard')) {
    return <Navigate to={`/periods/${periodId}/${page}`} replace />;
  }
  return <Navigate to="/" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route element={<AuthPage />}>
        <Route path="/login" element={null} />
        <Route path="/register" element={null} />
      </Route>

      <Route
        element={
          <ProtectedRoute>
            <OrganisationProvider>
              <OrganisationGate>
                <AppLayout />
              </OrganisationGate>
            </OrganisationProvider>
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<RoleHome />} />
        <Route path="/setup" element={<SetupPage />} />
        {/* Both roles: maintaining the financial data. */}
        <Route path="/history" element={<CompanyDetailPage />} />
        <Route path="/data" element={<LatestPeriodDataRedirect />} />
        <Route path="/periods/:periodId/data" element={<FinancialDataPage />} />
        {/* CEO / Admin only: confidential results and settings. */}
        <Route path="/overview" element={<AdminOnly><OverviewPage /></AdminOnly>} />
        <Route path="/analysis" element={<AdminOnly><LatestAssessedRedirect /></AdminOnly>} />
        <Route
          path="/periods/:periodId/dashboard"
          element={<AdminOnly><DashboardPage /></AdminOnly>}
        />
        <Route path="/settings" element={<AdminOnly><CompanySettingsPage /></AdminOnly>} />
        <Route path="/companies" element={<Navigate to="/" replace />} />
        <Route path="/companies/:companyId" element={<LegacyCompanyRedirect />} />
        <Route
          path="/companies/:companyId/periods/:periodId/:page"
          element={<LegacyCompanyRedirect />}
        />
      </Route>

      <Route path="/join" element={<JoinPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

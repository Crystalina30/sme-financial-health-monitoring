import { Navigate, Route, Routes } from 'react-router-dom';

import AppLayout from './layouts/AppLayout.jsx';
import ProtectedRoute from './components/ProtectedRoute.jsx';
import CompaniesPage from './pages/CompaniesPage.jsx';
import CompanyDetailPage from './pages/CompanyDetailPage.jsx';
import DashboardPage from './pages/DashboardPage.jsx';
import FinancialDataPage from './pages/FinancialDataPage.jsx';
import LoginPage from './pages/LoginPage.jsx';
import RegisterPage from './pages/RegisterPage.jsx';

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Navigate to="/companies" replace />} />
        <Route path="/companies" element={<CompaniesPage />} />
        <Route path="/companies/:companyId" element={<CompanyDetailPage />} />
        <Route
          path="/companies/:companyId/periods/:periodId/data"
          element={<FinancialDataPage />}
        />
        <Route
          path="/companies/:companyId/periods/:periodId/dashboard"
          element={<DashboardPage />}
        />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

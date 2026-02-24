/**
 * ARCHITECTURE NOTE:
 *
 * This app is a multi-account SEO monitoring system.
 *
 * - Route-scoped account context via :accountId URL params
 * - No user authentication gating
 * - Google OAuth is only used to bootstrap new GSC accounts into the system
 * - BootstrapGate ensures at least one GSC account is connected before rendering
 *
 * This is NOT a traditional user-authenticated application.
 * The "login" concept does not exist here — only portfolio selection.
 *
 * Route Structure:
 *   /                                      → SEOAccountSelector (portfolio picker)
 *   /dashboard/:accountId                  → DashboardSummary (account-scoped)
 *   /dashboard/:accountId/property/:pid    → PropertyDashboard
 *   /dashboard/:accountId/alerts           → AlertsPage
 *   /dashboard/:accountId/settings         → SettingsPage
 */

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { SessionProvider } from './SessionProvider';
import BootstrapGate from './components/BootstrapGate';
import SEOAccountSelector from './components/SEOAccountSelector';
import DashboardSummary from './components/DashboardSummary';
import PropertyDashboard from './components/PropertyDashboard';
import AlertsPage from './components/AlertsPage';
import SettingsPage from './components/SettingsPage';
import AlertConfig from './pages/AlertConfig';
import './index.css';

function App() {
  return (
    <SessionProvider>
      <BrowserRouter>
        <BootstrapGate>
          <Routes>
            {/* Master portfolio selector — landing page */}
            <Route path="/" element={<SEOAccountSelector />} />

            {/* Global alert configuration — accessible from the account selector */}
            <Route path="/alert-config" element={<AlertConfig />} />

            {/* Per-account dashboard routes — accountId is always in the URL */}
            <Route path="/dashboard/:accountId" element={<DashboardSummary />} />
            <Route path="/dashboard/:accountId/property/:propertyId" element={<PropertyDashboard />} />
            <Route path="/dashboard/:accountId/alerts" element={<AlertsPage />} />
            <Route path="/dashboard/:accountId/settings" element={<SettingsPage />} />

            {/* Deselecting account clears selection and returns to portfolio selector */}
            <Route path="/logout" element={<Navigate to="/?logout=true" replace />} />

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BootstrapGate>
      </BrowserRouter>
    </SessionProvider>
  );
}

export default App;

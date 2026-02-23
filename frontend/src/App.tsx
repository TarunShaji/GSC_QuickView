import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './AuthProvider';
import AuthGate from './components/AuthGate';
import SEOAccountSelector from './components/SEOAccountSelector';
import DashboardSummary from './components/DashboardSummary';
import PropertyDashboard from './components/PropertyDashboard';
import AlertsPage from './components/AlertsPage';
import SettingsPage from './components/SettingsPage';
import './index.css';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AuthGate>
          <Routes>
            {/* Master account selector — landing page */}
            <Route path="/" element={<SEOAccountSelector />} />

            {/* Per-account dashboard routes */}
            <Route path="/dashboard/:accountId" element={<DashboardSummary />} />
            <Route path="/dashboard/:accountId/property/:propertyId" element={<PropertyDashboard />} />
            <Route path="/dashboard/:accountId/alerts" element={<AlertsPage />} />
            <Route path="/dashboard/:accountId/settings" element={<SettingsPage />} />

            {/* Logout clears state and goes back to selector */}
            <Route path="/logout" element={<Navigate to="/?logout=true" replace />} />

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthGate>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;

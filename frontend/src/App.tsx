import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './AuthProvider';
import AuthGate from './components/AuthGate';
import DashboardSummary from './components/DashboardSummary';
import PropertyDashboard from './components/PropertyDashboard';
import AlertsPage from './components/AlertsPage';
import SettingsPage from './components/SettingsPage';
import './index.css';

function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 py-8">
        {children}
      </div>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <AuthGate>
        <BrowserRouter>
          <MainLayout>
            <Routes>
              <Route path="/" element={<DashboardSummary />} />
              <Route path="/property/:propertyId" element={<PropertyDashboard />} />
              <Route path="/alerts" element={<AlertsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </MainLayout>
        </BrowserRouter>
      </AuthGate>
    </AuthProvider>
  );
}

export default App;

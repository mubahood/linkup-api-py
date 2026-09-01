import React, { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { AppScopeProvider } from './contexts/AppScopeContext';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';

const DashboardHome  = lazy(() => import('./components/DashboardHome'));
const AccountsPage   = lazy(() => import('./components/AccountsPage'));
const ReportsPage    = lazy(() => import('./components/ReportsPage'));
const HubsPage       = lazy(() => import('./components/HubsPage'));
const EventsPage     = lazy(() => import('./components/EventsPage'));
const WalletPage     = lazy(() => import('./components/WalletPage'));
const SafetyPage     = lazy(() => import('./components/SafetyPage'));
const ReviewsPage    = lazy(() => import('./components/ReviewsPage'));
const AppVersionsPage = lazy(() => import('./components/AppVersionsPage'));
const ListingsPage    = lazy(() => import('./components/ListingsPage'));
const SubscriptionsPage = lazy(() => import('./components/SubscriptionsPage'));
const AnalyticsPage    = lazy(() => import('./components/AnalyticsPage'));

const Loader = () => <div className="page-loader">Loading…</div>;

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <Loader />;
  return isAuthenticated ? children : <Navigate to="/login" />;
}

function PublicRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <Loader />;
  return !isAuthenticated ? children : <Navigate to="/" />;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
      <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>}>
        <Route index element={<Suspense fallback={<Loader />}><DashboardHome /></Suspense>} />
        <Route path="accounts" element={<Suspense fallback={<Loader />}><AccountsPage /></Suspense>} />
        <Route path="reports" element={<Suspense fallback={<Loader />}><ReportsPage /></Suspense>} />
        <Route path="hubs" element={<Suspense fallback={<Loader />}><HubsPage /></Suspense>} />
        <Route path="activity" element={<Suspense fallback={<Loader />}><EventsPage /></Suspense>} />
        <Route path="wallet" element={<Suspense fallback={<Loader />}><WalletPage /></Suspense>} />
        <Route path="safety" element={<Suspense fallback={<Loader />}><SafetyPage /></Suspense>} />
        <Route path="reviews" element={<Suspense fallback={<Loader />}><ReviewsPage /></Suspense>} />
        <Route path="app-versions" element={<Suspense fallback={<Loader />}><AppVersionsPage /></Suspense>} />
        <Route path="listings" element={<Suspense fallback={<Loader />}><ListingsPage /></Suspense>} />
        <Route path="subscriptions" element={<Suspense fallback={<Loader />}><SubscriptionsPage /></Suspense>} />
        <Route path="analytics" element={<Suspense fallback={<Loader />}><AnalyticsPage /></Suspense>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppScopeProvider>
          <AppRoutes />
        </AppScopeProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

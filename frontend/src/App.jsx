import React, { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';

const DashboardHome = lazy(() => import('./components/DashboardHome'));
const AccountsPage  = lazy(() => import('./components/AccountsPage'));
const ReportsPage   = lazy(() => import('./components/ReportsPage'));
const HubsPage      = lazy(() => import('./components/HubsPage'));
const EventsPage    = lazy(() => import('./components/EventsPage'));

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
        <Route path="events" element={<Suspense fallback={<Loader />}><EventsPage /></Suspense>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

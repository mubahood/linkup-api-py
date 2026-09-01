import React, { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useAppScope, APP_LABELS } from '../contexts/AppScopeContext';
import Sidebar from '../components/Sidebar';
import { FiMenu, FiLogOut, FiUser, FiChevronDown } from 'react-icons/fi';

const TITLES = {
  '/':              'Dashboard',
  '/accounts':      'Accounts',
  '/reports':       'Reports',
  '/hubs':          'Hubs',
  '/activity':      'Activity Log',
  '/wallet':        'Wallet & Withdrawals',
  '/safety':        'Safety',
  '/reviews':       'Reviews',
  '/app-versions':  'App Version Config',
  '/listings':      'Listings Importer',
};

function AppSwitcher() {
  const { appId, setAppId } = useAppScope();
  return (
    <div style={{ position: 'relative' }}>
      <select
        value={appId}
        onChange={(e) => setAppId(e.target.value)}
        title="Scope the console to one app"
        style={{
          appearance: 'none', padding: '7px 30px 7px 12px', borderRadius: 8,
          border: '1px solid #d8d8e0', fontSize: 12.5, fontWeight: 700,
          background: appId === 'abanoonya' ? '#FCE7F3' : appId === 'linkup' ? '#EDE9FE' : appId === 'uganda_dating' ? '#D1FAE5' : '#fff',
          color: appId === 'abanoonya' ? '#DB2777' : appId === 'linkup' ? '#5B21B6' : appId === 'uganda_dating' ? '#047857' : '#444',
          cursor: 'pointer',
        }}
      >
        {Object.entries(APP_LABELS).map(([v, label]) => <option key={v} value={v}>{label}</option>)}
      </select>
      <FiChevronDown style={{ position: 'absolute', right: 10, top: 9, pointerEvents: 'none', fontSize: 13 }} />
    </div>
  );
}

export default function Dashboard() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const title = TITLES[location.pathname] || 'Dashboard';
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="dashboard">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="dashboard-main">
        <header className="dashboard-header">
          <button className="menu-toggle" onClick={() => setSidebarOpen(true)}>
            <FiMenu />
          </button>
          <h1 className="header-title">{title}</h1>
          <AppSwitcher />
          <div className="header-user">
            <FiUser className="header-avatar-icon" />
            <span className="header-username">{user?.display_name || user?.name || 'Admin'}</span>
            <button className="btn-icon" onClick={logout} title="Sign out">
              <FiLogOut />
            </button>
          </div>
        </header>
        <div className="dashboard-content">
          <Outlet />
        </div>
      </div>
    </div>
  );
}

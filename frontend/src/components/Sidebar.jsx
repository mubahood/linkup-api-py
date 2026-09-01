import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  FiHome, FiUsers, FiFlag, FiLayers, FiActivity, FiX,
  FiDollarSign, FiShield, FiCheckSquare, FiSmartphone, FiSearch, FiCreditCard,
  FiTrendingUp,
} from 'react-icons/fi';

const NAV = [
  { to: '/',             icon: FiHome,        label: 'Dashboard', end: true },
  { to: '/analytics',    icon: FiTrendingUp,  label: 'Analytics' },
  { to: '/accounts',     icon: FiUsers,       label: 'Accounts' },
  { to: '/reports',      icon: FiFlag,        label: 'Reports' },
  { to: '/safety',       icon: FiShield,      label: 'Safety' },
  { to: '/reviews',      icon: FiCheckSquare, label: 'Reviews' },
  { to: '/listings',     icon: FiSearch,      label: 'Listings' },
  { to: '/subscriptions', icon: FiCreditCard, label: 'Subscriptions' },
  { to: '/wallet',       icon: FiDollarSign,  label: 'Wallet' },
  { to: '/hubs',         icon: FiLayers,      label: 'Hubs' },
  { to: '/app-versions', icon: FiSmartphone,  label: 'App Versions' },
  { to: '/activity',     icon: FiActivity,    label: 'Activity Log' },
];

export default function Sidebar({ open, onClose }) {
  return (
    <>
      <div className="sidebar-overlay" onClick={onClose} />
      <nav className={`sidebar ${open ? 'sidebar--open' : ''}`}>
        <div className="sidebar-brand">
          <img src="/logo.svg" alt="" className="brand-mark" style={{ padding: 0 }} />
          <div className="brand-info">
            <span className="brand-text">LinkUp Platform</span>
            <span className="brand-tag">Admin Console</span>
          </div>
          <button className="sidebar-close" onClick={onClose}><FiX /></button>
        </div>

        <ul className="sidebar-nav">
          {NAV.map(({ to, icon: Icon, label, end }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={end}
                className={({ isActive }) => `nav-link ${isActive ? 'nav-link--active' : ''}`}
                onClick={onClose}
              >
                <Icon className="nav-icon" />
                <span>{label}</span>
              </NavLink>
            </li>
          ))}
        </ul>

        <div className="sidebar-footer">LinkUp, Abanoonya Pro &amp; Uganda Dating App © 2026</div>
      </nav>
    </>
  );
}

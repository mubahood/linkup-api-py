import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  FiHome, FiUsers, FiMessageSquare, FiCreditCard,
  FiDollarSign, FiMessageCircle, FiBriefcase, FiX,
  FiTrendingUp, FiHeart, FiSettings,
} from 'react-icons/fi';

const NAV = [
  { to: '/',        icon: FiHome,          label: 'Dashboard',       end: true },
  { to: '/users',   icon: FiUsers,         label: 'Members' },
  { to: '/payments',icon: FiCreditCard,    label: 'Payments' },
  { to: '/wallets', icon: FiDollarSign,    label: 'Wallets' },
  { to: '/chats',   icon: FiMessageCircle, label: 'Chats' },
];

export default function Sidebar({ open, onClose }) {
  return (
    <>
      <div className="sidebar-overlay" onClick={onClose} />
      <nav className={`sidebar ${open ? 'sidebar--open' : ''}`}>
        <div className="sidebar-brand">
          <div className="brand-mark">LU</div>
          <div className="brand-info">
            <span className="brand-text">LinkUp</span>
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

        <div className="sidebar-footer">LinkUp Platform © 2026</div>
      </nav>
    </>
  );
}

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminAPI, dataOf } from '../services/api';
import { useAppScope } from '../contexts/AppScopeContext';
import {
  FiUsers, FiUserCheck, FiStar, FiUserPlus, FiSlash,
  FiLayers, FiFileText, FiBriefcase, FiCalendar, FiHeart, FiLink2,
  FiFlag, FiAlertTriangle, FiRefreshCw, FiShield, FiCheckSquare, FiDollarSign,
} from 'react-icons/fi';

const card = {
  background: '#fff', border: '1px solid #ececf1', borderRadius: 10,
  padding: '16px 18px', display: 'flex', alignItems: 'center', gap: 14,
};
const iconWrap = (c) => ({
  width: 42, height: 42, borderRadius: 10, display: 'grid', placeItems: 'center',
  background: `${c}14`, color: c, flexShrink: 0,
});

function Stat({ icon: Icon, label, value, color, onClick, urgent }) {
  return (
    <div style={{ ...card, cursor: onClick ? 'pointer' : 'default',
      borderColor: urgent && value > 0 ? '#fecaca' : '#ececf1' }} onClick={onClick}>
      <div style={iconWrap(color)}><Icon size={20} /></div>
      <div>
        <div style={{ fontSize: 22, fontWeight: 800, lineHeight: 1.1,
          color: urgent && value > 0 ? '#DC2626' : '#151519' }}>
          {value ?? '—'}
        </div>
        <div style={{ fontSize: 12.5, color: '#6b6b76', marginTop: 2 }}>{label}</div>
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div style={{ marginBottom: 28 }}>
      <h3 style={{ fontSize: 13, textTransform: 'uppercase', letterSpacing: 0.6,
        color: '#8a8a93', margin: '0 0 12px', fontWeight: 700 }}>{title}</h3>
      <div style={{ display: 'grid', gap: 14,
        gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))' }}>
        {children}
      </div>
    </div>
  );
}

export default function DashboardHome() {
  const navigate = useNavigate();
  const { appId } = useAppScope();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = async () => {
    setLoading(true); setError(null);
    try {
      const res = await adminAPI.stats({ app_id: appId || undefined });
      setStats(dataOf(res));
    } catch (e) {
      setError(e.response?.data?.message || 'Could not load stats.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [appId]);

  if (loading) return <div className="page-loader">Loading…</div>;
  if (error) {
    return (
      <div style={{ padding: 24 }}>
        <p style={{ color: '#DC2626' }}>{error}</p>
        <button className="btn" onClick={load}><FiRefreshCw /> Retry</button>
      </div>
    );
  }

  const a = stats?.accounts || {};
  const c = stats?.content || {};
  const m = stats?.moderation || {};

  return (
    <div style={{ padding: 4 }}>
      <Section title="Accounts">
        <Stat icon={FiUsers}     label="Total accounts"   value={a.total}         color="#7C3AED" onClick={() => navigate('/accounts')} />
        <Stat icon={FiUserCheck} label="Active"           value={a.active}        color="#059669" onClick={() => navigate('/accounts')} />
        <Stat icon={FiStar}      label="Premium"          value={a.premium}       color="#B45309" onClick={() => navigate('/accounts')} />
        <Stat icon={FiUserPlus}  label="New today"        value={a.new_today}     color="#2563EB" onClick={() => navigate('/accounts')} />
        <Stat icon={FiUserPlus}  label="New this week"    value={a.new_this_week} color="#0891B2" onClick={() => navigate('/accounts')} />
        <Stat icon={FiSlash}     label="Suspended"        value={a.suspended}     color="#DC2626" onClick={() => navigate('/accounts')} />
      </Section>

      <Section title="Content">
        <Stat icon={FiLayers}    label="Hubs"        value={c.hubs}      color="#7C3AED" onClick={() => navigate('/hubs')} />
        <Stat icon={FiFileText}  label="Hub posts"   value={c.hub_posts} color="#4F46E5" />
        <Stat icon={FiBriefcase} label="Open jobs"   value={c.jobs_open} color="#0891B2" />
        <Stat icon={FiCalendar}  label="Events"      value={c.events}    color="#2563EB" />
        <Stat icon={FiHeart}     label="Matches"     value={c.matches}   color="#DB2777" />
        <Stat icon={FiLink2}     label="Links"       value={c.links}     color="#059669" />
      </Section>

      <Section title="Needs your attention">
        <Stat icon={FiFlag}          label="Pending reports"      value={m.pending_reports}      color="#DC2626" urgent onClick={() => navigate('/reports')} />
        <Stat icon={FiShield}        label="Open panic alerts"    value={m.open_panic_alerts}    color="#DC2626" urgent onClick={() => navigate('/safety')} />
        <Stat icon={FiDollarSign}    label="Withdrawals to review" value={m.pending_withdrawals} color="#DC2626" urgent onClick={() => navigate('/wallet')} />
        <Stat icon={FiCheckSquare}   label="KYC to review"        value={m.pending_kyc}          color="#B45309" onClick={() => navigate('/reviews')} />
        <Stat icon={FiCheckSquare}   label="Institutions to review" value={m.pending_institutions} color="#B45309" onClick={() => navigate('/reviews')} />
        <Stat icon={FiAlertTriangle} label="Total reports (all-time)" value={m.total_reports}     color="#8a8a93" onClick={() => navigate('/reports')} />
      </Section>
    </div>
  );
}

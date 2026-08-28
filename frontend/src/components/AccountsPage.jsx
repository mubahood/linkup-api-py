import React, { useEffect, useState, useCallback } from 'react';
import { adminAPI, dataOf, pageOf } from '../services/api';
import {
  FiSearch, FiStar, FiSlash, FiRotateCcw, FiRefreshCw, FiUserPlus, FiEdit2,
  FiHeart, FiBriefcase, FiCamera, FiMapPin,
} from 'react-icons/fi';
import {
  Badge, Avatar, fmtDate, tableStyle, thStyle, tdStyle,
  Toolbar, Pager, EmptyRow, btn, ActionMenu,
} from './adminUi';
import AccountFormModal from './AccountFormModal';

const STATUSES = ['', 'active', 'suspended', 'closed'];
const GENDER_LABEL = { male: 'Man', female: 'Woman' };

function truncate(text, max = 64) {
  if (!text) return '';
  return text.length > max ? `${text.slice(0, max).trimEnd()}…` : text;
}

export default function AccountsPage() {
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({ page: 1, lastPage: 1, total: 0 });
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [q, setQ] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const [editingAccount, setEditingAccount] = useState(null);
  const [editLoadingId, setEditLoadingId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminAPI.accounts({ q, status, page, per_page: 20 });
      const p = pageOf(res);
      setRows(p.items);
      setMeta({ page: p.page, lastPage: p.lastPage, total: p.total });
    } catch (_) {
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [q, status, page]);

  useEffect(() => { load(); }, [load]);

  const setStatusFor = async (acct, newStatus) => {
    const verb = newStatus === 'active' ? 'reinstate' : 'suspend';
    if (!window.confirm(`Are you sure you want to ${verb} ${acct.display_name || acct.handle}?`)) return;
    setBusyId(acct.id);
    try {
      await adminAPI.accountStatus(acct.id, { status: newStatus });
      await load();
    } catch (e) {
      alert(e.response?.data?.message || 'Action failed.');
    } finally {
      setBusyId(null);
    }
  };

  const togglePremium = async (acct) => {
    setBusyId(acct.id);
    try {
      await adminAPI.accountPremium(acct.id, { is_premium: !acct.is_premium });
      await load();
    } catch (e) {
      alert(e.response?.data?.message || 'Action failed.');
    } finally {
      setBusyId(null);
    }
  };

  const openEdit = async (acct) => {
    setEditLoadingId(acct.id);
    try {
      const res = await adminAPI.accountShow(acct.id);
      setEditingAccount(dataOf(res));
    } catch (e) {
      alert(e.response?.data?.message || 'Could not load this account.');
    } finally {
      setEditLoadingId(null);
    }
  };

  const onSearch = (e) => { e.preventDefault(); setPage(1); load(); };

  return (
    <div style={{ padding: 4 }}>
      <Toolbar>
        <form onSubmit={onSearch} style={{ display: 'flex', gap: 8, flex: 1, minWidth: 220 }}>
          <div style={{ position: 'relative', flex: 1, maxWidth: 360 }}>
            <FiSearch style={{ position: 'absolute', left: 10, top: 10, color: '#9a9aa3' }} />
            <input
              value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="Search name, handle, email, phone…"
              style={{ width: '100%', padding: '9px 12px 9px 32px', borderRadius: 8,
                border: '1px solid #d8d8e0', fontSize: 13.5 }}
            />
          </div>
        </form>
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          style={{ padding: '9px 12px', borderRadius: 8, border: '1px solid #d8d8e0', fontSize: 13.5 }}>
          {STATUSES.map((s) => <option key={s} value={s}>{s ? s[0].toUpperCase() + s.slice(1) : 'All statuses'}</option>)}
        </select>
        <button style={btn(false)} onClick={load}><FiRefreshCw /> Refresh</button>
        <button style={btn(true)} onClick={() => setCreating(true)}><FiUserPlus /> New account</button>
      </Toolbar>

      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={thStyle}>Member</th>
            <th style={thStyle}>Profile</th>
            <th style={thStyle}>Location</th>
            <th style={thStyle}>Modes</th>
            <th style={thStyle}>Photos</th>
            <th style={thStyle}>Status</th>
            <th style={thStyle}>Tier</th>
            <th style={thStyle}>Joined</th>
            <th style={{ ...thStyle, textAlign: 'right' }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <EmptyRow colSpan={9} text="Loading…" />
          ) : rows.length === 0 ? (
            <EmptyRow colSpan={9} text="No accounts found." />
          ) : rows.map((u) => {
            const dp = u.dating_profile_summary;
            const modes = u.modes_enabled || {};
            return (
              <tr key={u.id}>
                <td style={tdStyle}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <Avatar name={u.display_name} avatar={u.avatar} />
                    <div>
                      <div style={{ fontWeight: 700 }}>{u.display_name || '—'}</div>
                      <div style={{ fontSize: 12, color: '#9a9aa3' }}>@{u.handle || '—'}</div>
                      <div style={{ fontSize: 11, color: '#b3b3bb' }}>{u.email || u.phone || '—'}</div>
                    </div>
                  </div>
                </td>
                <td style={{ ...tdStyle, maxWidth: 260 }}>
                  {dp ? (
                    <>
                      <div style={{ fontSize: 12.5, fontWeight: 600 }}>
                        {GENDER_LABEL[dp.gender] || dp.gender || '—'}{dp.age ? `, ${dp.age}` : ''}
                      </div>
                      {dp.bio && <div style={{ fontSize: 11.5, color: '#8a8a93', marginTop: 2 }}>{truncate(dp.bio)}</div>}
                    </>
                  ) : <span style={{ color: '#c4c4cc', fontSize: 12 }}>No dating profile</span>}
                </td>
                <td style={tdStyle}>
                  {dp?.location_label ? (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12.5 }}>
                      <FiMapPin size={12} color="#9a9aa3" /> {dp.location_label}
                    </span>
                  ) : <span style={{ color: '#c4c4cc', fontSize: 12 }}>—</span>}
                </td>
                <td style={tdStyle}>
                  <div style={{ display: 'flex', gap: 5 }}>
                    {modes.sparks && (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, fontSize: 10.5, fontWeight: 700, color: '#DB2777', background: '#FCE7F3', borderRadius: 5, padding: '2px 7px' }}>
                        <FiHeart size={10} /> Sparks
                      </span>
                    )}
                    {modes.professional && (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, fontSize: 10.5, fontWeight: 700, color: '#5B21B6', background: '#EDE9FE', borderRadius: 5, padding: '2px 7px' }}>
                        <FiBriefcase size={10} /> Pro
                      </span>
                    )}
                    {!modes.sparks && !modes.professional && <span style={{ color: '#c4c4cc', fontSize: 12 }}>—</span>}
                  </div>
                </td>
                <td style={tdStyle}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12.5, color: u.photo_count ? '#27272a' : '#c4c4cc' }}>
                    <FiCamera size={12} /> {u.photo_count || 0}
                  </span>
                </td>
                <td style={tdStyle}><Badge value={u.account_status} /></td>
                <td style={tdStyle}>{u.is_premium ? <Badge value="premium">Premium</Badge> : <span style={{ color: '#9a9aa3' }}>Free</span>}</td>
                <td style={tdStyle}>{fmtDate(u.created_at)}</td>
                <td style={{ ...tdStyle, textAlign: 'right' }}>
                  <ActionMenu items={[
                    {
                      label: editLoadingId === u.id ? 'Loading…' : 'Edit',
                      icon: FiEdit2, onClick: () => openEdit(u),
                    },
                    {
                      label: u.is_premium ? 'Revoke premium' : 'Grant premium',
                      icon: FiStar, onClick: () => togglePremium(u),
                    },
                    u.account_status === 'active'
                      ? { label: 'Suspend', icon: FiSlash, danger: true, onClick: () => setStatusFor(u, 'suspended') }
                      : { label: 'Reinstate', icon: FiRotateCcw, onClick: () => setStatusFor(u, 'active') },
                  ]} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <Pager page={meta.page} lastPage={meta.lastPage} total={meta.total} onPage={setPage} />

      <AccountFormModal open={creating} onClose={() => setCreating(false)} onSaved={load} />
      <AccountFormModal
        open={!!editingAccount}
        account={editingAccount}
        onClose={() => setEditingAccount(null)}
        onSaved={load}
      />
    </div>
  );
}

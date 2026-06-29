import React, { useEffect, useState, useCallback } from 'react';
import { adminAPI, pageOf } from '../services/api';
import { FiSearch, FiStar, FiSlash, FiRotateCcw, FiRefreshCw } from 'react-icons/fi';
import {
  Badge, Avatar, fmtDate, tableStyle, thStyle, tdStyle,
  Toolbar, Pager, EmptyRow, btn,
} from './adminUi';

const STATUSES = ['', 'active', 'suspended', 'closed'];

export default function AccountsPage() {
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({ page: 1, lastPage: 1, total: 0 });
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [q, setQ] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);

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
      </Toolbar>

      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={thStyle}>Account</th>
            <th style={thStyle}>Contact</th>
            <th style={thStyle}>Status</th>
            <th style={thStyle}>Tier</th>
            <th style={thStyle}>KYC</th>
            <th style={thStyle}>Joined</th>
            <th style={{ ...thStyle, textAlign: 'right' }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <EmptyRow colSpan={7} text="Loading…" />
          ) : rows.length === 0 ? (
            <EmptyRow colSpan={7} text="No accounts found." />
          ) : rows.map((u) => (
            <tr key={u.id}>
              <td style={tdStyle}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <Avatar name={u.display_name} avatar={u.avatar} />
                  <div>
                    <div style={{ fontWeight: 700 }}>{u.display_name || '—'}</div>
                    <div style={{ fontSize: 12, color: '#9a9aa3' }}>@{u.handle || '—'}</div>
                  </div>
                </div>
              </td>
              <td style={tdStyle}>
                <div>{u.email || '—'}</div>
                <div style={{ fontSize: 12, color: '#9a9aa3' }}>{u.phone || ''}</div>
              </td>
              <td style={tdStyle}><Badge value={u.account_status} /></td>
              <td style={tdStyle}>{u.is_premium ? <Badge value="premium">Premium</Badge> : <span style={{ color: '#9a9aa3' }}>Free</span>}</td>
              <td style={tdStyle}>L{u.kyc_level ?? 0}</td>
              <td style={tdStyle}>{fmtDate(u.created_at)}</td>
              <td style={{ ...tdStyle, textAlign: 'right' }}>
                <div style={{ display: 'inline-flex', gap: 6 }}>
                  <button style={btn(false)} disabled={busyId === u.id}
                    onClick={() => togglePremium(u)}>
                    <FiStar /> {u.is_premium ? 'Revoke' : 'Premium'}
                  </button>
                  {u.account_status === 'active' ? (
                    <button style={{ ...btn(false), color: '#DC2626', borderColor: '#f3c4c4' }}
                      disabled={busyId === u.id} onClick={() => setStatusFor(u, 'suspended')}>
                      <FiSlash /> Suspend
                    </button>
                  ) : (
                    <button style={{ ...btn(false), color: '#059669', borderColor: '#bfe7d4' }}
                      disabled={busyId === u.id} onClick={() => setStatusFor(u, 'active')}>
                      <FiRotateCcw /> Reinstate
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <Pager page={meta.page} lastPage={meta.lastPage} total={meta.total} onPage={setPage} />
    </div>
  );
}

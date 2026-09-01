import React, { useEffect, useState, useCallback } from 'react';
import { adminAPI, pageOf, dataOf } from '../services/api';
import { FiCheck, FiRefreshCw, FiAlertTriangle } from 'react-icons/fi';
import {
  Badge, Avatar, fmtDate, tableStyle, thStyle, tdStyle, Toolbar, Pager, EmptyRow, btn,
} from './adminUi';

const TABS = [
  { id: 'panic', label: 'Panic / SOS alerts' },
  { id: 'blocks', label: 'Blocks' },
];

export default function SafetyPage() {
  const [tab, setTab] = useState('panic');
  return (
    <div style={{ padding: 4 }}>
      <div style={{ display: 'flex', gap: 4, marginBottom: 16 }}>
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            padding: '8px 14px', borderRadius: 8, fontSize: 13, fontWeight: 700,
            border: 'none', cursor: 'pointer',
            background: tab === t.id ? '#7C3AED' : 'transparent',
            color: tab === t.id ? '#fff' : '#6b6b76',
          }}>{t.label}</button>
        ))}
      </div>
      {tab === 'panic' ? <PanicTab /> : <BlocksTab />}
    </div>
  );
}

function PanicTab() {
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({ page: 1, lastPage: 1, total: 0 });
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [status, setStatus] = useState('open');
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminAPI.panicAlerts({ status: status || undefined, page, per_page: 20 });
      const p = pageOf(res);
      setRows(p.items);
      setMeta({ page: p.page, lastPage: p.lastPage, total: p.total });
    } catch (_) { setRows([]); } finally { setLoading(false); }
  }, [status, page]);

  useEffect(() => { load(); }, [load]);

  const resolve = async (a) => {
    const note = window.prompt('Resolution note (e.g. "confirmed safe via phone call"):', '');
    if (note === null) return;
    setBusyId(a.id);
    try { await adminAPI.panicAlertResolve(a.id, { status: 'resolved', note }); await load(); }
    catch (e) { alert(e.response?.data?.message || 'Failed.'); }
    finally { setBusyId(null); }
  };

  return (
    <>
      <Toolbar>
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          style={{ padding: '9px 12px', borderRadius: 8, border: '1px solid #d8d8e0', fontSize: 13.5 }}>
          <option value="open">Open</option>
          <option value="acknowledged">Acknowledged</option>
          <option value="resolved">Resolved</option>
          <option value="">All</option>
        </select>
        <button style={btn(false)} onClick={load}><FiRefreshCw /> Refresh</button>
      </Toolbar>
      <table style={tableStyle}>
        <thead><tr>
          <th style={thStyle}>Member</th><th style={thStyle}>Location</th>
          <th style={thStyle}>Contacts notified</th><th style={thStyle}>Status</th>
          <th style={thStyle}>Fired</th><th style={{ ...thStyle, textAlign: 'right' }}>Actions</th>
        </tr></thead>
        <tbody>
          {loading ? <EmptyRow colSpan={6} text="Loading…" />
            : rows.length === 0 ? <EmptyRow colSpan={6} text="No panic alerts — good." />
            : rows.map((a) => (
              <tr key={a.id}>
                <td style={tdStyle}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Avatar name={a.account?.display_name} avatar={a.account?.avatar} size={28} />
                    {a.account?.display_name || '—'}
                  </div>
                </td>
                <td style={tdStyle}>{a.location_text || '—'}</td>
                <td style={tdStyle}>{a.contacts_notified}</td>
                <td style={tdStyle}>
                  {a.status === 'open'
                    ? <span style={{ color: '#DC2626', fontWeight: 800, display: 'inline-flex', alignItems: 'center', gap: 4 }}><FiAlertTriangle /> Open</span>
                    : <Badge value={a.status} />}
                </td>
                <td style={tdStyle}>{fmtDate(a.created_at)}</td>
                <td style={{ ...tdStyle, textAlign: 'right' }}>
                  {a.status !== 'resolved' && (
                    <button style={btn(true)} disabled={busyId === a.id} onClick={() => resolve(a)}>
                      <FiCheck /> Resolve
                    </button>
                  )}
                </td>
              </tr>
            ))}
        </tbody>
      </table>
      <Pager page={meta.page} lastPage={meta.lastPage} total={meta.total} onPage={setPage} />
    </>
  );
}

function BlocksTab() {
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({ page: 1, lastPage: 1, total: 0 });
  const [mostBlocked, setMostBlocked] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminAPI.blocks({ page, per_page: 20 });
      const p = pageOf(res);
      setRows(p.items);
      setMeta({ page: p.page, lastPage: p.lastPage, total: p.total });
      setMostBlocked(dataOf(await adminAPI.mostBlocked()) || []);
    } catch (_) { setRows([]); } finally { setLoading(false); }
  }, [page]);

  useEffect(() => { load(); }, [load]);

  return (
    <>
      {mostBlocked.length > 0 && (
        <div style={{ background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: 10,
          padding: '12px 16px', marginBottom: 16 }}>
          <div style={{ fontWeight: 800, fontSize: 12.5, color: '#C2410C', marginBottom: 6 }}>
            Most-blocked accounts — a real abuse signal
          </div>
          {mostBlocked.slice(0, 5).map((m) => (
            <div key={m.account.id} style={{ fontSize: 12.5, padding: '2px 0' }}>
              {m.account.display_name} (@{m.account.handle}) — blocked by {m.block_count} people
            </div>
          ))}
        </div>
      )}
      <Toolbar><button style={btn(false)} onClick={load}><FiRefreshCw /> Refresh</button></Toolbar>
      <table style={tableStyle}>
        <thead><tr>
          <th style={thStyle}>Blocker</th><th style={thStyle}>Blocked</th><th style={thStyle}>When</th>
        </tr></thead>
        <tbody>
          {loading ? <EmptyRow colSpan={3} text="Loading…" />
            : rows.length === 0 ? <EmptyRow colSpan={3} text="No blocks yet." />
            : rows.map((b) => (
              <tr key={b.id}>
                <td style={tdStyle}>{b.blocker?.display_name || '—'}</td>
                <td style={tdStyle}>{b.blocked?.display_name || '—'}</td>
                <td style={tdStyle}>{fmtDate(b.created_at)}</td>
              </tr>
            ))}
        </tbody>
      </table>
      <Pager page={meta.page} lastPage={meta.lastPage} total={meta.total} onPage={setPage} />
    </>
  );
}

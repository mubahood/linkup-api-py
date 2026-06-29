import React, { useEffect, useState, useCallback } from 'react';
import { adminAPI, pageOf } from '../services/api';
import { FiCheck, FiXCircle, FiAlertTriangle, FiRefreshCw } from 'react-icons/fi';
import {
  Badge, fmtDate, tableStyle, thStyle, tdStyle, Toolbar, Pager, EmptyRow, btn,
} from './adminUi';

const STATUSES = ['pending', 'resolved', 'dismissed', 'escalated', ''];

export default function ReportsPage() {
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({ page: 1, lastPage: 1, total: 0 });
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [status, setStatus] = useState('pending');
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminAPI.reports({ status, page, per_page: 20 });
      const p = pageOf(res);
      setRows(p.items);
      setMeta({ page: p.page, lastPage: p.lastPage, total: p.total });
    } catch (_) {
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [status, page]);

  useEffect(() => { load(); }, [load]);

  const act = async (report, action) => {
    setBusyId(report.id);
    try {
      await adminAPI.reportResolve(report.id, { action });
      await load();
    } catch (e) {
      alert(e.response?.data?.message || 'Action failed.');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div style={{ padding: 4 }}>
      <Toolbar>
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          style={{ padding: '9px 12px', borderRadius: 8, border: '1px solid #d8d8e0', fontSize: 13.5 }}>
          {STATUSES.map((s) => <option key={s} value={s}>{s ? s[0].toUpperCase() + s.slice(1) : 'All'}</option>)}
        </select>
        <button style={btn(false)} onClick={load}><FiRefreshCw /> Refresh</button>
      </Toolbar>

      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={thStyle}>Reason</th>
            <th style={thStyle}>Reported user</th>
            <th style={thStyle}>Reporter</th>
            <th style={thStyle}>Status</th>
            <th style={thStyle}>Date</th>
            <th style={{ ...thStyle, textAlign: 'right' }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <EmptyRow colSpan={6} text="Loading…" />
          ) : rows.length === 0 ? (
            <EmptyRow colSpan={6} text="No reports." />
          ) : rows.map((r) => (
            <tr key={r.id}>
              <td style={tdStyle}>
                <div style={{ fontWeight: 700, textTransform: 'capitalize' }}>{r.reason || '—'}</div>
                {r.details && <div style={{ fontSize: 12, color: '#9a9aa3', maxWidth: 280 }}>{r.details}</div>}
              </td>
              <td style={tdStyle}>{r.target?.display_name || r.target_account_id || '—'}</td>
              <td style={tdStyle}>{r.reporter?.display_name || r.reporter?.handle || '—'}</td>
              <td style={tdStyle}><Badge value={r.status} /></td>
              <td style={tdStyle}>{fmtDate(r.created_at)}</td>
              <td style={{ ...tdStyle, textAlign: 'right' }}>
                {r.status === 'pending' ? (
                  <div style={{ display: 'inline-flex', gap: 6 }}>
                    <button style={{ ...btn(false), color: '#059669', borderColor: '#bfe7d4' }}
                      disabled={busyId === r.id} onClick={() => act(r, 'resolve')}>
                      <FiCheck /> Resolve
                    </button>
                    <button style={btn(false)} disabled={busyId === r.id}
                      onClick={() => act(r, 'dismiss')}><FiXCircle /> Dismiss</button>
                    <button style={{ ...btn(false), color: '#DC2626', borderColor: '#f3c4c4' }}
                      disabled={busyId === r.id} onClick={() => act(r, 'escalate')}>
                      <FiAlertTriangle /> Escalate
                    </button>
                  </div>
                ) : <span style={{ color: '#9a9aa3', fontSize: 12.5 }}>—</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <Pager page={meta.page} lastPage={meta.lastPage} total={meta.total} onPage={setPage} />
    </div>
  );
}

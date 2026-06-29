import React, { useEffect, useState, useCallback } from 'react';
import { adminAPI, pageOf } from '../services/api';
import { FiSearch, FiRefreshCw } from 'react-icons/fi';
import {
  Badge, fmtDate, tableStyle, thStyle, tdStyle, Toolbar, Pager, EmptyRow, btn,
} from './adminUi';

export default function EventsPage() {
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({ page: 1, lastPage: 1, total: 0 });
  const [loading, setLoading] = useState(true);
  const [verb, setVerb] = useState('');
  const [acct, setAcct] = useState('');
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, per_page: 50 };
      if (verb) params.verb = verb;
      if (acct) params.account_id = acct;
      const res = await adminAPI.events(params);
      const p = pageOf(res);
      setRows(p.items);
      setMeta({ page: p.page, lastPage: p.lastPage, total: p.total });
    } catch (_) {
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [verb, acct, page]);

  useEffect(() => { load(); }, [load]);

  const onSearch = (e) => { e.preventDefault(); setPage(1); load(); };

  const metaPreview = (e) => {
    const m = e.meta ?? e.data ?? e.payload;
    if (!m) return '—';
    try { return typeof m === 'string' ? m : JSON.stringify(m); }
    catch { return '—'; }
  };

  return (
    <div style={{ padding: 4 }}>
      <Toolbar>
        <form onSubmit={onSearch} style={{ display: 'flex', gap: 8, flex: 1, flexWrap: 'wrap' }}>
          <div style={{ position: 'relative' }}>
            <FiSearch style={{ position: 'absolute', left: 10, top: 10, color: '#9a9aa3' }} />
            <input value={verb} onChange={(e) => setVerb(e.target.value)} placeholder="Filter by verb (e.g. profile.view)"
              style={{ padding: '9px 12px 9px 32px', borderRadius: 8, border: '1px solid #d8d8e0',
                fontSize: 13.5, width: 240 }} />
          </div>
          <input value={acct} onChange={(e) => setAcct(e.target.value)} placeholder="Account ID"
            style={{ padding: '9px 12px', borderRadius: 8, border: '1px solid #d8d8e0',
              fontSize: 13.5, width: 240 }} />
          <button style={btn(true)} type="submit"><FiSearch /> Filter</button>
        </form>
        <button style={btn(false)} onClick={load}><FiRefreshCw /> Refresh</button>
      </Toolbar>

      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={thStyle}>Verb</th>
            <th style={thStyle}>Account</th>
            <th style={thStyle}>Target</th>
            <th style={thStyle}>Meta</th>
            <th style={thStyle}>When</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <EmptyRow colSpan={5} text="Loading…" />
          ) : rows.length === 0 ? (
            <EmptyRow colSpan={5} text="No events." />
          ) : rows.map((e) => (
            <tr key={e.id}>
              <td style={tdStyle}><Badge>{e.verb || '—'}</Badge></td>
              <td style={{ ...tdStyle, fontSize: 12, color: '#6b6b76' }}>{e.account_id || '—'}</td>
              <td style={{ ...tdStyle, fontSize: 12, color: '#6b6b76' }}>
                {e.target_type ? `${e.target_type}:${e.target_id || ''}` : (e.target_id || '—')}
              </td>
              <td style={{ ...tdStyle, fontSize: 12, color: '#6b6b76', maxWidth: 280,
                whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{metaPreview(e)}</td>
              <td style={tdStyle}>{fmtDate(e.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <Pager page={meta.page} lastPage={meta.lastPage} total={meta.total} onPage={setPage} />
    </div>
  );
}

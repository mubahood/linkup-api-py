import React, { useEffect, useState, useCallback } from 'react';
import { adminAPI, pageOf } from '../services/api';
import { FiSearch, FiRefreshCw, FiUsers } from 'react-icons/fi';
import {
  Badge, fmtDate, tableStyle, thStyle, tdStyle, Toolbar, Pager, EmptyRow, btn,
} from './adminUi';

export default function HubsPage() {
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({ page: 1, lastPage: 1, total: 0 });
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminAPI.hubs({ q, page, per_page: 20 });
      const p = pageOf(res);
      setRows(p.items);
      setMeta({ page: p.page, lastPage: p.lastPage, total: p.total });
    } catch (_) {
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [q, page]);

  useEffect(() => { load(); }, [load]);

  const onSearch = (e) => { e.preventDefault(); setPage(1); load(); };

  return (
    <div style={{ padding: 4 }}>
      <Toolbar>
        <form onSubmit={onSearch} style={{ display: 'flex', flex: 1, minWidth: 220 }}>
          <div style={{ position: 'relative', flex: 1, maxWidth: 360 }}>
            <FiSearch style={{ position: 'absolute', left: 10, top: 10, color: '#9a9aa3' }} />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search hubs by name…"
              style={{ width: '100%', padding: '9px 12px 9px 32px', borderRadius: 8,
                border: '1px solid #d8d8e0', fontSize: 13.5 }} />
          </div>
        </form>
        <button style={btn(false)} onClick={load}><FiRefreshCw /> Refresh</button>
      </Toolbar>

      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={thStyle}>Hub</th>
            <th style={thStyle}>Members</th>
            <th style={thStyle}>Visibility</th>
            <th style={thStyle}>Category</th>
            <th style={thStyle}>Created</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <EmptyRow colSpan={5} text="Loading…" />
          ) : rows.length === 0 ? (
            <EmptyRow colSpan={5} text="No hubs found." />
          ) : rows.map((h) => (
            <tr key={h.id}>
              <td style={tdStyle}>
                <div style={{ fontWeight: 700 }}>{h.name || '—'}</div>
                {h.description && <div style={{ fontSize: 12, color: '#9a9aa3', maxWidth: 320,
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{h.description}</div>}
              </td>
              <td style={tdStyle}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                  <FiUsers size={13} color="#9a9aa3" /> {h.member_count ?? 0}
                </span>
              </td>
              <td style={tdStyle}>
                <Badge>{h.is_private ? 'Private' : (h.visibility || 'Public')}</Badge>
              </td>
              <td style={tdStyle}>{h.category || h.type || '—'}</td>
              <td style={tdStyle}>{fmtDate(h.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <Pager page={meta.page} lastPage={meta.lastPage} total={meta.total} onPage={setPage} />
    </div>
  );
}

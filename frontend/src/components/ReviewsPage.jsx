import React, { useEffect, useState, useCallback } from 'react';
import { adminAPI, pageOf } from '../services/api';
import { FiCheck, FiX, FiRefreshCw } from 'react-icons/fi';
import { fmtDate, tableStyle, thStyle, tdStyle, Toolbar, Pager, EmptyRow, btn } from './adminUi';

const TABS = [
  { id: 'kyc', label: 'KYC verification' },
  { id: 'institutions', label: 'Institutions' },
];

// Two dead-end approval queues in one place: user-submitted national ID
// verification, and user-suggested schools/universities. Both used to save to
// the database with a "pending" status and nothing ever listed or resolved them.
export default function ReviewsPage() {
  const [tab, setTab] = useState('kyc');
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
      {tab === 'kyc' ? <KycTab /> : <InstitutionsTab />}
    </div>
  );
}

function KycTab() {
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({ page: 1, lastPage: 1, total: 0 });
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [status, setStatus] = useState('pending');
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminAPI.kycQueue({ status, page, per_page: 20 });
      const p = pageOf(res);
      setRows(p.items);
      setMeta({ page: p.page, lastPage: p.lastPage, total: p.total });
    } catch (_) { setRows([]); } finally { setLoading(false); }
  }, [status, page]);

  useEffect(() => { load(); }, [load]);

  const decide = async (row, decision) => {
    let reason = null;
    if (decision === 'reject') {
      reason = window.prompt(`Reason for rejecting ${row.account?.display_name}'s ID? (shown to the member, optional)`, '');
      if (reason === null) return; // cancelled
    } else if (!window.confirm(`Approve ${row.account?.display_name}'s ID verification?`)) {
      return;
    }
    setBusyId(row.id);
    try { await adminAPI.kycDecide(row.id, { decision, reason: reason || undefined }); await load(); }
    catch (e) { alert(e.response?.data?.message || 'Failed.'); }
    finally { setBusyId(null); }
  };

  return (
    <>
      <Toolbar>
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          style={{ padding: '9px 12px', borderRadius: 8, border: '1px solid #d8d8e0', fontSize: 13.5 }}>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
        <button style={btn(false)} onClick={load}><FiRefreshCw /> Refresh</button>
      </Toolbar>
      <table style={tableStyle}>
        <thead><tr>
          <th style={thStyle}>Member</th><th style={thStyle}>ID number</th>
          <th style={thStyle}>Evidence</th>
          <th style={thStyle}>Submitted</th><th style={{ ...thStyle, textAlign: 'right' }}>Actions</th>
        </tr></thead>
        <tbody>
          {loading ? <EmptyRow colSpan={5} text="Loading…" />
            : rows.length === 0 ? <EmptyRow colSpan={5} text="Nothing pending." />
            : rows.map((r) => (
              <tr key={r.id}>
                <td style={tdStyle}>{r.account?.display_name || '—'} <span style={{ color: '#9a9aa3' }}>(currently L{r.account?.kyc_level ?? 0})</span></td>
                <td style={tdStyle}>{r.national_id || '—'}</td>
                <td style={tdStyle}>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <KycThumb url={r.id_photo_url} label="ID" />
                    <KycThumb url={r.selfie_url} label="Selfie" />
                  </div>
                  {r.status === 'rejected' && r.rejection_reason && (
                    <div style={{ fontSize: 11.5, color: '#B91C1C', marginTop: 4 }}>Reason: {r.rejection_reason}</div>
                  )}
                </td>
                <td style={tdStyle}>{fmtDate(r.created_at)}</td>
                <td style={{ ...tdStyle, textAlign: 'right' }}>
                  {r.status === 'pending' && (
                    <div style={{ display: 'inline-flex', gap: 6 }}>
                      <button style={btn(true)} disabled={busyId === r.id} onClick={() => decide(r, 'approve')}><FiCheck /> Approve</button>
                      <button style={btn(true, true)} disabled={busyId === r.id} onClick={() => decide(r, 'reject')}><FiX /> Reject</button>
                    </div>
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

// A KYC decision needs an actual photo to look at, not a raw metadata
// string — thumbnail opens the full-size image in a new tab on click.
export function KycThumb({ url, label }) {
  if (!url) {
    return (
      <div style={{
        width: 48, height: 48, borderRadius: 6, background: '#F4F4F6',
        color: '#9a9aa3', display: 'grid', placeItems: 'center', fontSize: 9,
      }}>No {label}</div>
    );
  }
  return (
    <a href={url} target="_blank" rel="noreferrer" title={`View full-size ${label}`}>
      <img src={url} alt={label} style={{
        width: 48, height: 48, borderRadius: 6, objectFit: 'cover',
        border: '1px solid #d8d8e0', cursor: 'pointer',
      }} />
    </a>
  );
}

function InstitutionsTab() {
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({ page: 1, lastPage: 1, total: 0 });
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [verified, setVerified] = useState(0);
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminAPI.institutionsAdmin({ verified, page, per_page: 20 });
      const p = pageOf(res);
      setRows(p.items);
      setMeta({ page: p.page, lastPage: p.lastPage, total: p.total });
    } catch (_) { setRows([]); } finally { setLoading(false); }
  }, [verified, page]);

  useEffect(() => { load(); }, [load]);

  const decide = async (row, decision) => {
    if (decision === 'reject' && !window.confirm(`Reject and remove "${row.name}"?`)) return;
    setBusyId(row.id);
    try { await adminAPI.institutionVerify(row.id, { decision }); await load(); }
    catch (e) { alert(e.response?.data?.message || 'Failed.'); }
    finally { setBusyId(null); }
  };

  return (
    <>
      <Toolbar>
        <select value={verified} onChange={(e) => { setVerified(Number(e.target.value)); setPage(1); }}
          style={{ padding: '9px 12px', borderRadius: 8, border: '1px solid #d8d8e0', fontSize: 13.5 }}>
          <option value={0}>Pending review</option>
          <option value={1}>Verified</option>
        </select>
        <button style={btn(false)} onClick={load}><FiRefreshCw /> Refresh</button>
      </Toolbar>
      <table style={tableStyle}>
        <thead><tr>
          <th style={thStyle}>Name</th><th style={thStyle}>Type</th>
          <th style={thStyle}>District</th><th style={thStyle}>Submitted</th>
          <th style={{ ...thStyle, textAlign: 'right' }}>Actions</th>
        </tr></thead>
        <tbody>
          {loading ? <EmptyRow colSpan={5} text="Loading…" />
            : rows.length === 0 ? <EmptyRow colSpan={5} text="Nothing pending." />
            : rows.map((r) => (
              <tr key={r.id}>
                <td style={tdStyle}>{r.name} {r.short_name ? <span style={{ color: '#9a9aa3' }}>({r.short_name})</span> : null}</td>
                <td style={tdStyle}>{r.type}</td>
                <td style={tdStyle}>{r.district || '—'}</td>
                <td style={tdStyle}>{fmtDate(r.created_at)}</td>
                <td style={{ ...tdStyle, textAlign: 'right' }}>
                  {!r.verified && (
                    <div style={{ display: 'inline-flex', gap: 6 }}>
                      <button style={btn(true)} disabled={busyId === r.id} onClick={() => decide(r, 'approve')}><FiCheck /> Approve</button>
                      <button style={btn(true, true)} disabled={busyId === r.id} onClick={() => decide(r, 'reject')}><FiX /> Reject</button>
                    </div>
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

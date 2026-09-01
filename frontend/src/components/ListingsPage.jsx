import React, { useEffect, useState, useCallback } from 'react';
import { adminAPI, pageOf, dataOf } from '../services/api';
import { FiRefreshCw, FiExternalLink, FiCheck, FiX, FiImage } from 'react-icons/fi';
import {
  fmtDate, tableStyle, thStyle, tdStyle, Toolbar, Pager, EmptyRow, btn,
  Badge, Drawer, SectionTitle, KeyVal,
} from './adminUi';

const TABS = [
  { id: 'sources', label: 'Sources' },
  { id: 'discovered', label: 'Discovered' },
  { id: 'claims', label: 'Claims' },
];

// Admin surface for the profile-claim-and-verify importer (see
// PROFILE_CLAIM_IMPORTER_PLAN.md). Discovery/sources are read-only here —
// there's no crawl-trigger endpoint yet, and no adapter to run regardless
// (both configured sources are currently 'unavailable'). Claims review is
// the one place an admin actually acts: reviewing a liveness capture is ONE
// of two required verification factors — approving it here never authorizes
// a claim by itself (the backend enforces that; this UI just reflects it).
export default function ListingsPage() {
  const [tab, setTab] = useState('sources');
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
      {tab === 'sources' && <SourcesTab />}
      {tab === 'discovered' && <DiscoveredTab />}
      {tab === 'claims' && <ClaimsTab />}
    </div>
  );
}

const SOURCE_STATUS_LABEL = {
  discovery_only: 'Discovery only',
  active: 'Active',
  paused_health: 'Paused (health)',
  unavailable: 'Unavailable',
};

function sourceBadgeValue(status) {
  if (status === 'active' || status === 'discovery_only') return 'active';
  if (status === 'unavailable') return 'suspended';
  return 'pending';
}

function SourcesTab() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try { setRows(dataOf(await adminAPI.listingSources()) || []); }
    catch (_) { setRows([]); } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <>
      <Toolbar>
        <button style={btn(false)} onClick={load}><FiRefreshCw /> Refresh</button>
      </Toolbar>
      {loading ? (
        <div style={{ padding: 24, color: '#9a9aa3', fontSize: 13.5 }}>Loading…</div>
      ) : (
        <div style={{ display: 'grid', gap: 12 }}>
          {rows.map((s) => (
            <div key={s.source} style={{
              background: '#fff', border: '1px solid #ececf1', borderRadius: 10, padding: 16,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <div style={{ fontWeight: 800, fontSize: 14.5 }}>{s.label}</div>
                <Badge value={sourceBadgeValue(s.status)}>{SOURCE_STATUS_LABEL[s.status] || s.status}</Badge>
                <span style={{ color: '#9a9aa3', fontSize: 12.5 }}>{s.mechanism}</span>
                <a href={s.base_url} target="_blank" rel="noreferrer" style={{
                  marginLeft: 'auto', fontSize: 12.5, color: '#7C3AED', display: 'inline-flex',
                  alignItems: 'center', gap: 4, textDecoration: 'none',
                }}>{s.base_url} <FiExternalLink /></a>
              </div>
              <div style={{ display: 'flex', gap: 24, marginTop: 10, fontSize: 12.5, color: '#6b6b76' }}>
                <span><strong>{s.total_discovered}</strong> discovered</span>
                <span>Last crawl: {s.last_crawl ? fmtDate(s.last_crawl.started_at) : 'never'}</span>
              </div>
              {s.notes && (
                <div style={{
                  marginTop: 10, fontSize: 12.5, color: '#78716c', background: '#fafafa',
                  border: '1px solid #f0f0f0', borderRadius: 8, padding: '8px 10px', lineHeight: 1.5,
                }}>{s.notes}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function DiscoveredTab() {
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({ page: 1, lastPage: 1, total: 0 });
  const [loading, setLoading] = useState(true);
  const [claimStatus, setClaimStatus] = useState('');
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminAPI.listingsDiscovered({
        claim_status: claimStatus || undefined, page, per_page: 20,
      });
      const p = pageOf(res);
      setRows(p.items);
      setMeta({ page: p.page, lastPage: p.lastPage, total: p.total });
    } catch (_) { setRows([]); } finally { setLoading(false); }
  }, [claimStatus, page]);

  useEffect(() => { load(); }, [load]);

  return (
    <>
      <Toolbar>
        <select value={claimStatus} onChange={(e) => { setClaimStatus(e.target.value); setPage(1); }}
          style={{ padding: '9px 12px', borderRadius: 8, border: '1px solid #d8d8e0', fontSize: 13.5 }}>
          <option value="">All statuses</option>
          <option value="discovered">Discovered</option>
          <option value="claim_requested">Claim requested</option>
          <option value="authorized">Authorized</option>
          <option value="published">Published</option>
          <option value="rejected">Rejected</option>
        </select>
        <button style={btn(false)} onClick={load}><FiRefreshCw /> Refresh</button>
      </Toolbar>
      <table style={tableStyle}>
        <thead><tr>
          <th style={thStyle}>Source</th><th style={thStyle}>Location</th>
          <th style={thStyle}>Status</th><th style={thStyle}>Discovered</th>
          <th style={thStyle}>Link</th>
        </tr></thead>
        <tbody>
          {loading ? <EmptyRow colSpan={5} text="Loading…" />
            : rows.length === 0 ? (
              <EmptyRow colSpan={5} text="No listings discovered yet — both configured sources are currently unavailable (see Sources tab)." />
            ) : rows.map((r) => (
              <tr key={r.id}>
                <td style={tdStyle}>{r.source}</td>
                <td style={tdStyle}>{r.location_text || '—'}</td>
                <td style={tdStyle}><Badge value={r.claim_status === 'published' ? 'active' : r.claim_status === 'rejected' ? 'suspended' : 'pending'}>{r.claim_status}</Badge></td>
                <td style={tdStyle}>{fmtDate(r.discovered_at)}</td>
                <td style={tdStyle}>
                  {r.source_url ? <a href={r.source_url} target="_blank" rel="noreferrer" style={{ color: '#7C3AED' }}><FiExternalLink /></a> : '—'}
                </td>
              </tr>
            ))}
        </tbody>
      </table>
      <Pager page={meta.page} lastPage={meta.lastPage} total={meta.total} onPage={setPage} />
    </>
  );
}

const CLAIM_BADGE = {
  authorized: 'active', published: 'active',
  rejected: 'suspended', removed: 'suspended',
};

function ClaimsTab() {
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({ page: 1, lastPage: 1, total: 0 });
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [reviewing, setReviewing] = useState(null); // claim row being reviewed
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminAPI.listingClaims({ status: status || undefined, page, per_page: 20 });
      const p = pageOf(res);
      setRows(p.items);
      setMeta({ page: p.page, lastPage: p.lastPage, total: p.total });
    } catch (_) { setRows([]); } finally { setLoading(false); }
  }, [status, page]);

  useEffect(() => { load(); }, [load]);

  const reviewLiveness = async (passed) => {
    if (!reviewing) return;
    setBusyId(reviewing.id);
    try {
      await adminAPI.listingReviewLiveness(reviewing.id, { passed });
      setReviewing(null);
      await load();
    } catch (e) { alert(e.response?.data?.message || 'Failed.'); }
    finally { setBusyId(null); }
  };

  const reject = async (row) => {
    const reason = window.prompt(`Reason for rejecting this claim?`, '');
    if (reason === null) return;
    setBusyId(row.id);
    try {
      await adminAPI.listingTransitionClaim(row.id, { status: 'rejected', reason });
      await load();
    } catch (e) { alert(e.response?.data?.message || 'Failed.'); }
    finally { setBusyId(null); }
  };

  const hasPassedEvent = (row, method) =>
    (row.verification_events || []).some((e) => e.method === method && e.result === 'passed');

  return (
    <>
      <Toolbar>
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          style={{ padding: '9px 12px', borderRadius: 8, border: '1px solid #d8d8e0', fontSize: 13.5 }}>
          <option value="">All statuses</option>
          <option value="claim_requested">Claim requested</option>
          <option value="verification_pending">Verification pending</option>
          <option value="authorized">Authorized</option>
          <option value="rejected">Rejected</option>
        </select>
        <button style={btn(false)} onClick={load}><FiRefreshCw /> Refresh</button>
      </Toolbar>
      <table style={tableStyle}>
        <thead><tr>
          <th style={thStyle}>Listing</th><th style={thStyle}>Status</th>
          <th style={thStyle}>OTP</th><th style={thStyle}>Liveness</th>
          <th style={thStyle}>Started</th><th style={{ ...thStyle, textAlign: 'right' }}>Actions</th>
        </tr></thead>
        <tbody>
          {loading ? <EmptyRow colSpan={6} text="Loading…" />
            : rows.length === 0 ? <EmptyRow colSpan={6} text="No claims yet." />
            : rows.map((r) => (
              <tr key={r.id}>
                <td style={tdStyle}>{r.listing?.source || '—'} · {r.listing?.location_text || '—'}</td>
                <td style={tdStyle}><Badge value={CLAIM_BADGE[r.status] || 'pending'}>{r.status}</Badge></td>
                <td style={tdStyle}>{hasPassedEvent(r, 'otp') ? <FiCheck color="#059669" /> : '—'}</td>
                <td style={tdStyle}>
                  {hasPassedEvent(r, 'liveness_match') ? <FiCheck color="#059669" />
                    : r.liveness_capture_path ? <span style={{ color: '#C2410C', fontWeight: 700 }}>Pending review</span>
                    : '—'}
                </td>
                <td style={tdStyle}>{fmtDate(r.created_at)}</td>
                <td style={{ ...tdStyle, textAlign: 'right' }}>
                  <div style={{ display: 'inline-flex', gap: 6 }}>
                    {r.liveness_capture_path && !hasPassedEvent(r, 'liveness_match') && (
                      <button style={btn(false)} onClick={() => setReviewing(r)}><FiImage /> Review liveness</button>
                    )}
                    {!['rejected', 'removed', 'published'].includes(r.status) && (
                      <button style={btn(true, true)} disabled={busyId === r.id} onClick={() => reject(r)}><FiX /> Reject</button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
        </tbody>
      </table>
      <Pager page={meta.page} lastPage={meta.lastPage} total={meta.total} onPage={setPage} />

      <Drawer open={!!reviewing} onClose={() => setReviewing(null)} title="Review liveness capture">
        {reviewing && (
          <>
            <SectionTitle>Claim</SectionTitle>
            <KeyVal k="Listing" v={`${reviewing.listing?.source || '—'} · ${reviewing.listing?.location_text || '—'}`} />
            <KeyVal k="Started" v={fmtDate(reviewing.created_at)} />
            <KeyVal k="OTP factor" v={hasPassedEvent(reviewing, 'otp') ? 'Passed' : 'Not yet passed'} />

            <SectionTitle>Liveness capture</SectionTitle>
            <p style={{ fontSize: 12.5, color: '#8a8a93', marginTop: -4, marginBottom: 10, lineHeight: 1.5 }}>
              Compare this capture against the claimed listing's photos on the source site. This is one of
              two required factors — approving it does not authorize the claim by itself unless the OTP
              factor has also passed.
            </p>
            {reviewing.liveness_capture_path ? (
              <img src={reviewing.liveness_capture_path} alt="Liveness capture" style={{
                width: '100%', borderRadius: 10, border: '1px solid #ececf1', maxHeight: 360, objectFit: 'contain',
                background: '#fafafa',
              }} />
            ) : <div style={{ color: '#9a9aa3', fontSize: 13 }}>No capture on file.</div>}

            <div style={{ display: 'flex', gap: 8, marginTop: 18 }}>
              <button style={btn(true)} disabled={busyId === reviewing.id} onClick={() => reviewLiveness(true)}>
                <FiCheck /> Matches — approve
              </button>
              <button style={btn(true, true)} disabled={busyId === reviewing.id} onClick={() => reviewLiveness(false)}>
                <FiX /> Doesn't match — reject
              </button>
            </div>
          </>
        )}
      </Drawer>
    </>
  );
}

import React, { useEffect, useState, useCallback } from 'react';
import { adminAPI, pageOf, dataOf } from '../services/api';
import { FiCheck, FiX, FiRefreshCw, FiGift } from 'react-icons/fi';
import {
  Badge, fmtDate, tableStyle, thStyle, tdStyle, Toolbar, Pager, EmptyRow, btn,
} from './adminUi';

const STATUSES = ['review', 'requested', 'processing', 'paid', 'failed', 'reversed', ''];
const TABS = [
  { id: 'withdrawals', label: 'Withdrawals' },
  { id: 'gifts', label: 'Gift transactions' },
  { id: 'catalog', label: 'Gift catalog' },
];

export default function WalletPage() {
  const [tab, setTab] = useState('withdrawals');
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
      {tab === 'withdrawals' && <WithdrawalsTab />}
      {tab === 'gifts' && <GiftsTab />}
      {tab === 'catalog' && <CatalogTab />}
    </div>
  );
}

function WithdrawalsTab() {
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({ page: 1, lastPage: 1, total: 0 });
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [status, setStatus] = useState('review');
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminAPI.withdrawals({ status: status || undefined, page, per_page: 20 });
      const p = pageOf(res);
      setRows(p.items);
      setMeta({ page: p.page, lastPage: p.lastPage, total: p.total });
    } catch (_) { setRows([]); } finally { setLoading(false); }
  }, [status, page]);

  useEffect(() => { load(); }, [load]);

  const decide = async (w, decision) => {
    const note = decision === 'reject' ? window.prompt('Reason for rejecting (refunds the member):') : '';
    if (decision === 'reject' && note === null) return;
    if (!window.confirm(`${decision === 'approve' ? 'Approve' : 'Reject'} this ${w.net_ugx.toLocaleString()} UGX withdrawal for ${w.account?.display_name}?`)) return;
    setBusyId(w.id);
    try {
      await adminAPI.withdrawalRelease(w.id, { decision, note });
      await load();
    } catch (e) {
      alert(e.response?.data?.message || 'Action failed.');
    } finally { setBusyId(null); }
  };

  return (
    <>
      <Toolbar>
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          style={{ padding: '9px 12px', borderRadius: 8, border: '1px solid #d8d8e0', fontSize: 13.5 }}>
          {STATUSES.map((s) => <option key={s} value={s}>{s ? s[0].toUpperCase() + s.slice(1) : 'All statuses'}</option>)}
        </select>
        <button style={btn(false)} onClick={load}><FiRefreshCw /> Refresh</button>
      </Toolbar>
      <table style={tableStyle}>
        <thead><tr>
          <th style={thStyle}>Member</th><th style={thStyle}>Amount</th>
          <th style={thStyle}>Network</th><th style={thStyle}>Status</th>
          <th style={thStyle}>Requested</th><th style={{ ...thStyle, textAlign: 'right' }}>Actions</th>
        </tr></thead>
        <tbody>
          {loading ? <EmptyRow colSpan={6} text="Loading…" />
            : rows.length === 0 ? <EmptyRow colSpan={6} text="No withdrawals here." />
            : rows.map((w) => (
              <tr key={w.id}>
                <td style={tdStyle}>{w.account?.display_name || '—'} <span style={{ color: '#9a9aa3' }}>@{w.account?.handle}</span></td>
                <td style={tdStyle}>{w.net_ugx.toLocaleString()} UGX {w.fee_ugx ? <span style={{ color: '#9a9aa3', fontSize: 11 }}> (fee {w.fee_ugx.toLocaleString()})</span> : null}</td>
                <td style={tdStyle}>{w.network} — {w.phone}</td>
                <td style={tdStyle}><Badge value={w.status} /></td>
                <td style={tdStyle}>{fmtDate(w.requested_at)}</td>
                <td style={{ ...tdStyle, textAlign: 'right' }}>
                  {w.status === 'review' ? (
                    <div style={{ display: 'inline-flex', gap: 6 }}>
                      <button style={btn(true)} disabled={busyId === w.id} onClick={() => decide(w, 'approve')}><FiCheck /> Approve</button>
                      <button style={btn(true, true)} disabled={busyId === w.id} onClick={() => decide(w, 'reject')}><FiX /> Reject</button>
                    </div>
                  ) : <span style={{ color: '#9a9aa3', fontSize: 12 }}>{w.failure_reason || '—'}</span>}
                </td>
              </tr>
            ))}
        </tbody>
      </table>
      <Pager page={meta.page} lastPage={meta.lastPage} total={meta.total} onPage={setPage} />
    </>
  );
}

function GiftsTab() {
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({ page: 1, lastPage: 1, total: 0 });
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminAPI.gifts({ page, per_page: 20 });
      const p = pageOf(res);
      setRows(p.items);
      setMeta({ page: p.page, lastPage: p.lastPage, total: p.total });
    } catch (_) { setRows([]); } finally { setLoading(false); }
  }, [page]);

  useEffect(() => { load(); }, [load]);

  return (
    <>
      <Toolbar><button style={btn(false)} onClick={load}><FiRefreshCw /> Refresh</button></Toolbar>
      <table style={tableStyle}>
        <thead><tr>
          <th style={thStyle}>Gift</th><th style={thStyle}>From</th><th style={thStyle}>To</th>
          <th style={thStyle}>Coins spent</th><th style={thStyle}>Net (recipient)</th><th style={thStyle}>Sent</th>
        </tr></thead>
        <tbody>
          {loading ? <EmptyRow colSpan={6} text="Loading…" />
            : rows.length === 0 ? <EmptyRow colSpan={6} text="No gifts sent yet." />
            : rows.map((g) => (
              <tr key={g.id}>
                <td style={tdStyle}>{g.gift_name}</td>
                <td style={tdStyle}>{g.sender?.display_name || '—'}</td>
                <td style={tdStyle}>{g.recipient?.display_name || '—'}</td>
                <td style={tdStyle}>{g.coins_spent}</td>
                <td style={tdStyle}>{g.net_ugx.toLocaleString()} UGX</td>
                <td style={tdStyle}>{fmtDate(g.created_at)}</td>
              </tr>
            ))}
        </tbody>
      </table>
      <Pager page={meta.page} lastPage={meta.lastPage} total={meta.total} onPage={setPage} />
    </>
  );
}

function CatalogTab() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try { setRows(dataOf(await adminAPI.giftCatalog()) || []); }
    catch (_) { setRows([]); } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggleActive = async (g) => {
    setBusyId(g.id);
    try { await adminAPI.giftCatalogUpdate(g.id, { active: !g.active }); await load(); }
    catch (e) { alert(e.response?.data?.message || 'Failed.'); }
    finally { setBusyId(null); }
  };

  const editPrice = async (g) => {
    const price = window.prompt(`Price in coins for ${g.name}:`, g.price_coins);
    if (price === null || isNaN(Number(price))) return;
    setBusyId(g.id);
    try { await adminAPI.giftCatalogUpdate(g.id, { price_coins: Number(price) }); await load(); }
    catch (e) { alert(e.response?.data?.message || 'Failed.'); }
    finally { setBusyId(null); }
  };

  return (
    <>
      <Toolbar><button style={btn(false)} onClick={load}><FiRefreshCw /> Refresh</button></Toolbar>
      <table style={tableStyle}>
        <thead><tr>
          <th style={thStyle}>Gift</th><th style={thStyle}>Price (coins)</th>
          <th style={thStyle}>Cash value</th><th style={thStyle}>Active</th><th style={{ ...thStyle, textAlign: 'right' }}>Actions</th>
        </tr></thead>
        <tbody>
          {loading ? <EmptyRow colSpan={5} text="Loading…" />
            : rows.map((g) => (
              <tr key={g.id}>
                <td style={tdStyle}><FiGift style={{ marginRight: 6 }} />{g.icon} {g.name}</td>
                <td style={tdStyle}>{g.price_coins}</td>
                <td style={tdStyle}>{g.cash_value_ugx.toLocaleString()} UGX</td>
                <td style={tdStyle}>{g.active ? <Badge value="active">Active</Badge> : <Badge value="closed">Retired</Badge>}</td>
                <td style={{ ...tdStyle, textAlign: 'right' }}>
                  <div style={{ display: 'inline-flex', gap: 6 }}>
                    <button style={btn(false)} disabled={busyId === g.id} onClick={() => editPrice(g)}>Edit price</button>
                    <button style={btn(false)} disabled={busyId === g.id} onClick={() => toggleActive(g)}>
                      {g.active ? 'Retire' : 'Reactivate'}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
        </tbody>
      </table>
    </>
  );
}

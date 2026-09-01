import React, { useEffect, useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { adminAPI, referenceAPI, dataOf, pageOf } from '../services/api';
import {
  FiSearch, FiStar, FiSlash, FiRotateCcw, FiRefreshCw, FiUserPlus, FiEdit2,
  FiHeart, FiBriefcase, FiCamera, FiMapPin, FiEye, FiMoon, FiCheckCircle, FiX,
} from 'react-icons/fi';
import {
  Badge, Avatar, AppBadge, fmtDate, tableStyle, thStyle, tdStyle,
  Toolbar, Pager, EmptyRow, btn, ActionMenu, Lightbox, ToggleSwitch,
} from './adminUi';
import AccountDetailDrawer from './AccountDetailDrawer';
import AccountFormModal from './AccountFormModal';
import AccountGalleryModal from './AccountGalleryModal';
import { useAppScope } from '../contexts/AppScopeContext';

const STATUSES = ['', 'active', 'inactive', 'suspended', 'closed'];
const GENDER_LABEL = { male: 'Man', female: 'Woman' };
const GENDERS = ['', 'male', 'female'];

const filterSelectStyle = { padding: '9px 12px', borderRadius: 8, border: '1px solid #d8d8e0', fontSize: 13.5 };

function truncate(text, max = 64) {
  if (!text) return '';
  return text.length > max ? `${text.slice(0, max).trimEnd()}…` : text;
}

// Every filter/pagination key this page keeps in sync with the URL. Centralized
// so the two things that must agree on names — the reader below and the
// writer inside load() — can't quietly drift apart.
const URL_PARAM = { q: 'q', status: 'status', gender: 'gender', districtId: 'district_id', page: 'page' };

export default function AccountsPage() {
  const { appId } = useAppScope();
  const [searchParams, setSearchParams] = useSearchParams();
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({ page: 1, lastPage: 1, total: 0 });
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  // Seeded from the URL on first render (not on every navigation — a normal
  // useState lazy initializer only ever runs once) so a refresh, a bookmark,
  // or a shared link reproduces exactly this view instead of resetting to
  // page 1 with no filters.
  const [q, setQ] = useState(() => searchParams.get(URL_PARAM.q) || '');
  const [status, setStatus] = useState(() => searchParams.get(URL_PARAM.status) || '');
  const [gender, setGender] = useState(() => searchParams.get(URL_PARAM.gender) || '');
  const [districtId, setDistrictId] = useState(() => searchParams.get(URL_PARAM.districtId) || '');
  const [districts, setDistricts] = useState([]);
  const [page, setPage] = useState(() => {
    const p = parseInt(searchParams.get(URL_PARAM.page), 10);
    return Number.isFinite(p) && p > 0 ? p : 1;
  });
  const [openId, setOpenId] = useState(null);
  const [creating, setCreating] = useState(false);
  const [editingAccount, setEditingAccount] = useState(null); // full detail object, or null
  const [editLoadingId, setEditLoadingId] = useState(null);
  const [galleryId, setGalleryId] = useState(null);
  const [lightboxSrc, setLightboxSrc] = useState(null);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);

  const load = useCallback(async () => {
    // Mirror the current filters/page into the URL on every load, not just
    // on explicit changes — one place, always right, instead of a separate
    // setSearchParams call bolted onto every setter (search box, 3 selects,
    // Pager). app_id is deliberately left out: it's global admin-console
    // scope already persisted via AppScopeContext's localStorage, not
    // per-page state, so it shouldn't get a second, URL-based source of truth.
    const next = new URLSearchParams();
    if (q) next.set(URL_PARAM.q, q);
    if (status) next.set(URL_PARAM.status, status);
    if (gender) next.set(URL_PARAM.gender, gender);
    if (districtId) next.set(URL_PARAM.districtId, districtId);
    if (page > 1) next.set(URL_PARAM.page, String(page));
    setSearchParams(next, { replace: true });

    setLoading(true);
    try {
      const res = await adminAPI.accounts({
        q, status, gender: gender || undefined, district_id: districtId || undefined,
        app_id: appId || undefined, page, per_page: 20,
      });
      const p = pageOf(res);
      setRows(p.items);
      setMeta({ page: p.page, lastPage: p.lastPage, total: p.total });
    } catch (_) {
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [q, status, gender, districtId, appId, page, setSearchParams]);

  useEffect(() => { load(); }, [load]);
  // A fresh page/filter result invalidates any selection made on the
  // previous rows — stale off-screen ids should never survive into a bulk
  // action on what's now showing.
  useEffect(() => { setSelectedIds(new Set()); }, [rows]);

  const toggleOne = (id) => setSelectedIds((prev) => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });
  const allOnPageSelected = rows.length > 0 && rows.every((r) => selectedIds.has(r.id));
  const toggleAllOnPage = () => setSelectedIds((prev) => {
    if (allOnPageSelected) return new Set();
    return new Set(rows.map((r) => r.id));
  });

  const BULK_VERBS = { active: 'activate', inactive: 'deactivate', suspended: 'suspend' };
  const bulkSetStatus = async (newStatus) => {
    const ids = [...selectedIds];
    if (!ids.length) return;
    const verb = BULK_VERBS[newStatus] || 'update';
    if (newStatus === 'suspended' &&
        !window.confirm(`Suspend ${ids.length} account(s)? Each one gets notified.`)) return;
    setBulkBusy(true);
    try {
      const res = await adminAPI.accountBulkStatus({ account_ids: ids, status: newStatus });
      await load();
      const msg = dataOf(res);
      if (msg?.skipped) alert(`${verb[0].toUpperCase() + verb.slice(1)}d ${msg.updated}, skipped ${msg.skipped} (admins or already gone).`);
    } catch (e) {
      alert(e.response?.data?.message || 'Bulk action failed.');
    } finally {
      setBulkBusy(false);
    }
  };

  useEffect(() => {
    referenceAPI.locations({ level: 'district' }).then((res) => {
      setDistricts([...(dataOf(res) || [])].sort((a, b) => a.name.localeCompare(b.name)));
    }).catch(() => setDistricts([]));
  }, []);

  const STATUS_VERBS = { active: 'reinstate', inactive: 'mark inactive', suspended: 'suspend', closed: 'close' };
  const setStatusFor = async (acct, newStatus) => {
    // Activating/deactivating is a light, frequent, reversible action — no
    // popup. Suspend/close are heavier (policy action, user gets emailed)
    // so those still confirm.
    const verb = STATUS_VERBS[newStatus] || 'update';
    const needsConfirm = newStatus === 'suspended' || newStatus === 'closed';
    if (needsConfirm && !window.confirm(`Are you sure you want to ${verb} ${acct.display_name || acct.handle}?`)) return;
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
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} style={filterSelectStyle}>
          {STATUSES.map((s) => <option key={s} value={s}>{s ? s[0].toUpperCase() + s.slice(1) : 'All statuses'}</option>)}
        </select>
        <select value={gender} onChange={(e) => { setGender(e.target.value); setPage(1); }} style={filterSelectStyle}>
          {GENDERS.map((g) => <option key={g} value={g}>{g ? GENDER_LABEL[g] : 'All genders'}</option>)}
        </select>
        <select value={districtId} onChange={(e) => { setDistrictId(e.target.value); setPage(1); }} style={{ ...filterSelectStyle, maxWidth: 170 }}>
          <option value="">All districts</option>
          {districts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        <button style={btn(false)} onClick={load}><FiRefreshCw /> Refresh</button>
        <button style={btn(true)} onClick={() => setCreating(true)}><FiUserPlus /> New account</button>
      </Toolbar>

      {selectedIds.size > 0 && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px', marginBottom: 10,
          background: '#F5F3FF', border: '1px solid #DDD6FE', borderRadius: 10,
        }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: '#5B21B6' }}>
            <FiCheckCircle style={{ verticalAlign: -2, marginRight: 5 }} />
            {selectedIds.size} selected
          </span>
          <div style={{ display: 'flex', gap: 8, marginLeft: 'auto' }}>
            <button style={btn(false)} disabled={bulkBusy} onClick={() => bulkSetStatus('active')}>Activate</button>
            <button style={btn(false)} disabled={bulkBusy} onClick={() => bulkSetStatus('inactive')}>Deactivate</button>
            <button style={btn(false, true)} disabled={bulkBusy} onClick={() => bulkSetStatus('suspended')}>Suspend</button>
            <button style={{ ...btn(false), padding: '7px 9px' }} disabled={bulkBusy}
              onClick={() => setSelectedIds(new Set())} title="Clear selection"><FiX /></button>
          </div>
        </div>
      )}

      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={{ ...thStyle, width: 36 }}>
              <input type="checkbox" checked={allOnPageSelected} onChange={toggleAllOnPage} />
            </th>
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
            <EmptyRow colSpan={10} text="Loading…" />
          ) : rows.length === 0 ? (
            <EmptyRow colSpan={10} text="No accounts found." />
          ) : rows.map((u) => {
            const dp = u.dating_profile_summary;
            const modes = u.modes_enabled || {};
            return (
              <tr key={u.id} style={{ cursor: 'pointer' }} onClick={() => setOpenId(u.id)}>
                <td style={tdStyle} onClick={(e) => e.stopPropagation()}>
                  <input type="checkbox" checked={selectedIds.has(u.id)} onChange={() => toggleOne(u.id)} />
                </td>
                <td style={tdStyle}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div
                      onClick={(e) => { if (u.avatar) { e.stopPropagation(); setLightboxSrc(u.avatar); } }}
                      style={{ cursor: u.avatar ? 'zoom-in' : 'default' }}
                      title={u.avatar ? 'Click to view full photo' : ''}
                    >
                      <Avatar name={u.display_name} avatar={u.avatar} />
                    </div>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontWeight: 700 }}>{u.display_name || '—'}</span>
                        <AppBadge appId={u.app_id} />
                      </div>
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
                  <span
                    onClick={(e) => { e.stopPropagation(); setGalleryId(u.id); }}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12.5, cursor: 'pointer',
                      color: u.photo_count ? '#27272a' : '#c4c4cc', textDecoration: 'underline',
                      textDecorationColor: 'transparent',
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.textDecorationColor = '#d8d8e0'; }}
                    onMouseLeave={(e) => { e.currentTarget.style.textDecorationColor = 'transparent'; }}
                    title="View photo gallery"
                  >
                    <FiCamera size={12} /> {u.photo_count || 0}
                  </span>
                </td>
                <td style={tdStyle}><Badge value={u.account_status} /></td>
                <td style={tdStyle}>{u.is_premium ? <Badge value="premium">Premium</Badge> : <span style={{ color: '#9a9aa3' }}>Free</span>}</td>
                <td style={tdStyle}>{fmtDate(u.created_at)}</td>
                <td style={{ ...tdStyle, textAlign: 'right' }} onClick={(e) => e.stopPropagation()}>
                  <div style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}>
                    <ToggleSwitch
                      checked={u.account_status === 'active'}
                      disabled={busyId === u.id}
                      title={u.account_status === 'active' ? 'Active — click to deactivate' : 'Click to activate'}
                      onChange={(next) => setStatusFor(u, next ? 'active' : 'inactive')}
                    />
                    <button
                      type="button" onClick={() => openEdit(u)} title="Edit"
                      disabled={editLoadingId === u.id}
                      className="btn-icon"
                      style={{
                        width: 30, height: 30, display: 'grid', placeItems: 'center', borderRadius: 8,
                        border: '1px solid #d8d8e0', background: '#fff', cursor: 'pointer', color: '#52525b',
                      }}
                    ><FiEdit2 size={13} /></button>
                    <ActionMenu items={[
                      { label: 'View detail', icon: FiEye, onClick: () => setOpenId(u.id) },
                      {
                        label: u.is_premium ? 'Revoke premium' : 'Grant premium',
                        icon: FiStar, onClick: () => togglePremium(u),
                      },
                      u.account_status !== 'active' &&
                        { label: 'Reinstate (active)', icon: FiRotateCcw, onClick: () => setStatusFor(u, 'active') },
                      u.account_status !== 'inactive' &&
                        { label: 'Mark inactive', icon: FiMoon, onClick: () => setStatusFor(u, 'inactive') },
                      u.account_status !== 'suspended' &&
                        { label: 'Suspend', icon: FiSlash, danger: true, onClick: () => setStatusFor(u, 'suspended') },
                    ]} />
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <Pager page={meta.page} lastPage={meta.lastPage} total={meta.total} onPage={setPage} />

      <AccountDetailDrawer accountId={openId} onClose={() => setOpenId(null)} onChanged={load} />
      <AccountFormModal open={creating} onClose={() => setCreating(false)} onSaved={load} />
      <AccountFormModal
        open={!!editingAccount}
        account={editingAccount}
        onClose={() => setEditingAccount(null)}
        onSaved={load}
      />
      <AccountGalleryModal accountId={galleryId} onClose={() => setGalleryId(null)} />
      <Lightbox images={lightboxSrc ? [lightboxSrc] : []} index={lightboxSrc ? 0 : null} onClose={() => setLightboxSrc(null)} />
    </div>
  );
}

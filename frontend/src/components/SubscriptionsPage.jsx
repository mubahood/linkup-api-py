import React, { useEffect, useState, useCallback } from 'react';
import { adminAPI, pageOf, dataOf } from '../services/api';
import { useAppScope } from '../contexts/AppScopeContext';
import { FiRefreshCw, FiPlus, FiSave, FiUsers, FiDollarSign } from 'react-icons/fi';
import {
  Badge, fmtDate, tableStyle, thStyle, tdStyle, Toolbar, Pager, EmptyRow, btn,
  AppBadge, Modal, FormRow, FormGrid, inputStyle,
} from './adminUi';

const TABS = [
  { id: 'plans', label: 'Plans' },
  { id: 'subscribers', label: 'Subscribers' },
];

// limits JSON shape (backend/domains/subscriptions/models.py) — numeric
// fields use -1 for unlimited, the rest are booleans.
const NUMERIC_LIMIT_FIELDS = [
  ['swipes_per_day', 'Swipes / day'],
  ['standouts_per_day', 'Standouts / day'],
  ['chats_per_day', 'Chats / day'],
  ['rewinds_per_day', 'Rewinds / day'],
  ['boosts_per_month', 'Boosts / month'],
  ['streak_freeze_per_month', 'Streak freezes / month'],
];
const BOOLEAN_LIMIT_FIELDS = [
  ['can_view_likers', 'Can view likers'],
  ['can_view_profile_viewers', 'Can view profile viewers'],
  ['can_reveal_contact', 'Can reveal contact'],
  ['priority_deck', 'Priority deck'],
  ['read_receipts', 'Read receipts'],
  ['advanced_filters', 'Advanced filters'],
];

const STATUSES = ['', 'active', 'expired', 'pending', 'cancelled'];

function emptyLimits() {
  const l = {};
  NUMERIC_LIMIT_FIELDS.forEach(([k]) => { l[k] = 0; });
  BOOLEAN_LIMIT_FIELDS.forEach(([k]) => { l[k] = false; });
  return l;
}

export default function SubscriptionsPage() {
  const [tab, setTab] = useState('plans');
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
      {tab === 'plans' ? <PlansTab /> : <SubscribersTab />}
    </div>
  );
}

function PlansTab() {
  const { appId } = useAppScope();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try { setRows(dataOf(await adminAPI.subscriptionPlans({ app_id: appId || undefined })) || []); }
    catch (_) { setRows([]); } finally { setLoading(false); }
  }, [appId]);

  useEffect(() => { load(); }, [load]);

  return (
    <>
      <Toolbar>
        <button style={btn(false)} onClick={load}><FiRefreshCw /> Refresh</button>
        <button style={btn(true)} onClick={() => setShowCreate(true)}><FiPlus /> New plan</button>
      </Toolbar>
      {loading ? (
        <div style={{ padding: '32px 14px', textAlign: 'center', color: '#9a9aa3' }}>Loading…</div>
      ) : rows.length === 0 ? (
        <div style={{ padding: '32px 14px', textAlign: 'center', color: '#9a9aa3' }}>No plans yet.</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 14 }}>
          {rows.map((p) => <PlanCard key={p.id} plan={p} onSaved={load} />)}
        </div>
      )}
      <CreatePlanModal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onCreated={() => { setShowCreate(false); load(); }}
        defaultAppId={appId}
      />
    </>
  );
}

function PlanCard({ plan, onSaved }) {
  const [edit, setEdit] = useState(() => ({
    name: plan.name, tagline: plan.tagline || '', price_ugx: plan.price_ugx,
    duration_days: plan.duration_days, sort_order: plan.sort_order,
    badge_color: plan.badge_color || '', active: plan.active,
    discount_price_ugx: plan.discount_price_ugx ?? '',
    discount_ends_at: plan.discount_ends_at ? plan.discount_ends_at.slice(0, 16) : '',
    limits: { ...emptyLimits(), ...(plan.limits || {}) },
  }));
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState(false);

  const setField = (field, val) => setEdit((e) => ({ ...e, [field]: val }));
  const setLimit = (key, val) => setEdit((e) => ({ ...e, limits: { ...e.limits, [key]: val } }));

  const save = async () => {
    setBusy(true);
    try {
      await adminAPI.subscriptionPlanUpdate(plan.id, {
        name: edit.name,
        tagline: edit.tagline || null,
        price_ugx: Number(edit.price_ugx),
        duration_days: Number(edit.duration_days),
        sort_order: Number(edit.sort_order),
        active: !!edit.active,
        badge_color: edit.badge_color || null,
        discount_price_ugx: edit.discount_price_ugx === '' ? null : Number(edit.discount_price_ugx),
        discount_ends_at: edit.discount_ends_at || null,
        limits: edit.limits,
      });
      await onSaved();
    } catch (e) {
      alert(e.response?.data?.message || 'Save failed.');
    } finally { setBusy(false); }
  };

  return (
    <div style={{ background: '#fff', border: '1px solid #ececf1', borderRadius: 10, padding: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <AppBadge appId={plan.app_id} />
          <span style={{ fontWeight: 800, fontSize: 15 }}>{plan.name}</span>
        </div>
        <Badge value={plan.active ? 'active' : 'closed'}>{plan.active ? 'Active' : 'Inactive'}</Badge>
      </div>
      <div style={{ fontSize: 11.5, color: '#9a9aa3', marginBottom: 10 }}>
        code: <code>{plan.code}</code> · {plan.duration_days === 0 ? 'no expiry' : `${plan.duration_days}d`}
      </div>
      <div style={{ fontSize: 18, fontWeight: 800, marginBottom: 10 }}>
        {plan.discount_active ? (
          <>
            <span style={{ textDecoration: 'line-through', color: '#9a9aa3', fontWeight: 600, fontSize: 14, marginRight: 6 }}>
              {plan.price_ugx.toLocaleString()} UGX
            </span>
            {plan.effective_price_ugx.toLocaleString()} UGX
          </>
        ) : `${plan.price_ugx.toLocaleString()} UGX`}
      </div>

      <Field label="Name" value={edit.name} onChange={(v) => setField('name', v)} />
      <Field label="Tagline" value={edit.tagline} onChange={(v) => setField('tagline', v)} />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <Field label="Price (UGX)" type="number" value={edit.price_ugx} onChange={(v) => setField('price_ugx', v)} />
        <Field label="Duration (days)" type="number" value={edit.duration_days} onChange={(v) => setField('duration_days', v)} />
        <Field label="Sort order" type="number" value={edit.sort_order} onChange={(v) => setField('sort_order', v)} />
        <Field label="Badge color" value={edit.badge_color} placeholder="#7C3AED" onChange={(v) => setField('badge_color', v)} />
        <Field label="Discount price (UGX)" type="number" value={edit.discount_price_ugx} placeholder="none" onChange={(v) => setField('discount_price_ugx', v)} />
        <Field label="Discount ends" type="datetime-local" value={edit.discount_ends_at} onChange={(v) => setField('discount_ends_at', v)} />
      </div>
      <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, fontWeight: 700, color: '#52525b', margin: '8px 0 4px', cursor: 'pointer' }}>
        <input type="checkbox" checked={!!edit.active} onChange={(e) => setField('active', e.target.checked)} />
        Active (visible to members)
      </label>

      <button onClick={() => setExpanded((v) => !v)} style={{
        background: 'none', border: 'none', color: '#7C3AED', fontWeight: 700, fontSize: 12.5,
        cursor: 'pointer', padding: '8px 0', textAlign: 'left', width: '100%',
      }}>{expanded ? 'Hide limits ▲' : 'Edit limits ▼'}</button>

      {expanded && (
        <div style={{ background: '#fafafb', border: '1px solid #ececf1', borderRadius: 8, padding: 12, marginBottom: 10 }}>
          <div style={{ fontSize: 10.5, fontWeight: 800, textTransform: 'uppercase', color: '#8a8a93', marginBottom: 8 }}>
            Numeric limits (-1 = unlimited)
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
            {NUMERIC_LIMIT_FIELDS.map(([key, label]) => (
              <Field key={key} label={label} type="number" value={edit.limits[key]}
                onChange={(v) => setLimit(key, Number(v))} compact />
            ))}
          </div>
          <div style={{ fontSize: 10.5, fontWeight: 800, textTransform: 'uppercase', color: '#8a8a93', marginBottom: 8 }}>
            Feature flags
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
            {BOOLEAN_LIMIT_FIELDS.map(([key, label]) => (
              <label key={key} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.5, cursor: 'pointer' }}>
                <input type="checkbox" checked={!!edit.limits[key]} onChange={(e) => setLimit(key, e.target.checked)} />
                {label}
              </label>
            ))}
          </div>
        </div>
      )}

      <button style={btn(true)} disabled={busy} onClick={save}><FiSave /> Save</button>
    </div>
  );
}

function Field({ label, value, onChange, type = 'text', placeholder, compact }) {
  return (
    <label style={{ display: 'block', marginBottom: compact ? 0 : 10 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: '#6b6b76', marginBottom: 3 }}>{label}</div>
      <input type={type} value={value ?? ''} placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        style={{ width: '100%', padding: '7px 9px', borderRadius: 6, border: '1px solid #d8d8e0',
          fontSize: 13, fontFamily: 'inherit', boxSizing: 'border-box' }} />
    </label>
  );
}

function CreatePlanModal({ open, onClose, onCreated, defaultAppId }) {
  const initial = () => ({
    app_id: defaultAppId || 'linkup', code: '', name: '', tagline: '',
    price_ugx: 0, duration_days: 0, sort_order: 0, badge_color: '',
    limits: emptyLimits(),
  });
  const [form, setForm] = useState(initial);
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (open) setForm(initial()); /* eslint-disable-next-line */ }, [open, defaultAppId]);

  const setField = (field, val) => setForm((f) => ({ ...f, [field]: val }));
  const setLimit = (key, val) => setForm((f) => ({ ...f, limits: { ...f.limits, [key]: val } }));

  const create = async () => {
    if (!form.code.trim() || !form.name.trim()) { alert('Code and name are required.'); return; }
    setBusy(true);
    try {
      await adminAPI.subscriptionPlanCreate({
        ...form,
        price_ugx: Number(form.price_ugx),
        duration_days: Number(form.duration_days),
        sort_order: Number(form.sort_order),
        badge_color: form.badge_color || null,
      });
      await onCreated();
    } catch (e) {
      alert(e.response?.data?.message || 'Create failed.');
    } finally { setBusy(false); }
  };

  return (
    <Modal open={open} onClose={onClose} title="New subscription plan" footer={
      <>
        <button style={btn(false)} onClick={onClose}>Cancel</button>
        <button style={btn(true)} disabled={busy} onClick={create}><FiPlus /> Create plan</button>
      </>
    }>
      <FormGrid cols={2}>
        <FormRow label="App" required>
          <select value={form.app_id} onChange={(e) => setField('app_id', e.target.value)} style={inputStyle}>
            <option value="linkup">LinkUp</option>
            <option value="abanoonya">Abanoonya Pro</option>
            <option value="uganda_dating">Uganda Dating App</option>
          </select>
        </FormRow>
        <FormRow label="Code" required hint="e.g. weekly, monthly — unique per app">
          <input style={inputStyle} value={form.code} onChange={(e) => setField('code', e.target.value)} />
        </FormRow>
        <FormRow label="Name" required>
          <input style={inputStyle} value={form.name} onChange={(e) => setField('name', e.target.value)} />
        </FormRow>
        <FormRow label="Badge color">
          <input style={inputStyle} value={form.badge_color} placeholder="#7C3AED" onChange={(e) => setField('badge_color', e.target.value)} />
        </FormRow>
        <FormRow label="Price (UGX)" required>
          <input type="number" style={inputStyle} value={form.price_ugx} onChange={(e) => setField('price_ugx', e.target.value)} />
        </FormRow>
        <FormRow label="Duration (days)" required hint="0 = free / no expiry">
          <input type="number" style={inputStyle} value={form.duration_days} onChange={(e) => setField('duration_days', e.target.value)} />
        </FormRow>
        <FormRow label="Sort order">
          <input type="number" style={inputStyle} value={form.sort_order} onChange={(e) => setField('sort_order', e.target.value)} />
        </FormRow>
      </FormGrid>
      <FormRow label="Tagline">
        <input style={inputStyle} value={form.tagline} onChange={(e) => setField('tagline', e.target.value)} />
      </FormRow>

      <div style={{ fontSize: 11.5, fontWeight: 800, textTransform: 'uppercase', color: '#8a8a93', margin: '16px 0 8px' }}>
        Numeric limits (-1 = unlimited)
      </div>
      <FormGrid cols={3}>
        {NUMERIC_LIMIT_FIELDS.map(([key, label]) => (
          <FormRow key={key} label={label}>
            <input type="number" style={inputStyle} value={form.limits[key]} onChange={(e) => setLimit(key, Number(e.target.value))} />
          </FormRow>
        ))}
      </FormGrid>
      <div style={{ fontSize: 11.5, fontWeight: 800, textTransform: 'uppercase', color: '#8a8a93', margin: '4px 0 8px' }}>
        Feature flags
      </div>
      <FormGrid cols={3}>
        {BOOLEAN_LIMIT_FIELDS.map(([key, label]) => (
          <label key={key} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.5, marginBottom: 10, cursor: 'pointer' }}>
            <input type="checkbox" checked={!!form.limits[key]} onChange={(e) => setLimit(key, e.target.checked)} />
            {label}
          </label>
        ))}
      </FormGrid>
    </Modal>
  );
}

function SubscribersTab() {
  const { appId } = useAppScope();
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({ page: 1, lastPage: 1, total: 0 });
  const [revenue, setRevenue] = useState({ total_active_subscribers: 0, total_revenue_ugx: 0 });
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminAPI.subscriptions({ status: status || undefined, app_id: appId || undefined, page, per_page: 20 });
      const p = pageOf(res);
      setRows(p.items);
      setMeta({ page: p.page, lastPage: p.lastPage, total: p.total });
      setRevenue(res?.data?.data?.revenue_summary || { total_active_subscribers: 0, total_revenue_ugx: 0 });
    } catch (_) { setRows([]); } finally { setLoading(false); }
  }, [status, appId, page]);

  useEffect(() => { load(); }, [load]);

  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 14, marginBottom: 16 }}>
        <StatCard icon={FiUsers} label="Active subscribers" value={revenue.total_active_subscribers} color="#7C3AED" />
        <StatCard icon={FiDollarSign} label="Revenue (active)" value={`${(revenue.total_revenue_ugx || 0).toLocaleString()} UGX`} color="#059669" />
      </div>
      <Toolbar>
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          style={{ padding: '9px 12px', borderRadius: 8, border: '1px solid #d8d8e0', fontSize: 13.5 }}>
          {STATUSES.map((s) => <option key={s} value={s}>{s ? s[0].toUpperCase() + s.slice(1) : 'All statuses'}</option>)}
        </select>
        <button style={btn(false)} onClick={load}><FiRefreshCw /> Refresh</button>
      </Toolbar>
      <table style={tableStyle}>
        <thead><tr>
          <th style={thStyle}>Member</th><th style={thStyle}>Plan</th><th style={thStyle}>Status</th>
          <th style={thStyle}>Amount paid</th><th style={thStyle}>Expires</th><th style={thStyle}>Started</th>
        </tr></thead>
        <tbody>
          {loading ? <EmptyRow colSpan={6} text="Loading…" />
            : rows.length === 0 ? <EmptyRow colSpan={6} text="No subscriptions yet." />
            : rows.map((s) => (
              <tr key={s.id}>
                <td style={tdStyle}>{s.account?.display_name || '—'} <span style={{ color: '#9a9aa3' }}>@{s.account?.handle}</span></td>
                <td style={tdStyle}>{s.plan?.name || '—'}</td>
                <td style={tdStyle}><Badge value={s.status} /></td>
                <td style={tdStyle}>{s.amount_paid_ugx.toLocaleString()} UGX</td>
                <td style={tdStyle}>{fmtDate(s.expires_at)}</td>
                <td style={tdStyle}>{fmtDate(s.created_at)}</td>
              </tr>
            ))}
        </tbody>
      </table>
      <Pager page={meta.page} lastPage={meta.lastPage} total={meta.total} onPage={setPage} />
    </>
  );
}

function StatCard({ icon: Icon, label, value, color }) {
  return (
    <div style={{ background: '#fff', border: '1px solid #ececf1', borderRadius: 10, padding: '16px 18px',
      display: 'flex', alignItems: 'center', gap: 14 }}>
      <div style={{ width: 42, height: 42, borderRadius: 10, display: 'grid', placeItems: 'center',
        background: `${color}14`, color, flexShrink: 0 }}><Icon size={20} /></div>
      <div>
        <div style={{ fontSize: 22, fontWeight: 800, lineHeight: 1.1, color: '#151519' }}>{value ?? '—'}</div>
        <div style={{ fontSize: 12.5, color: '#6b6b76', marginTop: 2 }}>{label}</div>
      </div>
    </div>
  );
}

import React, { useEffect, useState } from 'react';
import { adminAPI, dataOf, pageOf } from '../services/api';
import { Badge, Avatar, fmtDate, tableStyle, thStyle, tdStyle, Pager, EmptyRow, btn } from './adminUi';
import { useAppScope } from '../contexts/AppScopeContext';
import {
  FiUsers, FiTrendingUp, FiPhoneCall, FiRefreshCw,
} from 'react-icons/fi';

// Same stat-card visual language as DashboardHome.jsx — deliberately not a
// new component, this page is meant to feel like a continuation of it, not
// a different product.
const card = {
  background: '#fff', border: '1px solid #ececf1', borderRadius: 10,
  padding: '16px 18px', display: 'flex', alignItems: 'center', gap: 14,
};
const iconWrap = (c) => ({
  width: 42, height: 42, borderRadius: 10, display: 'grid', placeItems: 'center',
  background: `${c}14`, color: c, flexShrink: 0,
});

function Stat({ icon: Icon, label, value, color }) {
  return (
    <div style={card}>
      <div style={iconWrap(color)}><Icon size={20} /></div>
      <div>
        <div style={{ fontSize: 22, fontWeight: 800, lineHeight: 1.1, color: '#151519' }}>{value ?? '—'}</div>
        <div style={{ fontSize: 12.5, color: '#6b6b76', marginTop: 2 }}>{label}</div>
      </div>
    </div>
  );
}

function Section({ title, right, children }) {
  return (
    <div style={{ marginBottom: 28 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h3 style={{ fontSize: 13, textTransform: 'uppercase', letterSpacing: 0.6,
          color: '#8a8a93', margin: 0, fontWeight: 700 }}>{title}</h3>
        {right}
      </div>
      {children}
    </div>
  );
}

const VERB_LABELS = {
  'spark.spark_up': 'Sparks (likes)', 'spark.pass': 'Passes', 'spark.standout': 'Standouts',
  'spark.undo': 'Undos', 'profile.view': 'Profile views', 'photo.view': 'Photo views',
  'message.send': 'Messages sent', 'contact.reveal': 'Contacts revealed',
  'link.request': 'Link requests', 'link.accept': 'Link accepts', 'job.apply': 'Job applications',
  'job.view': 'Job views', 'post.like': 'Post likes', 'post.comment': 'Post comments',
  'hub.join': 'Hub joins', 'moderation.flag': 'Moderation flags',
};
const verbLabel = (v) => VERB_LABELS[v] || v;

export default function AnalyticsPage() {
  const { appId } = useAppScope();
  const [overview, setOverview] = useState(null);
  const [trending, setTrending] = useState([]);
  const [contacts, setContacts] = useState([]);
  const [contactsMeta, setContactsMeta] = useState({ page: 1, lastPage: 1, total: 0 });
  const [contactsPage, setContactsPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const scope = { app_id: appId || 'abanoonya' };

  const load = async () => {
    setLoading(true);
    try {
      const [ov, tr] = await Promise.all([
        adminAPI.analyticsOverview(scope),
        adminAPI.analyticsTrending({ ...scope, limit: 10 }),
      ]);
      setOverview(dataOf(ov));
      setTrending(dataOf(tr) || []);
    } finally {
      setLoading(false);
    }
  };

  const loadContacts = async () => {
    const res = await adminAPI.analyticsContacts({ ...scope, page: contactsPage, per_page: 10 });
    const p = pageOf(res);
    setContacts(p.items);
    setContactsMeta({ page: p.page, lastPage: p.lastPage, total: p.total });
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [appId]);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { loadContacts(); }, [appId, contactsPage]);

  if (loading) return <div className="page-loader">Loading…</div>;

  const dau = overview?.dau ?? 0;
  const wau = overview?.wau ?? 0;
  const mau = overview?.mau ?? 0;
  const events = overview?.events_by_verb_7d || [];
  const maxCount = Math.max(1, ...events.map((e) => e.count));

  return (
    <div style={{ padding: 4 }}>
      <Section title="Active members" right={
        <button style={btn(false)} onClick={load}><FiRefreshCw /> Refresh</button>
      }>
        <div style={{ display: 'grid', gap: 14, gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))' }}>
          <Stat icon={FiUsers} label="Active today (DAU)" value={dau} color="#7C3AED" />
          <Stat icon={FiUsers} label="Active this week (WAU)" value={wau} color="#2563EB" />
          <Stat icon={FiUsers} label="Active this month (MAU)" value={mau} color="#0891B2" />
        </div>
      </Section>

      <Section title="Engagement — last 7 days">
        {events.length === 0 ? (
          <div style={{ color: '#9a9aa3', fontSize: 13 }}>No activity recorded in the last 7 days.</div>
        ) : (
          <div style={{ background: '#fff', border: '1px solid #ececf1', borderRadius: 10, padding: '14px 18px' }}>
            {events.map((e) => (
              <div key={e.verb} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '7px 0' }}>
                <div style={{ width: 150, fontSize: 12.5, color: '#3f3f46', flexShrink: 0 }}>{verbLabel(e.verb)}</div>
                <div style={{ flex: 1, background: '#f4f4f6', borderRadius: 6, height: 10, overflow: 'hidden' }}>
                  <div style={{
                    width: `${(e.count / maxCount) * 100}%`, height: '100%',
                    background: 'linear-gradient(90deg,#7C3AED,#DB2777)', borderRadius: 6,
                  }} />
                </div>
                <div style={{ width: 48, textAlign: 'right', fontSize: 12.5, fontWeight: 700, color: '#151519' }}>{e.count}</div>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title={<><FiTrendingUp style={{ verticalAlign: -2, marginRight: 5 }} />Trending profiles (7-day)</>}>
        {trending.length === 0 ? (
          <div style={{ color: '#9a9aa3', fontSize: 13 }}>Nothing trending yet.</div>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            {trending.map((t) => (
              <div key={t.account_id} style={{
                display: 'flex', alignItems: 'center', gap: 10, background: '#fff',
                border: '1px solid #ececf1', borderRadius: 10, padding: '8px 12px', minWidth: 200,
              }}>
                <Avatar name={t.display_name} avatar={t.avatar} size={34} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {t.display_name || '—'}
                  </div>
                  {t.account_status !== 'active' && (
                    <Badge value={t.account_status} />
                  )}
                </div>
                <div style={{ fontSize: 13, fontWeight: 800, color: '#DB2777' }}>{t.score}</div>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title={<><FiPhoneCall style={{ verticalAlign: -2, marginRight: 5 }} />Contact reveals</>}>
        <table style={tableStyle}>
          <thead>
            <tr>
              <th style={thStyle}>Who revealed</th>
              <th style={thStyle}>Whose contact</th>
              <th style={thStyle}>When</th>
            </tr>
          </thead>
          <tbody>
            {contacts.length === 0 ? (
              <EmptyRow colSpan={3} text="No contact reveals yet." />
            ) : contacts.map((c) => (
              <tr key={c.id}>
                <td style={tdStyle}>{c.actor_name || c.actor_id}</td>
                <td style={tdStyle}>{c.target_name || c.target_id}</td>
                <td style={tdStyle}>{fmtDate(c.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <Pager page={contactsMeta.page} lastPage={contactsMeta.lastPage} total={contactsMeta.total} onPage={setContactsPage} />
      </Section>
    </div>
  );
}

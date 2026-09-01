import React, { useEffect, useState } from 'react';
import { adminAPI, dataOf } from '../services/api';
import { Drawer, Badge, Avatar, AppBadge, fmtDate, SectionTitle, KeyVal, btn } from './adminUi';
import { KycThumb } from './ReviewsPage';

export default function AccountDetailDrawer({ accountId, onClose, onChanged }) {
  const [data, setData] = useState(null);
  const [engagement, setEngagement] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!accountId) return;
    setLoading(true);
    setEngagement(null);
    adminAPI.accountShow(accountId)
      .then((res) => setData(dataOf(res)))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
    // Separate, independent fetch — a failure here shouldn't block the rest
    // of the drawer from rendering, this section just stays empty.
    adminAPI.analyticsAccount(accountId)
      .then((res) => setEngagement(dataOf(res)))
      .catch(() => setEngagement(null));
  }, [accountId]);

  const doStatus = async (status) => {
    const verb = status === 'active' ? 'reinstate' : 'suspend';
    if (!window.confirm(`${verb[0].toUpperCase() + verb.slice(1)} ${data.display_name}?`)) return;
    setBusy(true);
    try {
      await adminAPI.accountStatus(accountId, { status });
      const res = await adminAPI.accountShow(accountId);
      setData(dataOf(res));
      onChanged?.();
    } catch (e) {
      alert(e.response?.data?.message || 'Action failed.');
    } finally {
      setBusy(false);
    }
  };

  const togglePremium = async () => {
    setBusy(true);
    try {
      await adminAPI.accountPremium(accountId, { is_premium: !data.is_premium });
      const res = await adminAPI.accountShow(accountId);
      setData(dataOf(res));
      onChanged?.();
    } catch (e) {
      alert(e.response?.data?.message || 'Action failed.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Drawer open={!!accountId} onClose={onClose} title="Account detail" width={520}>
      {loading || !data ? (
        <div style={{ color: '#9a9aa3', padding: 20, textAlign: 'center' }}>
          {loading ? 'Loading…' : 'Not found.'}
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
            <Avatar name={data.display_name} avatar={data.avatar} size={56} />
            <div>
              <div style={{ fontWeight: 800, fontSize: 16 }}>{data.display_name}</div>
              <div style={{ color: '#9a9aa3', fontSize: 13 }}>@{data.handle}</div>
              <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                <AppBadge appId={data.app_id} />
                <Badge value={data.account_status} />
                {data.is_premium && <Badge value="premium">Premium</Badge>}
                {data.is_admin && <Badge value="admin">Admin</Badge>}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
            <button style={btn(true)} disabled={busy} onClick={togglePremium}>
              {data.is_premium ? 'Revoke premium' : 'Grant premium'}
            </button>
            {data.account_status === 'active' ? (
              <button style={btn(true, true)} disabled={busy} onClick={() => doStatus('suspended')}>Suspend</button>
            ) : (
              <button style={btn(false)} disabled={busy} onClick={() => doStatus('active')}>Reinstate</button>
            )}
          </div>

          <SectionTitle>Contact</SectionTitle>
          <KeyVal k="Email" v={data.email} />
          <KeyVal k="Phone" v={data.phone} />
          <KeyVal k="Joined" v={fmtDate(data.created_at)} />
          <KeyVal k="Last seen" v={data.is_online ? 'Online now' : fmtDate(data.last_seen_at)} />

          <SectionTitle>Trust & safety</SectionTitle>
          <KeyVal k="KYC level" v={`L${data.kyc_level ?? 0}`} />
          <KeyVal k="Reports against them" v={data.report_count} />
          <KeyVal k="Reports they've filed" v={data.reports_filed_count} />
          <KeyVal k="Blocked by" v={`${data.blocked_by_count} people`} />
          <KeyVal k="Blocking" v={`${data.blocking_count} people`} />
          {data.kyc_submissions?.length > 0 && (
            <div style={{ marginTop: 8 }}>
              {data.kyc_submissions.map((k) => (
                <div key={k.id} style={{ padding: '6px 0', borderBottom: '1px solid #f0f0f3' }}>
                  <div style={{ fontSize: 12, color: '#8a8a93' }}>
                    {k.type} — <Badge value={k.status} /> — {fmtDate(k.created_at)}
                  </div>
                  <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
                    <KycThumb url={k.id_photo_url} label="ID" />
                    <KycThumb url={k.selfie_url} label="Selfie" />
                  </div>
                  {k.status === 'rejected' && k.rejection_reason && (
                    <div style={{ fontSize: 11.5, color: '#B91C1C', marginTop: 4 }}>Reason: {k.rejection_reason}</div>
                  )}
                </div>
              ))}
            </div>
          )}

          <SectionTitle>Wallet</SectionTitle>
          {data.wallet ? (
            <>
              <KeyVal k="Balance" v={`${data.wallet.balance.toLocaleString()} ${data.wallet.currency}`} />
              <KeyVal k="Coins" v={data.wallet.coins} />
              <KeyVal k="Redeemable (gifts)" v={`${data.wallet.redeemable.toLocaleString()} ${data.wallet.currency}`} />
            </>
          ) : <KeyVal k="Wallet" v="No wallet yet" />}

          <SectionTitle>Profile</SectionTitle>
          <KeyVal k="Photos" v={data.photo_count} />
          <KeyVal k="Professional profile" v={data.professional_profile ? data.professional_profile.headline || 'Set up' : 'Not set up'} />
          <KeyVal k="Dating profile" v={data.dating_profile ? 'Set up' : 'Not set up'} />
          <KeyVal k="Modes enabled" v={Object.entries(data.modes_enabled || {}).filter(([, v]) => v).map(([k]) => k).join(', ') || '—'} />

          <SectionTitle>Engagement</SectionTitle>
          {!engagement ? (
            <div style={{ color: '#c4c4cc', fontSize: 12.5 }}>Loading…</div>
          ) : (
            <>
              <KeyVal k="Location freshness"
                v={engagement.needs_location_update
                  ? `Stale${engagement.location_updated_at ? ` — since ${fmtDate(engagement.location_updated_at)}` : ' — never set'}`
                  : 'Up to date'} />
              {(engagement.actions_given_30d?.length > 0 || engagement.actions_received_30d?.length > 0) ? (
                <div style={{ display: 'flex', gap: 20, marginTop: 8 }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: '#9a9aa3', marginBottom: 4 }}>DID (30d)</div>
                    {(engagement.actions_given_30d || []).map((e) => (
                      <div key={e.verb} style={{ fontSize: 12, color: '#3f3f46', padding: '2px 0' }}>
                        {e.verb} — <strong>{e.count}</strong>
                      </div>
                    ))}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: '#9a9aa3', marginBottom: 4 }}>RECEIVED (30d)</div>
                    {(engagement.actions_received_30d || []).map((e) => (
                      <div key={e.verb} style={{ fontSize: 12, color: '#3f3f46', padding: '2px 0' }}>
                        {e.verb} — <strong>{e.count}</strong>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div style={{ color: '#c4c4cc', fontSize: 12.5, marginTop: 6 }}>No recorded activity in the last 30 days.</div>
              )}
            </>
          )}
        </>
      )}
    </Drawer>
  );
}

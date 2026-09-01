import React, { useEffect, useState, useCallback } from 'react';
import { adminAPI, dataOf } from '../services/api';
import { FiRefreshCw, FiSave } from 'react-icons/fi';
import { AppBadge, Toolbar, btn } from './adminUi';

// Ship a build, then raise min_supported_build to force everyone onto it.
// This config used to be database-only — no admin route could write it.
export default function AppVersionsPage() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [edits, setEdits] = useState({});
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = dataOf(await adminAPI.appVersions()) || [];
      setRows(data);
      setEdits(Object.fromEntries(data.map((r) => [r.id, { ...r }])));
    } catch (_) { setRows([]); } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const setField = (id, field, val) => setEdits((e) => ({ ...e, [id]: { ...e[id], [field]: val } }));

  const save = async (id) => {
    const e = edits[id];
    setBusyId(id);
    try {
      await adminAPI.appVersionUpdate(id, {
        latest_build: Number(e.latest_build),
        min_supported_build: Number(e.min_supported_build),
        latest_version_name: e.latest_version_name,
        update_notes: e.update_notes,
        android_url: e.android_url,
        ios_url: e.ios_url,
      });
      await load();
    } catch (err) {
      alert(err.response?.data?.message || 'Save failed.');
    } finally { setBusyId(null); }
  };

  return (
    <div style={{ padding: 4 }}>
      <Toolbar><button style={btn(false)} onClick={load}><FiRefreshCw /> Refresh</button></Toolbar>
      {loading ? <div style={{ padding: '32px 14px', textAlign: 'center', color: '#9a9aa3' }}>Loading…</div> : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          {rows.map((r) => {
            const e = edits[r.id] || r;
            const forcing = Number(e.min_supported_build) > 0;
            return (
              <div key={r.id} style={{ background: '#fff', border: '1px solid #ececf1',
                borderRadius: 10, padding: 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                  <AppBadge appId={r.app_id} />
                  <span style={{ fontWeight: 800, textTransform: 'capitalize' }}>{r.platform}</span>
                </div>
                <Field label="Latest version name" value={e.latest_version_name}
                  onChange={(v) => setField(r.id, 'latest_version_name', v)} />
                <Field label="Latest build" value={e.latest_build} type="number"
                  onChange={(v) => setField(r.id, 'latest_build', v)} />
                <Field label="Min supported build (force-update threshold)" value={e.min_supported_build} type="number"
                  onChange={(v) => setField(r.id, 'min_supported_build', v)} />
                <Field label="Update notes" value={e.update_notes} multiline
                  onChange={(v) => setField(r.id, 'update_notes', v)} />
                <Field label="Android store URL" value={e.android_url}
                  onChange={(v) => setField(r.id, 'android_url', v)} />
                <Field label="iOS store URL" value={e.ios_url}
                  onChange={(v) => setField(r.id, 'ios_url', v)} />
                <div style={{ fontSize: 11.5, color: '#8a8a93', margin: '6px 0 10px' }}>
                  Builds below <b>{e.min_supported_build}</b> will be force-blocked from continuing until they update.
                </div>
                <button style={btn(true)} disabled={busyId === r.id} onClick={() => save(r.id)}>
                  <FiSave /> Save
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Field({ label, value, onChange, type = 'text', multiline }) {
  const props = {
    value: value ?? '', onChange: (e) => onChange(e.target.value),
    style: { width: '100%', padding: '7px 10px', borderRadius: 6, border: '1px solid #d8d8e0',
      fontSize: 13, marginTop: 3, marginBottom: 10, fontFamily: 'inherit' },
  };
  return (
    <label style={{ display: 'block' }}>
      <div style={{ fontSize: 11.5, fontWeight: 700, color: '#6b6b76' }}>{label}</div>
      {multiline ? <textarea rows={2} {...props} /> : <input type={type} {...props} />}
    </label>
  );
}

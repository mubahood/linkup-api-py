import React, { useEffect, useState } from 'react';
import { adminAPI, referenceAPI, dataOf } from '../services/api';
import { FiCopy, FiCheck } from 'react-icons/fi';
import { Modal, FormRow, FormGrid, FormSection, inputStyle, btn, Avatar } from './adminUi';

const SENIORITY = ['entry', 'mid', 'senior', 'lead', 'executive'];
const AVAILABILITY = ['open', 'casually_looking', 'not_looking'];

const emptyForm = {
  display_name: '', handle: '', phone: '', email: '', password: '',
  app_id: 'linkup', is_premium: false,
  modes: { professional: true, sparks: false },
  dating_profile: {
    bio: '', gender: '', looking_for_gender: '', sexual_orientation: '',
    birth_year: '', relationship_goal: '', height_cm: '', body_type: '',
    smoking: '', drinking: '', marijuana: '', diet: '', exercise: '',
    education_level: '', religion: '', tribe_ethnicity: '', industry: '',
    district_id: '', max_distance_km: '',
  },
  professional_profile: {
    headline: '', bio: '', seniority: '', current_role: '', industry: '',
    years_experience: '', pronouns: '', tagline: '', availability_status: '',
  },
};

// Ajax-powered account creation with an optional complete dating/professional
// profile in the same request (POST /v1/admin/accounts). Options for every
// select come from the app's own canonical catalog (GET
// /v1/reference/dating-options) so this form can never drift out of sync
// with what the mobile app itself offers.
export default function CreateAccountModal({ open, onClose, onCreated }) {
  const [form, setForm] = useState(emptyForm);
  const [options, setOptions] = useState({});
  const [districts, setDistricts] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null); // set after a successful create
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!open) return;
    setForm(emptyForm);
    setError('');
    setResult(null);
    setCopied(false);
    referenceAPI.datingOptions().then((res) => setOptions(dataOf(res) || {})).catch(() => setOptions({}));
    referenceAPI.locations({ level: 'district' }).then((res) => {
      const list = dataOf(res) || [];
      setDistricts([...list].sort((a, b) => a.name.localeCompare(b.name)));
    }).catch(() => setDistricts([]));
  }, [open]);

  const set = (field, value) => setForm((f) => ({ ...f, [field]: value }));
  const setDating = (field, value) => setForm((f) => ({ ...f, dating_profile: { ...f.dating_profile, [field]: value } }));
  const setPro = (field, value) => setForm((f) => ({ ...f, professional_profile: { ...f.professional_profile, [field]: value } }));
  const setMode = (mode, value) => setForm((f) => ({ ...f, modes: { ...f.modes, [mode]: value } }));

  const optionsFor = (key) => options[key] || [];

  const submit = async () => {
    setError('');
    if (!form.display_name.trim()) return setError('Display name is required.');
    if (!form.phone.trim() && !form.email.trim()) return setError('Enter a phone number or an email address.');

    setSaving(true);
    try {
      const payload = {
        display_name: form.display_name.trim(),
        handle: form.handle.trim() || undefined,
        phone: form.phone.trim() || undefined,
        email: form.email.trim() || undefined,
        password: form.password.trim() || undefined,
        app_id: form.app_id,
        is_premium: form.is_premium,
        modes: form.modes,
      };
      if (form.modes.sparks) {
        payload.dating_profile = Object.fromEntries(
          Object.entries(form.dating_profile).filter(([, v]) => v !== '')
        );
      }
      if (form.modes.professional) {
        payload.professional_profile = Object.fromEntries(
          Object.entries(form.professional_profile).filter(([, v]) => v !== '')
        );
      }
      const res = await adminAPI.accountCreate(payload);
      setResult(dataOf(res));
      onCreated?.();
    } catch (e) {
      setError(e.response?.data?.message || 'Could not create the account.');
    } finally {
      setSaving(false);
    }
  };

  const copyPassword = () => {
    navigator.clipboard?.writeText(result.generated_password);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  // ── Success screen: show the one-time generated password, if any ──────────
  if (result) {
    return (
      <Modal open={open} onClose={onClose} title="Account created" width={480}
        footer={<button style={btn(true)} onClick={onClose}>Done</button>}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 18 }}>
          <Avatar name={result.display_name} avatar={result.avatar} size={44} />
          <div>
            <div style={{ fontWeight: 800 }}>{result.display_name}</div>
            <div style={{ color: '#9a9aa3', fontSize: 13 }}>@{result.handle}</div>
          </div>
        </div>
        {result.generated_password ? (
          <div style={{
            background: '#fafafa', border: '1px solid #ececf1', borderRadius: 10, padding: 14,
          }}>
            <div style={{ fontSize: 12, color: '#8a8a93', marginBottom: 6 }}>
              Generated password — shown once, not recoverable afterward. Share it securely.
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <code style={{
                flex: 1, background: '#fff', border: '1px solid #d8d8e0', borderRadius: 6,
                padding: '8px 10px', fontSize: 14, fontWeight: 700, letterSpacing: 0.5,
              }}>{result.generated_password}</code>
              <button style={btn(false)} onClick={copyPassword}>
                {copied ? <FiCheck color="#059669" /> : <FiCopy />}
              </button>
            </div>
          </div>
        ) : (
          <div style={{ fontSize: 13, color: '#6b6b76' }}>The password you set is active — no need to share anything further.</div>
        )}
      </Modal>
    );
  }

  return (
    <Modal open={open} onClose={onClose} title="New account" width={760}
      footer={<>
        <button style={btn(false)} onClick={onClose} disabled={saving}>Cancel</button>
        <button style={btn(true)} onClick={submit} disabled={saving}>{saving ? 'Creating…' : 'Create account'}</button>
      </>}>
      {error && (
        <div style={{
          background: '#fef2f2', color: '#DC2626', border: '1px solid #f3c4c4',
          borderRadius: 8, padding: '10px 12px', fontSize: 13, marginBottom: 16,
        }}>{error}</div>
      )}

      <FormSection title="Basic info">
        <FormGrid cols={2}>
          <FormRow label="Display name" required>
            <input style={inputStyle} value={form.display_name} onChange={(e) => set('display_name', e.target.value)} placeholder="Jane Doe" />
          </FormRow>
          <FormRow label="Handle" hint="Leave blank to auto-generate">
            <input style={inputStyle} value={form.handle} onChange={(e) => set('handle', e.target.value.toLowerCase())} placeholder="jane-doe" />
          </FormRow>
          <FormRow label="Phone" hint="At least one of phone or email is required">
            <input style={inputStyle} value={form.phone} onChange={(e) => set('phone', e.target.value)} placeholder="+256700000000" />
          </FormRow>
          <FormRow label="Email">
            <input style={inputStyle} type="email" value={form.email} onChange={(e) => set('email', e.target.value)} placeholder="jane@example.com" />
          </FormRow>
          <FormRow label="Password" hint="Leave blank to generate a random one">
            <input style={inputStyle} type="text" value={form.password} onChange={(e) => set('password', e.target.value)} placeholder="Auto-generated if blank" />
          </FormRow>
          <FormRow label="App">
            <select style={inputStyle} value={form.app_id} onChange={(e) => set('app_id', e.target.value)}>
              <option value="linkup">LinkUp</option>
              <option value="abanoonya">Abanoonya Pro</option>
            </select>
          </FormRow>
        </FormGrid>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, marginTop: 4 }}>
          <input type="checkbox" checked={form.is_premium} onChange={(e) => set('is_premium', e.target.checked)} />
          Grant premium immediately
        </label>
      </FormSection>

      <FormSection title="Modes" description="Which parts of the profile should this account have?">
        <div style={{ display: 'flex', gap: 20 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13.5 }}>
            <input type="checkbox" checked={form.modes.professional} onChange={(e) => setMode('professional', e.target.checked)} />
            Professional
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13.5 }}>
            <input type="checkbox" checked={form.modes.sparks} onChange={(e) => setMode('sparks', e.target.checked)} />
            Sparks (dating)
          </label>
        </div>
      </FormSection>

      {form.modes.sparks && (
        <FormSection title="Dating profile">
          <FormRow label="Bio">
            <textarea style={{ ...inputStyle, minHeight: 64, resize: 'vertical' }} value={form.dating_profile.bio}
              onChange={(e) => setDating('bio', e.target.value)} placeholder="A short bio…" />
          </FormRow>
          <FormGrid cols={3}>
            <FormRow label="Gender">
              <SelectFrom style={inputStyle} value={form.dating_profile.gender} onChange={(v) => setDating('gender', v)} options={optionsFor('gender')} />
            </FormRow>
            <FormRow label="Looking for">
              <SelectFrom style={inputStyle} value={form.dating_profile.looking_for_gender} onChange={(v) => setDating('looking_for_gender', v)} options={optionsFor('gender')} />
            </FormRow>
            <FormRow label="Orientation">
              <SelectFrom style={inputStyle} value={form.dating_profile.sexual_orientation} onChange={(v) => setDating('sexual_orientation', v)} options={optionsFor('orientation')} />
            </FormRow>
            <FormRow label="Birth year">
              <input style={inputStyle} type="number" min="1940" max={new Date().getFullYear() - 18} value={form.dating_profile.birth_year}
                onChange={(e) => setDating('birth_year', e.target.value ? Number(e.target.value) : '')} placeholder="1998" />
            </FormRow>
            <FormRow label="Relationship goal">
              <SelectFrom style={inputStyle} value={form.dating_profile.relationship_goal} onChange={(v) => setDating('relationship_goal', v)} options={optionsFor('relationship_goal')} />
            </FormRow>
            <FormRow label="Height (cm)">
              <input style={inputStyle} type="number" min="120" max="230" value={form.dating_profile.height_cm}
                onChange={(e) => setDating('height_cm', e.target.value ? Number(e.target.value) : '')} placeholder="170" />
            </FormRow>
            <FormRow label="Body type">
              <SelectFrom style={inputStyle} value={form.dating_profile.body_type} onChange={(v) => setDating('body_type', v)} options={optionsFor('body_type')} />
            </FormRow>
            <FormRow label="Smoking">
              <SelectFrom style={inputStyle} value={form.dating_profile.smoking} onChange={(v) => setDating('smoking', v)} options={optionsFor('smoking')} />
            </FormRow>
            <FormRow label="Drinking">
              <SelectFrom style={inputStyle} value={form.dating_profile.drinking} onChange={(v) => setDating('drinking', v)} options={optionsFor('drinking')} />
            </FormRow>
            <FormRow label="Marijuana">
              <SelectFrom style={inputStyle} value={form.dating_profile.marijuana} onChange={(v) => setDating('marijuana', v)} options={optionsFor('marijuana')} />
            </FormRow>
            <FormRow label="Diet">
              <SelectFrom style={inputStyle} value={form.dating_profile.diet} onChange={(v) => setDating('diet', v)} options={optionsFor('diet')} />
            </FormRow>
            <FormRow label="Exercise">
              <SelectFrom style={inputStyle} value={form.dating_profile.exercise} onChange={(v) => setDating('exercise', v)} options={optionsFor('exercise')} />
            </FormRow>
            <FormRow label="Education">
              <SelectFrom style={inputStyle} value={form.dating_profile.education_level} onChange={(v) => setDating('education_level', v)} options={optionsFor('education_level')} />
            </FormRow>
            <FormRow label="Religion">
              <SelectFrom style={inputStyle} value={form.dating_profile.religion} onChange={(v) => setDating('religion', v)} options={optionsFor('religion')} />
            </FormRow>
            <FormRow label="Tribe / ethnicity">
              <SelectFrom style={inputStyle} value={form.dating_profile.tribe_ethnicity} onChange={(v) => setDating('tribe_ethnicity', v)} options={optionsFor('tribe')} />
            </FormRow>
            <FormRow label="Industry">
              <SelectFrom style={inputStyle} value={form.dating_profile.industry} onChange={(v) => setDating('industry', v)} options={optionsFor('industry')} />
            </FormRow>
            <FormRow label="District">
              <select style={inputStyle} value={form.dating_profile.district_id} onChange={(e) => setDating('district_id', e.target.value)}>
                <option value="">—</option>
                {districts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </FormRow>
            <FormRow label="Max distance (km)">
              <input style={inputStyle} type="number" min="1" max="500" value={form.dating_profile.max_distance_km}
                onChange={(e) => setDating('max_distance_km', e.target.value ? Number(e.target.value) : '')} placeholder="50" />
            </FormRow>
          </FormGrid>
        </FormSection>
      )}

      {form.modes.professional && (
        <FormSection title="Professional profile">
          <FormGrid cols={2}>
            <FormRow label="Headline">
              <input style={inputStyle} value={form.professional_profile.headline} onChange={(e) => setPro('headline', e.target.value)} placeholder="Software Engineer at Acme" />
            </FormRow>
            <FormRow label="Current role">
              <input style={inputStyle} value={form.professional_profile.current_role} onChange={(e) => setPro('current_role', e.target.value)} placeholder="Backend Engineer" />
            </FormRow>
          </FormGrid>
          <FormRow label="Bio">
            <textarea style={{ ...inputStyle, minHeight: 64, resize: 'vertical' }} value={form.professional_profile.bio}
              onChange={(e) => setPro('bio', e.target.value)} placeholder="A short professional bio…" />
          </FormRow>
          <FormGrid cols={3}>
            <FormRow label="Seniority">
              <select style={inputStyle} value={form.professional_profile.seniority} onChange={(e) => setPro('seniority', e.target.value)}>
                <option value="">—</option>
                {SENIORITY.map((s) => <option key={s} value={s}>{s[0].toUpperCase() + s.slice(1)}</option>)}
              </select>
            </FormRow>
            <FormRow label="Industry">
              <SelectFrom style={inputStyle} value={form.professional_profile.industry} onChange={(v) => setPro('industry', v)} options={optionsFor('industry')} />
            </FormRow>
            <FormRow label="Years of experience">
              <input style={inputStyle} type="number" min="0" max="60" value={form.professional_profile.years_experience}
                onChange={(e) => setPro('years_experience', e.target.value ? Number(e.target.value) : '')} placeholder="5" />
            </FormRow>
            <FormRow label="Pronouns">
              <input style={inputStyle} value={form.professional_profile.pronouns} onChange={(e) => setPro('pronouns', e.target.value)} placeholder="she/her" />
            </FormRow>
            <FormRow label="Tagline">
              <input style={inputStyle} value={form.professional_profile.tagline} onChange={(e) => setPro('tagline', e.target.value)} placeholder="Building things that matter" />
            </FormRow>
            <FormRow label="Availability">
              <select style={inputStyle} value={form.professional_profile.availability_status} onChange={(e) => setPro('availability_status', e.target.value)}>
                <option value="">—</option>
                {AVAILABILITY.map((a) => <option key={a} value={a}>{a.replace(/_/g, ' ')}</option>)}
              </select>
            </FormRow>
          </FormGrid>
        </FormSection>
      )}
    </Modal>
  );
}

function SelectFrom({ style, value, onChange, options }) {
  return (
    <select style={style} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">—</option>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

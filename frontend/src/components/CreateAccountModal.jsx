import React, { useEffect, useMemo, useState } from 'react';
import { adminAPI, referenceAPI, dataOf } from '../services/api';
import {
  FiCopy, FiCheck, FiUser, FiPhone, FiMail, FiLock, FiHeart, FiBriefcase,
  FiChevronRight, FiChevronLeft, FiShuffle, FiChevronDown, FiMapPin,
  FiWind, FiCoffee, FiCompass,
} from 'react-icons/fi';
import { Modal, inputStyle, btn, Stepper } from './adminUi';

const SENIORITY = ['entry', 'mid', 'senior', 'lead', 'executive'];
const AVAILABILITY = [
  { value: 'open', label: 'Open to opportunities' },
  { value: 'casually_looking', label: 'Casually looking' },
  { value: 'not_looking', label: 'Not looking' },
];

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

function generatePassword(length = 12) {
  const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789';
  let out = '';
  for (let i = 0; i < length; i++) out += alphabet[Math.floor(Math.random() * alphabet.length)];
  return out;
}

// Styled <select> — native under the hood (keyboard/accessibility for free),
// dressed up with a custom arrow so it matches the rest of the wizard.
function Select({ value, onChange, options, placeholder = '—' }) {
  return (
    <div style={{ position: 'relative' }}>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{ ...inputStyle, appearance: 'none', WebkitAppearance: 'none', paddingRight: 30, cursor: 'pointer' }}
      >
        <option value="">{placeholder}</option>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      <FiChevronDown style={{
        position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
        pointerEvents: 'none', color: '#9a9aa3', fontSize: 14,
      }} />
    </div>
  );
}

function IconInput({ icon: Icon, ...props }) {
  return (
    <div style={{ position: 'relative' }}>
      <Icon style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', color: '#9a9aa3', fontSize: 14 }} />
      <input {...props} style={{ ...inputStyle, paddingLeft: 32 }} />
    </div>
  );
}

function Field({ label, required, children, hint, span }) {
  return (
    <div style={{ marginBottom: 16, gridColumn: span ? `span ${span}` : undefined }}>
      <label style={{ display: 'block', fontSize: 12, fontWeight: 700, color: '#52525b', marginBottom: 6, letterSpacing: 0.1 }}>
        {label}{required && <span style={{ color: '#DC2626' }}> *</span>}
      </label>
      {children}
      {hint && <div style={{ fontSize: 11, color: '#a3a3ab', marginTop: 4 }}>{hint}</div>}
    </div>
  );
}

function Grid({ cols = 2, children }) {
  return <div style={{ display: 'grid', gridTemplateColumns: `repeat(${cols}, minmax(0,1fr))`, gap: '0 16px' }}>{children}</div>;
}

const ATTR_ICON = { gender: FiUser, smoking: FiWind, drinking: FiCoffee, relationship_goal: FiHeart, industry: FiCompass };

function ProfilePreview({ form, options, districtName }) {
  const dp = form.dating_profile;
  const pp = form.professional_profile;
  const initials = (form.display_name || '?').trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join('').toUpperCase() || '?';
  const age = dp.birth_year ? new Date().getFullYear() - Number(dp.birth_year) : null;
  const labelFor = (catalogKey, value) => (options[catalogKey] || []).find((o) => o.value === value)?.label;

  const chips = [];
  if (form.modes.sparks) {
    if (dp.gender) chips.push({ icon: FiUser, text: labelFor('gender', dp.gender) });
    if (dp.relationship_goal) chips.push({ icon: FiHeart, text: labelFor('relationship_goal', dp.relationship_goal) });
    if (dp.smoking && dp.smoking !== 'no') chips.push({ icon: FiWind, text: labelFor('smoking', dp.smoking) });
    if (dp.drinking && dp.drinking !== 'no') chips.push({ icon: FiCoffee, text: labelFor('drinking', dp.drinking) });
  }
  if (form.modes.professional && pp.industry) chips.push({ icon: FiCompass, text: labelFor('industry', pp.industry) });

  const bio = form.modes.sparks && dp.bio ? dp.bio : (form.modes.professional ? pp.bio : '') || dp.bio;

  return (
    <div style={{
      background: 'linear-gradient(165deg, #F5F3FF 0%, #FDF4FF 100%)', borderRadius: 16,
      border: '1px solid #ECE6FB', padding: '22px 18px', display: 'flex', flexDirection: 'column',
      alignItems: 'center', textAlign: 'center', height: '100%', boxSizing: 'border-box',
    }}>
      <div style={{
        width: 76, height: 76, borderRadius: '50%', display: 'grid', placeItems: 'center',
        background: 'linear-gradient(135deg, #7C3AED, #DB2777)', color: '#fff',
        fontSize: 26, fontWeight: 800, boxShadow: '0 8px 24px rgba(124,58,237,0.28)', marginBottom: 14,
      }}>{initials}</div>

      <div style={{ fontWeight: 800, fontSize: 16, color: '#1f1f27' }}>
        {form.display_name || 'New member'}{age ? `, ${age}` : ''}
      </div>
      <div style={{ fontSize: 12.5, color: '#8a8a93', marginBottom: 4 }}>
        @{form.handle || (form.display_name ? form.display_name.toLowerCase().replace(/[^a-z0-9]/g, '') : 'auto-generated')}
      </div>
      <span style={{
        fontSize: 10.5, fontWeight: 700, padding: '2px 9px', borderRadius: 20, marginBottom: 12,
        background: form.app_id === 'abanoonya' ? '#FCE7F3' : '#EDE9FE',
        color: form.app_id === 'abanoonya' ? '#DB2777' : '#5B21B6',
      }}>{form.app_id === 'abanoonya' ? 'Abanoonya Pro' : 'LinkUp'}</span>

      {districtName && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11.5, color: '#8a8a93', marginBottom: 10 }}>
          <FiMapPin size={12} /> {districtName}
        </div>
      )}

      {bio && (
        <div style={{
          fontSize: 12, color: '#52525b', lineHeight: 1.5, marginBottom: 12,
          maxHeight: 60, overflow: 'hidden', fontStyle: 'italic',
        }}>&ldquo;{bio}&rdquo;</div>
      )}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, justifyContent: 'center', marginTop: 'auto' }}>
        {chips.filter((c) => c.text).map((c, i) => (
          <span key={i} style={{
            display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 10.5, fontWeight: 600,
            background: '#fff', border: '1px solid #ECE6FB', borderRadius: 20, padding: '4px 9px', color: '#5B21B6',
          }}><c.icon size={11} /> {c.text}</span>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 6, marginTop: 14 }}>
        {form.modes.professional && (
          <span style={{ fontSize: 10, fontWeight: 700, color: '#7C3AED', background: '#fff', border: '1px solid #ECE6FB', borderRadius: 6, padding: '3px 8px' }}>
            <FiBriefcase size={10} style={{ marginRight: 3, verticalAlign: -1 }} />Professional
          </span>
        )}
        {form.modes.sparks && (
          <span style={{ fontSize: 10, fontWeight: 700, color: '#DB2777', background: '#fff', border: '1px solid #FBCFE8', borderRadius: 6, padding: '3px 8px' }}>
            <FiHeart size={10} style={{ marginRight: 3, verticalAlign: -1 }} />Sparks
          </span>
        )}
      </div>
    </div>
  );
}

export default function CreateAccountModal({ open, onClose, onCreated }) {
  const [form, setForm] = useState(emptyForm);
  const [options, setOptions] = useState({});
  const [districts, setDistricts] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [copied, setCopied] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    if (!open) return;
    setForm(emptyForm);
    setError('');
    setResult(null);
    setCopied(false);
    setStepIndex(0);
    referenceAPI.datingOptions().then((res) => setOptions(dataOf(res) || {})).catch(() => setOptions({}));
    referenceAPI.locations({ level: 'district' }).then((res) => {
      setDistricts([...(dataOf(res) || [])].sort((a, b) => a.name.localeCompare(b.name)));
    }).catch(() => setDistricts([]));
  }, [open]);

  const set = (field, value) => setForm((f) => ({ ...f, [field]: value }));
  const setDating = (field, value) => setForm((f) => ({ ...f, dating_profile: { ...f.dating_profile, [field]: value } }));
  const setPro = (field, value) => setForm((f) => ({ ...f, professional_profile: { ...f.professional_profile, [field]: value } }));
  const setMode = (mode, value) => setForm((f) => ({ ...f, modes: { ...f.modes, [mode]: value } }));
  const optionsFor = (key) => options[key] || [];
  const districtOptions = useMemo(() => districts.map((d) => ({ value: d.id, label: d.name })), [districts]);
  const districtName = districts.find((d) => d.id === form.dating_profile.district_id)?.name;

  const steps = useMemo(() => [
    { key: 'basic', label: 'Basic info', icon: FiUser },
    { key: 'modes', label: 'Modes', icon: FiHeart },
    ...(form.modes.sparks ? [{ key: 'dating', label: 'Dating', icon: FiHeart }] : []),
    ...(form.modes.professional ? [{ key: 'professional', label: 'Professional', icon: FiBriefcase }] : []),
    { key: 'review', label: 'Review', icon: FiCheck },
  ], [form.modes.sparks, form.modes.professional]);

  useEffect(() => {
    if (stepIndex > steps.length - 1) setStepIndex(steps.length - 1);
  }, [steps.length, stepIndex]);

  const step = steps[stepIndex];
  const basicValid = form.display_name.trim() && (form.phone.trim() || form.email.trim());

  const goNext = () => {
    if (step.key === 'basic' && !basicValid) {
      return setError(!form.display_name.trim() ? 'Display name is required.' : 'Enter a phone number or an email address.');
    }
    setError('');
    setStepIndex((i) => Math.min(i + 1, steps.length - 1));
  };
  const goBack = () => { setError(''); setStepIndex((i) => Math.max(i - 1, 0)); };

  const submit = async () => {
    setError('');
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
        payload.dating_profile = Object.fromEntries(Object.entries(form.dating_profile).filter(([, v]) => v !== ''));
      }
      if (form.modes.professional) {
        payload.professional_profile = Object.fromEntries(Object.entries(form.professional_profile).filter(([, v]) => v !== ''));
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

  if (result) {
    return (
      <Modal open={open} onClose={onClose} title="Account created" width={460}
        footer={<button style={btn(true)} onClick={onClose}>Done</button>}>
        <div style={{ textAlign: 'center', paddingTop: 6 }}>
          <div style={{
            width: 72, height: 72, borderRadius: '50%', margin: '0 auto 14px', display: 'grid', placeItems: 'center',
            background: 'linear-gradient(135deg, #7C3AED, #DB2777)', color: '#fff', fontSize: 26, fontWeight: 800,
            boxShadow: '0 10px 28px rgba(124,58,237,0.3)',
          }}>{(result.display_name || '?').trim()[0]?.toUpperCase()}</div>
          <div style={{ fontWeight: 800, fontSize: 16.5 }}>{result.display_name}</div>
          <div style={{ color: '#9a9aa3', fontSize: 13, marginBottom: 18 }}>@{result.handle}</div>
        </div>
        {result.generated_password ? (
          <div style={{ background: '#fafafa', border: '1px solid #ececf1', borderRadius: 10, padding: 14 }}>
            <div style={{ fontSize: 12, color: '#8a8a93', marginBottom: 6 }}>
              Generated password — shown once, not recoverable afterward. Share it securely.
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <code style={{
                flex: 1, background: '#fff', border: '1px solid #d8d8e0', borderRadius: 6,
                padding: '8px 10px', fontSize: 14, fontWeight: 700, letterSpacing: 0.5,
              }}>{result.generated_password}</code>
              <button style={btn(false)} onClick={copyPassword}>{copied ? <FiCheck color="#059669" /> : <FiCopy />}</button>
            </div>
          </div>
        ) : (
          <div style={{ fontSize: 13, color: '#6b6b76', textAlign: 'center' }}>The password you set is active — no need to share anything further.</div>
        )}
      </Modal>
    );
  }

  return (
    <Modal open={open} onClose={onClose} title="New account" width={920}
      footer={<>
        <div style={{ marginRight: 'auto', fontSize: 12, color: '#9a9aa3' }}>Step {stepIndex + 1} of {steps.length}</div>
        {stepIndex > 0 && <button style={btn(false)} onClick={goBack} disabled={saving}><FiChevronLeft /> Back</button>}
        {step.key !== 'review' ? (
          <button style={btn(true)} onClick={goNext}>Next <FiChevronRight /></button>
        ) : (
          <button style={btn(true)} onClick={submit} disabled={saving}>{saving ? 'Creating…' : 'Create account'}</button>
        )}
      </>}>
      <div style={{ display: 'flex', gap: 24 }}>
        <div style={{ width: 220, flexShrink: 0 }}>
          <ProfilePreview form={form} options={options} districtName={districtName} />
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <Stepper steps={steps} activeIndex={stepIndex} onSelect={setStepIndex} />

          {error && (
            <div style={{
              background: '#fef2f2', color: '#DC2626', border: '1px solid #f3c4c4',
              borderRadius: 8, padding: '10px 12px', fontSize: 13, marginBottom: 16,
            }}>{error}</div>
          )}

          {step.key === 'basic' && (
            <div>
              <Field label="Display name" required>
                <IconInput icon={FiUser} value={form.display_name} onChange={(e) => set('display_name', e.target.value)} placeholder="Jane Doe" />
              </Field>
              <Grid cols={2}>
                <Field label="Phone" hint="At least one of phone or email is required">
                  <IconInput icon={FiPhone} value={form.phone} onChange={(e) => set('phone', e.target.value)} placeholder="+256700000000" />
                </Field>
                <Field label="Email">
                  <IconInput icon={FiMail} type="email" value={form.email} onChange={(e) => set('email', e.target.value)} placeholder="jane@example.com" />
                </Field>
                <Field label="Handle" hint="Leave blank to auto-generate">
                  <input style={inputStyle} value={form.handle} onChange={(e) => set('handle', e.target.value.toLowerCase())} placeholder="jane-doe" />
                </Field>
                <Field label="App">
                  <Select value={form.app_id} onChange={(v) => set('app_id', v)} options={[
                    { value: 'linkup', label: 'LinkUp' }, { value: 'abanoonya', label: 'Abanoonya Pro' },
                  ]} />
                </Field>
              </Grid>
              <Field label="Password" hint="Leave blank to generate a random one at creation time">
                <div style={{ display: 'flex', gap: 8 }}>
                  <div style={{ flex: 1 }}><IconInput icon={FiLock} value={form.password} onChange={(e) => set('password', e.target.value)} placeholder="Auto-generated if blank" /></div>
                  <button type="button" style={btn(false)} onClick={() => set('password', generatePassword())} title="Generate a password now">
                    <FiShuffle />
                  </button>
                </div>
              </Field>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, marginTop: 4 }}>
                <input type="checkbox" checked={form.is_premium} onChange={(e) => set('is_premium', e.target.checked)} />
                Grant premium immediately
              </label>
            </div>
          )}

          {step.key === 'modes' && (
            <div>
              <p style={{ fontSize: 13, color: '#6b6b76', marginTop: 0, marginBottom: 18 }}>
                Which parts of the profile should this account have? Each enabled mode gets its own step next.
              </p>
              <div style={{ display: 'flex', gap: 14 }}>
                <ModeCard active={form.modes.professional} icon={FiBriefcase} title="Professional"
                  description="Career profile — headline, seniority, industry."
                  onClick={() => setMode('professional', !form.modes.professional)} color="#7C3AED" />
                <ModeCard active={form.modes.sparks} icon={FiHeart} title="Sparks (dating)"
                  description="Dating profile — bio, preferences, lifestyle."
                  onClick={() => setMode('sparks', !form.modes.sparks)} color="#DB2777" />
              </div>
            </div>
          )}

          {step.key === 'dating' && (
            <div>
              <Field label="Bio">
                <textarea style={{ ...inputStyle, minHeight: 70, resize: 'vertical' }} value={form.dating_profile.bio}
                  onChange={(e) => setDating('bio', e.target.value)} placeholder="A short bio…" />
              </Field>
              <Grid cols={3}>
                <Field label="Gender"><Select value={form.dating_profile.gender} onChange={(v) => setDating('gender', v)} options={optionsFor('gender')} /></Field>
                <Field label="Looking for"><Select value={form.dating_profile.looking_for_gender} onChange={(v) => setDating('looking_for_gender', v)} options={optionsFor('gender')} /></Field>
                <Field label="Orientation"><Select value={form.dating_profile.sexual_orientation} onChange={(v) => setDating('sexual_orientation', v)} options={optionsFor('orientation')} /></Field>
                <Field label="Birth year">
                  <input style={inputStyle} type="number" min="1940" max={new Date().getFullYear() - 18} value={form.dating_profile.birth_year}
                    onChange={(e) => setDating('birth_year', e.target.value ? Number(e.target.value) : '')} placeholder="1998" />
                </Field>
                <Field label="Relationship goal"><Select value={form.dating_profile.relationship_goal} onChange={(v) => setDating('relationship_goal', v)} options={optionsFor('relationship_goal')} /></Field>
                <Field label="Height (cm)">
                  <input style={inputStyle} type="number" min="120" max="230" value={form.dating_profile.height_cm}
                    onChange={(e) => setDating('height_cm', e.target.value ? Number(e.target.value) : '')} placeholder="170" />
                </Field>
                <Field label="Body type"><Select value={form.dating_profile.body_type} onChange={(v) => setDating('body_type', v)} options={optionsFor('body_type')} /></Field>
                <Field label="Smoking"><Select value={form.dating_profile.smoking} onChange={(v) => setDating('smoking', v)} options={optionsFor('smoking')} /></Field>
                <Field label="Drinking"><Select value={form.dating_profile.drinking} onChange={(v) => setDating('drinking', v)} options={optionsFor('drinking')} /></Field>
                <Field label="Marijuana"><Select value={form.dating_profile.marijuana} onChange={(v) => setDating('marijuana', v)} options={optionsFor('marijuana')} /></Field>
                <Field label="Diet"><Select value={form.dating_profile.diet} onChange={(v) => setDating('diet', v)} options={optionsFor('diet')} /></Field>
                <Field label="Exercise"><Select value={form.dating_profile.exercise} onChange={(v) => setDating('exercise', v)} options={optionsFor('exercise')} /></Field>
                <Field label="Education"><Select value={form.dating_profile.education_level} onChange={(v) => setDating('education_level', v)} options={optionsFor('education_level')} /></Field>
                <Field label="Religion"><Select value={form.dating_profile.religion} onChange={(v) => setDating('religion', v)} options={optionsFor('religion')} /></Field>
                <Field label="Tribe / ethnicity"><Select value={form.dating_profile.tribe_ethnicity} onChange={(v) => setDating('tribe_ethnicity', v)} options={optionsFor('tribe')} /></Field>
                <Field label="Industry"><Select value={form.dating_profile.industry} onChange={(v) => setDating('industry', v)} options={optionsFor('industry')} /></Field>
                <Field label="District"><Select value={form.dating_profile.district_id} onChange={(v) => setDating('district_id', v)} options={districtOptions} /></Field>
                <Field label="Max distance (km)">
                  <input style={inputStyle} type="number" min="1" max="500" value={form.dating_profile.max_distance_km}
                    onChange={(e) => setDating('max_distance_km', e.target.value ? Number(e.target.value) : '')} placeholder="50" />
                </Field>
              </Grid>
            </div>
          )}

          {step.key === 'professional' && (
            <div>
              <Grid cols={2}>
                <Field label="Headline"><input style={inputStyle} value={form.professional_profile.headline} onChange={(e) => setPro('headline', e.target.value)} placeholder="Software Engineer at Acme" /></Field>
                <Field label="Current role"><input style={inputStyle} value={form.professional_profile.current_role} onChange={(e) => setPro('current_role', e.target.value)} placeholder="Backend Engineer" /></Field>
              </Grid>
              <Field label="Bio">
                <textarea style={{ ...inputStyle, minHeight: 70, resize: 'vertical' }} value={form.professional_profile.bio}
                  onChange={(e) => setPro('bio', e.target.value)} placeholder="A short professional bio…" />
              </Field>
              <Grid cols={3}>
                <Field label="Seniority"><Select value={form.professional_profile.seniority} onChange={(v) => setPro('seniority', v)} options={SENIORITY.map((s) => ({ value: s, label: s[0].toUpperCase() + s.slice(1) }))} /></Field>
                <Field label="Industry"><Select value={form.professional_profile.industry} onChange={(v) => setPro('industry', v)} options={optionsFor('industry')} /></Field>
                <Field label="Years of experience">
                  <input style={inputStyle} type="number" min="0" max="60" value={form.professional_profile.years_experience}
                    onChange={(e) => setPro('years_experience', e.target.value ? Number(e.target.value) : '')} placeholder="5" />
                </Field>
                <Field label="Pronouns"><input style={inputStyle} value={form.professional_profile.pronouns} onChange={(e) => setPro('pronouns', e.target.value)} placeholder="she/her" /></Field>
                <Field label="Tagline"><input style={inputStyle} value={form.professional_profile.tagline} onChange={(e) => setPro('tagline', e.target.value)} placeholder="Building things that matter" /></Field>
                <Field label="Availability"><Select value={form.professional_profile.availability_status} onChange={(v) => setPro('availability_status', v)} options={AVAILABILITY} /></Field>
              </Grid>
            </div>
          )}

          {step.key === 'review' && (
            <ReviewStep form={form} options={options} districtName={districtName} />
          )}
        </div>
      </div>
    </Modal>
  );
}

function ModeCard({ active, icon: Icon, title, description, onClick, color }) {
  return (
    <button type="button" onClick={onClick} style={{
      flex: 1, textAlign: 'left', padding: 16, borderRadius: 12, cursor: 'pointer',
      border: active ? `2px solid ${color}` : '2px solid #ececf1',
      background: active ? `${color}0d` : '#fff', transition: 'all 0.15s ease',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
        <div style={{
          width: 32, height: 32, borderRadius: 9, display: 'grid', placeItems: 'center',
          background: active ? color : '#f3f3f6', color: active ? '#fff' : '#9a9aa3', flexShrink: 0,
        }}><Icon size={16} /></div>
        <div style={{ fontWeight: 800, fontSize: 14 }}>{title}</div>
        <div style={{
          marginLeft: 'auto', width: 18, height: 18, borderRadius: '50%',
          border: active ? `5px solid ${color}` : '2px solid #d8d8e0', flexShrink: 0,
        }} />
      </div>
      <div style={{ fontSize: 12, color: '#8a8a93', lineHeight: 1.4 }}>{description}</div>
    </button>
  );
}

function ReviewRow({ label, value }) {
  if (!value && value !== 0) return null;
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderBottom: '1px solid #f3f3f6', fontSize: 13 }}>
      <span style={{ color: '#8a8a93' }}>{label}</span>
      <span style={{ fontWeight: 600, textAlign: 'right' }}>{value}</span>
    </div>
  );
}

function ReviewStep({ form, options, districtName }) {
  const labelFor = (catalogKey, value) => (options[catalogKey] || []).find((o) => o.value === value)?.label || value;
  return (
    <div>
      <p style={{ fontSize: 13, color: '#6b6b76', marginTop: 0 }}>Everything looks right? Create the account to finish.</p>
      <div style={{ background: '#fafafa', border: '1px solid #ececf1', borderRadius: 10, padding: '4px 14px', marginBottom: 14 }}>
        <ReviewRow label="Display name" value={form.display_name} />
        <ReviewRow label="Handle" value={form.handle || 'auto-generated'} />
        <ReviewRow label="Phone" value={form.phone} />
        <ReviewRow label="Email" value={form.email} />
        <ReviewRow label="App" value={form.app_id === 'abanoonya' ? 'Abanoonya Pro' : 'LinkUp'} />
        <ReviewRow label="Password" value={form.password ? 'Set explicitly' : 'Will be generated'} />
        <ReviewRow label="Premium" value={form.is_premium ? 'Yes' : 'No'} />
      </div>
      {form.modes.sparks && (
        <>
          <div style={{ fontWeight: 800, fontSize: 12.5, color: '#DB2777', margin: '14px 0 6px' }}>Dating profile</div>
          <div style={{ background: '#fafafa', border: '1px solid #ececf1', borderRadius: 10, padding: '4px 14px', marginBottom: 14 }}>
            <ReviewRow label="Bio" value={form.dating_profile.bio} />
            <ReviewRow label="Gender" value={labelFor('gender', form.dating_profile.gender)} />
            <ReviewRow label="Looking for" value={labelFor('gender', form.dating_profile.looking_for_gender)} />
            <ReviewRow label="Birth year" value={form.dating_profile.birth_year} />
            <ReviewRow label="Relationship goal" value={labelFor('relationship_goal', form.dating_profile.relationship_goal)} />
            <ReviewRow label="District" value={districtName} />
          </div>
        </>
      )}
      {form.modes.professional && (
        <>
          <div style={{ fontWeight: 800, fontSize: 12.5, color: '#7C3AED', margin: '14px 0 6px' }}>Professional profile</div>
          <div style={{ background: '#fafafa', border: '1px solid #ececf1', borderRadius: 10, padding: '4px 14px' }}>
            <ReviewRow label="Headline" value={form.professional_profile.headline} />
            <ReviewRow label="Seniority" value={form.professional_profile.seniority} />
            <ReviewRow label="Industry" value={labelFor('industry', form.professional_profile.industry)} />
            <ReviewRow label="Years of experience" value={form.professional_profile.years_experience} />
          </div>
        </>
      )}
    </div>
  );
}

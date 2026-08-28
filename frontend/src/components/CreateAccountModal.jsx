import React, { useEffect, useRef, useState } from 'react';
import { adminAPI, referenceAPI, dataOf } from '../services/api';
import {
  FiCopy, FiCheck, FiUser, FiPhone, FiMail, FiLock, FiHeart, FiBriefcase,
  FiShuffle, FiChevronDown, FiCamera, FiX, FiAlertTriangle,
} from 'react-icons/fi';
import { Modal, btn } from './adminUi';

const SENIORITY = ['entry', 'mid', 'senior', 'lead', 'executive'];
const AVAILABILITY = [
  { value: 'open', label: 'Open to opportunities' },
  { value: 'casually_looking', label: 'Casually looking' },
  { value: 'not_looking', label: 'Not looking' },
];
const PHOTO_SLOTS = 6;

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

// Compact form chrome — deliberately tighter than the rest of the admin
// console's forms so a lot of fields fit without paging through steps.
const compactInput = {
  width: '100%', padding: '6px 9px', borderRadius: 7, border: '1px solid #d8d8e0',
  fontSize: 12.5, fontFamily: 'inherit', boxSizing: 'border-box', background: '#fff', color: '#18181b',
};

function Field({ label, required, children, hint }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: '#6b6b76', marginBottom: 3 }}>
        {label}{required && <span style={{ color: '#DC2626' }}> *</span>}
      </label>
      {children}
      {hint && <div style={{ fontSize: 10, color: '#a3a3ab', marginTop: 2 }}>{hint}</div>}
    </div>
  );
}

function Grid({ cols = 2, children }) {
  return <div style={{ display: 'grid', gridTemplateColumns: `repeat(${cols}, minmax(0,1fr))`, gap: '0 12px' }}>{children}</div>;
}

function SectionHeading({ children, color = '#18181b' }) {
  return <div style={{ fontWeight: 800, fontSize: 12.5, color, textTransform: 'uppercase', letterSpacing: 0.4, margin: '4px 0 8px' }}>{children}</div>;
}

function Select({ value, onChange, options, placeholder = '—' }) {
  return (
    <div style={{ position: 'relative' }}>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{ ...compactInput, appearance: 'none', WebkitAppearance: 'none', paddingRight: 24, cursor: 'pointer' }}
      >
        <option value="">{placeholder}</option>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      <FiChevronDown style={{ position: 'absolute', right: 7, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', color: '#9a9aa3', fontSize: 12 }} />
    </div>
  );
}

function IconInput({ icon: Icon, ...props }) {
  return (
    <div style={{ position: 'relative' }}>
      <Icon style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: '#9a9aa3', fontSize: 12 }} />
      <input {...props} style={{ ...compactInput, paddingLeft: 26 }} />
    </div>
  );
}

// One drag-and-drop photo slot. Slot 0 (main) renders as a circle; the rest
// as rounded squares. Click or drop to fill; the × removes it.
function PhotoSlot({ slot, onFile, onRemove, primary }) {
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);
  const size = primary ? 92 : 68;

  const accept = (files) => {
    const file = files?.[0];
    if (file && file.type.startsWith('image/')) onFile(file);
  };

  return (
    <div
      onClick={() => !slot && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => { e.preventDefault(); e.stopPropagation(); setDragOver(false); accept(e.dataTransfer.files); }}
      title={primary ? 'Main / profile photo' : 'Gallery photo'}
      style={{
        width: size, height: size, borderRadius: primary ? '50%' : 10, flexShrink: 0,
        border: `2px dashed ${dragOver ? '#7C3AED' : slot ? 'transparent' : '#d8d8e0'}`,
        background: slot ? `#000 url(${slot.previewUrl}) center/cover no-repeat` : dragOver ? '#F5F3FF' : '#fafafa',
        display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
        position: 'relative', transition: 'all 0.15s ease',
      }}
    >
      <input ref={inputRef} type="file" accept="image/*" style={{ display: 'none' }}
        onChange={(e) => accept(e.target.files)} />
      {!slot && <FiCamera color="#b3b3bb" size={primary ? 22 : 15} />}
      {slot && (
        <button type="button" onClick={(e) => { e.stopPropagation(); onRemove(); }} style={{
          position: 'absolute', top: -5, right: -5, width: 18, height: 18, borderRadius: '50%',
          background: '#DC2626', color: '#fff', border: '2px solid #fff', cursor: 'pointer',
          display: 'grid', placeItems: 'center', padding: 0, lineHeight: 1,
        }}><FiX size={10} /></button>
      )}
    </div>
  );
}

export default function CreateAccountModal({ open, onClose, onCreated }) {
  const [form, setForm] = useState(emptyForm);
  const [photos, setPhotos] = useState(Array(PHOTO_SLOTS).fill(null));
  const [options, setOptions] = useState({});
  const [districts, setDistricts] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [copied, setCopied] = useState(false);
  const [dropAreaOver, setDropAreaOver] = useState(false);

  // Tracks the current photos array without making it an effect dependency —
  // putting `photos` directly in a cleanup-effect's deps would revoke each
  // slot's object URL the moment ANY other slot changes (cleanup runs before
  // every re-run, not just on unmount), breaking already-filled previews.
  const photosRef = useRef(photos);
  photosRef.current = photos;

  useEffect(() => {
    if (!open) return;
    // Starting a fresh session — release any URLs left over from last time.
    photosRef.current.forEach((p) => p && URL.revokeObjectURL(p.previewUrl));
    setForm(emptyForm);
    setPhotos(Array(PHOTO_SLOTS).fill(null));
    setError('');
    setResult(null);
    setCopied(false);
    referenceAPI.datingOptions().then((res) => setOptions(dataOf(res) || {})).catch(() => setOptions({}));
    referenceAPI.locations({ level: 'district' }).then((res) => {
      setDistricts([...(dataOf(res) || [])].sort((a, b) => a.name.localeCompare(b.name)));
    }).catch(() => setDistricts([]));
  }, [open]);

  // Release any remaining object URLs when the component itself unmounts
  // (navigating away from the Accounts page entirely).
  useEffect(() => () => photosRef.current.forEach((p) => p && URL.revokeObjectURL(p.previewUrl)), []);

  const set = (field, value) => setForm((f) => ({ ...f, [field]: value }));
  const setDating = (field, value) => setForm((f) => ({ ...f, dating_profile: { ...f.dating_profile, [field]: value } }));
  const setPro = (field, value) => setForm((f) => ({ ...f, professional_profile: { ...f.professional_profile, [field]: value } }));
  const setMode = (mode, value) => setForm((f) => ({ ...f, modes: { ...f.modes, [mode]: value } }));
  const optionsFor = (key) => options[key] || [];
  const districtOptions = districts.map((d) => ({ value: d.id, label: d.name }));

  const fillSlot = (index, file) => {
    setPhotos((prev) => {
      const next = [...prev];
      if (next[index]) URL.revokeObjectURL(next[index].previewUrl);
      next[index] = { file, previewUrl: URL.createObjectURL(file) };
      return next;
    });
  };
  const clearSlot = (index) => {
    setPhotos((prev) => {
      const next = [...prev];
      if (next[index]) URL.revokeObjectURL(next[index].previewUrl);
      next[index] = null;
      return next;
    });
  };
  const distributeFiles = (fileList) => {
    const files = Array.from(fileList).filter((f) => f.type.startsWith('image/'));
    if (!files.length) return;
    setPhotos((prev) => {
      const next = [...prev];
      let fi = 0;
      for (let i = 0; i < next.length && fi < files.length; i++) {
        if (!next[i]) { next[i] = { file: files[fi], previewUrl: URL.createObjectURL(files[fi]) }; fi++; }
      }
      return next;
    });
  };

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
        payload.dating_profile = Object.fromEntries(Object.entries(form.dating_profile).filter(([, v]) => v !== ''));
      }
      if (form.modes.professional) {
        payload.professional_profile = Object.fromEntries(Object.entries(form.professional_profile).filter(([, v]) => v !== ''));
      }
      const res = await adminAPI.accountCreate(payload);
      const created = dataOf(res);

      // Photos are uploaded after the account exists — a failure here
      // shouldn't undo a successful account creation, just get reported.
      let photoFailures = 0;
      for (let i = 0; i < photos.length; i++) {
        const slot = photos[i];
        if (!slot) continue;
        try {
          const fd = new FormData();
          fd.append('photo', slot.file);
          if (i === 0) fd.append('is_profile_photo', 'true');
          await adminAPI.accountPhotoUpload(created.id, fd);
        } catch (_) {
          photoFailures++;
        }
      }

      setResult({ ...created, photoFailures, photoTotal: photos.filter(Boolean).length });
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
            width: 72, height: 72, borderRadius: '50%', margin: '0 auto 14px', overflow: 'hidden',
            display: 'grid', placeItems: 'center', background: photos[0]
              ? `url(${photos[0].previewUrl}) center/cover` : 'linear-gradient(135deg, #7C3AED, #DB2777)',
            color: '#fff', fontSize: 26, fontWeight: 800, boxShadow: '0 10px 28px rgba(124,58,237,0.3)',
          }}>{!photos[0] && (result.display_name || '?').trim()[0]?.toUpperCase()}</div>
          <div style={{ fontWeight: 800, fontSize: 16.5 }}>{result.display_name}</div>
          <div style={{ color: '#9a9aa3', fontSize: 13, marginBottom: 14 }}>@{result.handle}</div>
        </div>

        {result.photoTotal > 0 && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, marginBottom: 14,
            color: result.photoFailures ? '#C2410C' : '#059669',
          }}>
            {result.photoFailures ? <FiAlertTriangle /> : <FiCheck />}
            {result.photoFailures
              ? `${result.photoTotal - result.photoFailures} of ${result.photoTotal} photos uploaded — ${result.photoFailures} failed. You can add them later from the account's gallery.`
              : `${result.photoTotal} photo${result.photoTotal > 1 ? 's' : ''} uploaded.`}
          </div>
        )}

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
    <Modal open={open} onClose={onClose} title="New account" width={1180}
      footer={<>
        <button style={btn(false)} onClick={onClose} disabled={saving}>Cancel</button>
        <button style={btn(true)} onClick={submit} disabled={saving}>{saving ? 'Creating…' : 'Create account'}</button>
      </>}>
      {error && (
        <div style={{
          background: '#fef2f2', color: '#DC2626', border: '1px solid #f3c4c4',
          borderRadius: 8, padding: '9px 12px', fontSize: 12.5, marginBottom: 14,
        }}>{error}</div>
      )}

      <SectionHeading>Basic info</SectionHeading>
      <Grid cols={4}>
        <Field label="Display name" required><IconInput icon={FiUser} value={form.display_name} onChange={(e) => set('display_name', e.target.value)} placeholder="Jane Doe" /></Field>
        <Field label="Phone" hint="Phone or email required"><IconInput icon={FiPhone} value={form.phone} onChange={(e) => set('phone', e.target.value)} placeholder="+256700000000" /></Field>
        <Field label="Email"><IconInput icon={FiMail} type="email" value={form.email} onChange={(e) => set('email', e.target.value)} placeholder="jane@example.com" /></Field>
        <Field label="Handle" hint="Auto-generated if blank"><input style={compactInput} value={form.handle} onChange={(e) => set('handle', e.target.value.toLowerCase())} placeholder="jane-doe" /></Field>
      </Grid>
      <Grid cols={4}>
        <Field label="App">
          <Select value={form.app_id} onChange={(v) => set('app_id', v)} options={[{ value: 'linkup', label: 'LinkUp' }, { value: 'abanoonya', label: 'Abanoonya Pro' }]} />
        </Field>
        <Field label="Password" hint="Auto-generated if blank">
          <div style={{ display: 'flex', gap: 6 }}>
            <div style={{ flex: 1 }}><IconInput icon={FiLock} value={form.password} onChange={(e) => set('password', e.target.value)} placeholder="•••••••••" /></div>
            <button type="button" style={{ ...btn(false), padding: '6px 9px' }} onClick={() => set('password', generatePassword())} title="Generate now"><FiShuffle size={12} /></button>
          </div>
        </Field>
        <Field label="Premium">
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.5, height: 30 }}>
            <input type="checkbox" checked={form.is_premium} onChange={(e) => set('is_premium', e.target.checked)} /> Grant immediately
          </label>
        </Field>
        <div />
      </Grid>

      <SectionHeading color="#7C3AED">Photos</SectionHeading>
      <div
        onDragOver={(e) => { e.preventDefault(); setDropAreaOver(true); }}
        onDragLeave={() => setDropAreaOver(false)}
        onDrop={(e) => { e.preventDefault(); setDropAreaOver(false); distributeFiles(e.dataTransfer.files); }}
        style={{
          display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', borderRadius: 12,
          background: dropAreaOver ? '#F5F3FF' : '#fafafa', border: `1.5px dashed ${dropAreaOver ? '#7C3AED' : '#ececf1'}`,
          marginBottom: 16, transition: 'all 0.15s ease',
        }}
      >
        {photos.map((slot, i) => (
          <PhotoSlot key={i} slot={slot} primary={i === 0} onFile={(f) => fillSlot(i, f)} onRemove={() => clearSlot(i)} />
        ))}
        <div style={{ fontSize: 11, color: '#9a9aa3', marginLeft: 6, lineHeight: 1.5, maxWidth: 160 }}>
          Drag & drop up to {PHOTO_SLOTS} photos here, or click a slot. First one becomes the profile photo.
        </div>
      </div>

      <SectionHeading>Modes</SectionHeading>
      <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
        <ModeToggle active={form.modes.professional} icon={FiBriefcase} title="Professional" color="#7C3AED" onClick={() => setMode('professional', !form.modes.professional)} />
        <ModeToggle active={form.modes.sparks} icon={FiHeart} title="Sparks (dating)" color="#DB2777" onClick={() => setMode('sparks', !form.modes.sparks)} />
      </div>

      {form.modes.sparks && (
        <>
          <SectionHeading color="#DB2777">Dating profile</SectionHeading>
          <Field label="Bio">
            <textarea style={{ ...compactInput, minHeight: 46, resize: 'vertical' }} value={form.dating_profile.bio}
              onChange={(e) => setDating('bio', e.target.value)} placeholder="A short bio…" />
          </Field>
          <Grid cols={6}>
            <Field label="Gender"><Select value={form.dating_profile.gender} onChange={(v) => setDating('gender', v)} options={optionsFor('gender')} /></Field>
            <Field label="Looking for"><Select value={form.dating_profile.looking_for_gender} onChange={(v) => setDating('looking_for_gender', v)} options={optionsFor('gender')} /></Field>
            <Field label="Orientation"><Select value={form.dating_profile.sexual_orientation} onChange={(v) => setDating('sexual_orientation', v)} options={optionsFor('orientation')} /></Field>
            <Field label="Birth year"><input style={compactInput} type="number" min="1940" max={new Date().getFullYear() - 18} value={form.dating_profile.birth_year} onChange={(e) => setDating('birth_year', e.target.value ? Number(e.target.value) : '')} placeholder="1998" /></Field>
            <Field label="Goal"><Select value={form.dating_profile.relationship_goal} onChange={(v) => setDating('relationship_goal', v)} options={optionsFor('relationship_goal')} /></Field>
            <Field label="Height (cm)"><input style={compactInput} type="number" min="120" max="230" value={form.dating_profile.height_cm} onChange={(e) => setDating('height_cm', e.target.value ? Number(e.target.value) : '')} placeholder="170" /></Field>
            <Field label="Body type"><Select value={form.dating_profile.body_type} onChange={(v) => setDating('body_type', v)} options={optionsFor('body_type')} /></Field>
            <Field label="Smoking"><Select value={form.dating_profile.smoking} onChange={(v) => setDating('smoking', v)} options={optionsFor('smoking')} /></Field>
            <Field label="Drinking"><Select value={form.dating_profile.drinking} onChange={(v) => setDating('drinking', v)} options={optionsFor('drinking')} /></Field>
            <Field label="Marijuana"><Select value={form.dating_profile.marijuana} onChange={(v) => setDating('marijuana', v)} options={optionsFor('marijuana')} /></Field>
            <Field label="Diet"><Select value={form.dating_profile.diet} onChange={(v) => setDating('diet', v)} options={optionsFor('diet')} /></Field>
            <Field label="Exercise"><Select value={form.dating_profile.exercise} onChange={(v) => setDating('exercise', v)} options={optionsFor('exercise')} /></Field>
            <Field label="Education"><Select value={form.dating_profile.education_level} onChange={(v) => setDating('education_level', v)} options={optionsFor('education_level')} /></Field>
            <Field label="Religion"><Select value={form.dating_profile.religion} onChange={(v) => setDating('religion', v)} options={optionsFor('religion')} /></Field>
            <Field label="Tribe"><Select value={form.dating_profile.tribe_ethnicity} onChange={(v) => setDating('tribe_ethnicity', v)} options={optionsFor('tribe')} /></Field>
            <Field label="Industry"><Select value={form.dating_profile.industry} onChange={(v) => setDating('industry', v)} options={optionsFor('industry')} /></Field>
            <Field label="District"><Select value={form.dating_profile.district_id} onChange={(v) => setDating('district_id', v)} options={districtOptions} /></Field>
            <Field label="Max dist. (km)"><input style={compactInput} type="number" min="1" max="500" value={form.dating_profile.max_distance_km} onChange={(e) => setDating('max_distance_km', e.target.value ? Number(e.target.value) : '')} placeholder="50" /></Field>
          </Grid>
        </>
      )}

      {form.modes.professional && (
        <>
          <SectionHeading>Professional profile</SectionHeading>
          <Grid cols={3}>
            <Field label="Headline"><input style={compactInput} value={form.professional_profile.headline} onChange={(e) => setPro('headline', e.target.value)} placeholder="Software Engineer at Acme" /></Field>
            <Field label="Current role"><input style={compactInput} value={form.professional_profile.current_role} onChange={(e) => setPro('current_role', e.target.value)} placeholder="Backend Engineer" /></Field>
            <Field label="Tagline"><input style={compactInput} value={form.professional_profile.tagline} onChange={(e) => setPro('tagline', e.target.value)} placeholder="Building things that matter" /></Field>
          </Grid>
          <Field label="Bio">
            <textarea style={{ ...compactInput, minHeight: 46, resize: 'vertical' }} value={form.professional_profile.bio}
              onChange={(e) => setPro('bio', e.target.value)} placeholder="A short professional bio…" />
          </Field>
          <Grid cols={5}>
            <Field label="Seniority"><Select value={form.professional_profile.seniority} onChange={(v) => setPro('seniority', v)} options={SENIORITY.map((s) => ({ value: s, label: s[0].toUpperCase() + s.slice(1) }))} /></Field>
            <Field label="Industry"><Select value={form.professional_profile.industry} onChange={(v) => setPro('industry', v)} options={optionsFor('industry')} /></Field>
            <Field label="Years exp."><input style={compactInput} type="number" min="0" max="60" value={form.professional_profile.years_experience} onChange={(e) => setPro('years_experience', e.target.value ? Number(e.target.value) : '')} placeholder="5" /></Field>
            <Field label="Pronouns"><input style={compactInput} value={form.professional_profile.pronouns} onChange={(e) => setPro('pronouns', e.target.value)} placeholder="she/her" /></Field>
            <Field label="Availability"><Select value={form.professional_profile.availability_status} onChange={(v) => setPro('availability_status', v)} options={AVAILABILITY} /></Field>
          </Grid>
        </>
      )}
    </Modal>
  );
}

function ModeToggle({ active, icon: Icon, title, color, onClick }) {
  return (
    <button type="button" onClick={onClick} style={{
      display: 'flex', alignItems: 'center', gap: 8, padding: '7px 14px', borderRadius: 20, cursor: 'pointer',
      border: active ? `1.5px solid ${color}` : '1.5px solid #ececf1',
      background: active ? `${color}12` : '#fff', color: active ? color : '#8a8a93',
      fontSize: 12.5, fontWeight: 700, transition: 'all 0.15s ease',
    }}>
      <Icon size={13} /> {title}
    </button>
  );
}

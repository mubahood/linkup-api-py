import React, { useEffect, useRef, useState } from 'react';
import imageCompression from 'browser-image-compression';
import { adminAPI, referenceAPI, dataOf } from '../services/api';
import {
  FiCopy, FiCheck, FiUser, FiPhone, FiMail, FiLock, FiHeart, FiBriefcase,
  FiShuffle, FiChevronDown, FiCamera, FiX, FiAlertTriangle, FiLoader,
} from 'react-icons/fi';
import { Modal, btn } from './adminUi';

// Mirrors backend/shared/storage/image_compress.py's own numbers (1920px,
// WebP ~85%) so a photo looks the same regardless of which side ends up
// doing the real work — the backend re-compresses unconditionally anyway
// (never trust the client alone), so this is purely about cutting upload
// time/bandwidth for whoever's on the slow end of the connection, which for
// a multi-MB phone-camera photo is substantial.
const CLIENT_COMPRESS_OPTIONS = {
  maxSizeMB: 2, maxWidthOrHeight: 1920, useWebWorker: true,
  fileType: 'image/webp', initialQuality: 0.85,
};

async function compressForUpload(file) {
  try {
    const out = await imageCompression(file, CLIENT_COMPRESS_OPTIONS);
    if (out.size >= file.size) return { file, savedPct: 0 }; // never make it worse
    const named = new File([out], file.name.replace(/\.\w+$/, '') + '.webp', { type: 'image/webp' });
    return { file: named, savedPct: Math.round((1 - out.size / file.size) * 100) };
  } catch (e) {
    console.warn('Client-side image compression failed, uploading the original instead:', e);
    return { file, savedPct: 0 };
  }
}

// Not catalog-backed on mobile either — profile_wizard_screen.dart defines
// these 5 inline (WizardOption, not a dating-options catalogKey), so this
// list is a mirror of that file, same as every catalogKey field mirrors
// GET /v1/reference/dating-options.
const INTENT_OPTIONS = [
  { value: 'open', label: '🔓 Open to anything' },
  { value: 'relationship', label: '💍 Relationship' },
  { value: 'casual', label: '✨ Casual & fun' },
  { value: 'friends', label: '🤝 New friends' },
  { value: 'marriage', label: '💒 Marriage' },
];

const SENIORITY = ['entry', 'mid', 'senior', 'lead', 'executive'];
const AVAILABILITY = [
  { value: 'open', label: 'Open to opportunities' },
  { value: 'casually_looking', label: 'Casually looking' },
  { value: 'not_looking', label: 'Not looking' },
];
const PHOTO_SLOTS = 10;

// LinkUp is a dating app first — Sparks is the default profile type for a
// newly created account, not Professional.
const ACCOUNT_STATUSES = [
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
  { value: 'suspended', label: 'Suspended' },
  { value: 'closed', label: 'Closed' },
];
const STATUS_COLORS = { active: '#059669', inactive: '#71717a', suspended: '#DC2626', closed: '#52525b' };

const emptyForm = {
  display_name: '', handle: '', phone: '', email: '', password: '',
  app_id: 'linkup', is_premium: false, account_status: 'active',
  modes: { professional: false, sparks: true },
  dating_profile: {
    bio: '', gender: '', looking_for_gender: '', sexual_orientation: '',
    birth_year: '', relationship_goal: '', height_cm: '', body_type: '',
    smoking: '', drinking: '', marijuana: '', diet: '', exercise: '',
    education_level: '', religion: '', tribe_ethnicity: '', industry: '',
    district_id: '', max_distance_km: '',
    // Collected by profile_wizard_screen.dart but missing here until this
    // audit — an admin couldn't set what a member's own wizard can.
    intent: '', has_children: '', wants_children: '', pets: '',
    religiosity: '', politics: '', zodiac: '', personality_type: '',
    communication_style: '', languages_spoken: [], love_languages: [],
  },
  professional_profile: {
    headline: '', bio: '', seniority: '', current_role: '', industry: '',
    years_experience: '', pronouns: '', tagline: '', availability_status: '',
  },
};

function buildFormFromAccount(account) {
  if (!account) return { ...emptyForm, dating_profile: { ...emptyForm.dating_profile }, professional_profile: { ...emptyForm.professional_profile } };
  const dp = account.dating_profile || {};
  const pp = account.professional_profile || {};
  return {
    display_name: account.display_name || '',
    handle: account.handle || '',
    phone: account.phone || '',
    email: account.email || '',
    password: '',
    app_id: account.app_id || 'linkup',
    is_premium: !!account.is_premium,
    account_status: account.account_status || 'active',
    modes: {
      professional: !!account.modes_enabled?.professional,
      sparks: !!account.modes_enabled?.sparks,
    },
    dating_profile: {
      bio: dp.bio || '', gender: dp.gender || '', looking_for_gender: dp.looking_for_gender || '',
      sexual_orientation: dp.sexual_orientation || '', birth_year: dp.birth_year || '',
      relationship_goal: dp.relationship_goal || '', height_cm: dp.height_cm || '',
      body_type: dp.body_type || '', smoking: dp.smoking || '', drinking: dp.drinking || '',
      marijuana: dp.marijuana || '', diet: dp.diet || '', exercise: dp.exercise || '',
      education_level: dp.education_level || '', religion: dp.religion || '',
      tribe_ethnicity: dp.tribe_ethnicity || '', industry: dp.industry || '',
      district_id: dp.district_id || '', max_distance_km: dp.max_distance_km || '',
      intent: dp.intent || '', has_children: dp.has_children || '',
      wants_children: dp.wants_children || '', pets: dp.pets || '',
      religiosity: dp.religiosity || '', politics: dp.politics || '',
      zodiac: dp.zodiac || '', personality_type: dp.personality_type || '',
      communication_style: dp.communication_style || '',
      languages_spoken: dp.languages_spoken || [], love_languages: dp.love_languages || [],
    },
    professional_profile: {
      headline: pp.headline || '', bio: pp.bio || '', seniority: pp.seniority || '',
      current_role: pp.current_role || '', industry: pp.industry || '',
      years_experience: pp.years_experience || '', pronouns: pp.pronouns || '',
      tagline: pp.tagline || '', availability_status: pp.availability_status || '',
    },
  };
}

/**
 * Dragging an image FROM another webpage (not a local file) never puts
 * anything in `dataTransfer.files` — the browser only hands over the
 * image's own URL, in whichever of these three slots it felt like filling.
 * Checked in order of reliability: uri-list is the real drag-a-link/image
 * MIME type most browsers set; text/html is what's left when a page drags
 * an <img> element itself (Chrome does this); text/plain is the fallback
 * some sites use for a bare URL. Works identically for a paste (Ctrl+V) of
 * a copied image, since ClipboardEvent.clipboardData has the same shape.
 */
function extractImageUrlsFromDataTransfer(dt) {
  if (!dt) return [];
  const urls = [];

  const uriList = dt.getData?.('text/uri-list');
  if (uriList) {
    uriList.split('\n').map((s) => s.trim()).filter((s) => s && !s.startsWith('#')).forEach((u) => urls.push(u));
  }
  if (!urls.length) {
    const html = dt.getData?.('text/html');
    if (html) {
      const re = /<img[^>]+src=["']([^"']+)["']/gi;
      let m;
      while ((m = re.exec(html))) urls.push(m[1]);
    }
  }
  if (!urls.length) {
    const plain = (dt.getData?.('text/plain') || '').trim();
    if (plain) urls.push(plain);
  }

  // Only genuine http(s) URLs are worth sending to the backend — a relative
  // path or data: URI dragged from somewhere odd can't be fetched server-side.
  return [...new Set(urls)].filter((u) => /^https?:\/\//i.test(u));
}

function buildPhotoSlots(account) {
  const slots = Array(PHOTO_SLOTS).fill(null);
  (account?.photos || []).slice(0, PHOTO_SLOTS).forEach((p, i) => {
    slots[i] = { kind: 'existing', id: p.id, url: p.url };
  });
  return slots;
}

// Pasting a phone number often carries spaces, dashes, parens, or dots from
// wherever it was copied ("+256 700-000 000", "(256) 700.000.000") — this
// strips all of that down to digits (keeping a leading + for the country
// code) so what actually gets typed/pasted always lands clean, without the
// admin needing to notice and fix it themselves.
function cleanPhone(raw) {
  if (!raw) return raw;
  const hasPlus = raw.trim().startsWith('+');
  const digits = raw.replace(/\D/g, '');
  return (hasPlus ? '+' : '') + digits;
}

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

function SectionHeading({ children, color = '#18181b', style }) {
  return <div style={{ fontWeight: 800, fontSize: 12.5, color, textTransform: 'uppercase', letterSpacing: 0.4, margin: '4px 0 8px', ...style }}>{children}</div>;
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

// languages_spoken / love_languages are FieldType.multi on the mobile wizard
// (an array column, not a scalar) — Select can't represent that, so this is
// its multi-value twin: same option source (optionsFor), toggle-able chips
// instead of a dropdown.
function MultiChipSelect({ value, onChange, options }) {
  const selected = value || [];
  const toggle = (v) => onChange(selected.includes(v) ? selected.filter((x) => x !== v) : [...selected, v]);
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
      {options.map((o) => {
        const active = selected.includes(o.value);
        return (
          <button key={o.value} type="button" onClick={() => toggle(o.value)} style={{
            padding: '3px 9px', borderRadius: 12, cursor: 'pointer', fontSize: 11, fontWeight: 600,
            border: active ? '1.5px solid #7C3AED' : '1.5px solid #ececf1',
            background: active ? '#7C3AED14' : '#fff', color: active ? '#7C3AED' : '#8a8a93',
          }}>{o.label}</button>
        );
      })}
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

// One drag-and-drop photo slot. `slot` is one of:
//   {kind:'existing', id, url}         — already saved
//   {kind:'new', file, previewUrl}     — a local file, not yet uploaded
//   {kind:'new-url', url, previewUrl}  — dragged/pasted from another
//                                        webpage; previewUrl === url, since
//                                        <img src> can display any public
//                                        image regardless of CORS — only
//                                        fetch()/canvas reads are blocked,
//                                        and the actual download happens
//                                        server-side on save (see
//                                        backend/shared/storage/url_fetch.py)
//   null                                — empty
function PhotoSlot({ slot, onFile, onUrl, onRemove, primary, size }) {
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);
  const dim = size || (primary ? 90 : 52);
  const src = slot ? (slot.kind === 'existing' ? slot.url : slot.previewUrl) : null;

  const accept = (dataTransfer) => {
    const file = dataTransfer?.files?.[0];
    if (file && file.type.startsWith('image/')) { onFile(file); return; }
    const [url] = extractImageUrlsFromDataTransfer(dataTransfer);
    if (url) onUrl(url);
  };

  return (
    <div
      onClick={() => !slot && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => { e.preventDefault(); e.stopPropagation(); setDragOver(false); accept(e.dataTransfer); }}
      onPaste={(e) => accept(e.clipboardData)}
      tabIndex={0}
      title={
        slot?.compressing ? 'Compressing…'
        : slot?.savedPct > 0 ? `Compressed — ${slot.savedPct}% smaller, same quality`
        : (primary ? 'Main / profile photo' : 'Gallery photo') + ' — drag from your computer or another website, or paste (Ctrl+V)'
      }
      style={{
        width: dim, height: dim, borderRadius: primary ? '50%' : 10, flexShrink: 0,
        border: `2px dashed ${dragOver ? '#7C3AED' : src ? 'transparent' : '#d8d8e0'}`,
        background: src ? `#000 url(${src}) center/cover no-repeat` : dragOver ? '#F5F3FF' : '#fff',
        display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
        position: 'relative', transition: 'all 0.15s ease', outline: 'none',
      }}
    >
      <input ref={inputRef} type="file" accept="image/*" style={{ display: 'none' }}
        onChange={(e) => accept(e.target)} />
      {!src && <FiCamera color="#b3b3bb" size={primary ? 22 : 14} />}
      {slot?.compressing && (
        <div style={{
          position: 'absolute', inset: 0, borderRadius: primary ? '50%' : 10,
          background: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <FiLoader color="#fff" size={primary ? 20 : 13} style={{ animation: 'spin 0.7s linear infinite' }} />
        </div>
      )}
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

/**
 * Shared create/edit form for accounts. Pass `account` (the full detail
 * object from GET /v1/admin/accounts/:id, including nested dating_profile /
 * professional_profile / photos) to edit that account; omit it to create a
 * new one. Both paths go through the same fields, the same photo slots, and
 * the same validation — editing is not a second, drifted implementation.
 */
export default function AccountFormModal({ open, account, onClose, onSaved }) {
  const isEdit = !!account;
  const [form, setForm] = useState(() => buildFormFromAccount(account));
  const [photos, setPhotos] = useState(() => buildPhotoSlots(account));
  const [options, setOptions] = useState({});
  const [districts, setDistricts] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [copied, setCopied] = useState(false);
  const [dropAreaOver, setDropAreaOver] = useState(false);

  const photosRef = useRef(photos);
  photosRef.current = photos;

  useEffect(() => {
    if (!open) return;
    photosRef.current.forEach((p) => p?.kind === 'new' && URL.revokeObjectURL(p.previewUrl));
    setForm(buildFormFromAccount(account));
    setPhotos(buildPhotoSlots(account));
    setError('');
    setResult(null);
    setCopied(false);
    referenceAPI.datingOptions().then((res) => setOptions(dataOf(res) || {})).catch(() => setOptions({}));
    referenceAPI.locations({ level: 'district' }).then((res) => {
      setDistricts([...(dataOf(res) || [])].sort((a, b) => a.name.localeCompare(b.name)));
    }).catch(() => setDistricts([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, account?.id]);

  useEffect(() => () => photosRef.current.forEach((p) => p?.kind === 'new' && URL.revokeObjectURL(p.previewUrl)), []);

  const set = (field, value) => setForm((f) => ({ ...f, [field]: value }));
  const setDating = (field, value) => setForm((f) => ({ ...f, dating_profile: { ...f.dating_profile, [field]: value } }));
  const setPro = (field, value) => setForm((f) => ({ ...f, professional_profile: { ...f.professional_profile, [field]: value } }));
  const setMode = (mode, value) => setForm((f) => ({ ...f, modes: { ...f.modes, [mode]: value } }));
  const optionsFor = (key) => options[key] || [];
  const districtOptions = districts.map((d) => ({ value: d.id, label: d.name }));

  // Shows the original instantly (compression takes a moment for a big
  // photo — no reason to make the admin stare at an empty slot for it),
  // then swaps in the compressed file once ready. Guarded against the slot
  // having moved on (removed / replaced) while compression was still running.
  const runCompression = (index, file) => {
    compressForUpload(file).then(({ file: compressedFile, savedPct }) => {
      setPhotos((prev) => {
        const slot = prev[index];
        if (!slot || slot.kind !== 'new' || slot.file !== file) return prev;
        const next = [...prev];
        URL.revokeObjectURL(slot.previewUrl);
        next[index] = {
          kind: 'new', file: compressedFile, previewUrl: URL.createObjectURL(compressedFile),
          compressing: false, savedPct,
        };
        return next;
      });
    });
  };

  const fillSlot = (index, file) => {
    setPhotos((prev) => {
      const next = [...prev];
      if (next[index]?.kind === 'new') URL.revokeObjectURL(next[index].previewUrl);
      next[index] = { kind: 'new', file, previewUrl: URL.createObjectURL(file), compressing: true };
      return next;
    });
    runCompression(index, file);
  };

  const fillSlotFromUrl = (index, url) => {
    setPhotos((prev) => {
      const next = [...prev];
      if (next[index]?.kind === 'new') URL.revokeObjectURL(next[index].previewUrl);
      next[index] = { kind: 'new-url', url, previewUrl: url };
      return next;
    });
  };

  const removeSlot = async (index) => {
    const slot = photos[index];
    if (!slot) return;
    if (slot.kind === 'new' || slot.kind === 'new-url') {
      setPhotos((prev) => {
        const next = [...prev];
        if (next[index].kind === 'new') URL.revokeObjectURL(next[index].previewUrl);
        next[index] = null;
        return next;
      });
      return;
    }
    // Existing photo — delete server-side immediately, then refresh slots
    // from the account so any server-side profile-photo promotion shows up.
    if (!window.confirm('Remove this photo? This cannot be undone.')) return;
    try {
      await adminAPI.accountPhotoDelete(account.id, slot.id);
      const res = await adminAPI.accountShow(account.id);
      setPhotos(buildPhotoSlots(dataOf(res)));
    } catch (e) {
      alert(e.response?.data?.message || 'Could not delete photo.');
    }
  };

  const distributeFiles = (fileList) => {
    const files = Array.from(fileList).filter((f) => f.type.startsWith('image/'));
    if (!files.length) return;
    const filled = [];
    setPhotos((prev) => {
      const next = [...prev];
      let fi = 0;
      for (let i = 0; i < next.length && fi < files.length; i++) {
        if (!next[i]) {
          next[i] = { kind: 'new', file: files[fi], previewUrl: URL.createObjectURL(files[fi]), compressing: true };
          filled.push({ index: i, file: files[fi] });
          fi++;
        }
      }
      return next;
    });
    filled.forEach(({ index, file }) => runCompression(index, file));
  };

  const distributeUrls = (urls) => {
    if (!urls.length) return;
    setPhotos((prev) => {
      const next = [...prev];
      let ui = 0;
      for (let i = 0; i < next.length && ui < urls.length; i++) {
        if (!next[i]) { next[i] = { kind: 'new-url', url: urls[ui], previewUrl: urls[ui] }; ui++; }
      }
      return next;
    });
  };

  // The big drop zone around all 6 slots — same file-then-URL priority as
  // one slot's own onDrop, just spread across however many empty slots
  // there are instead of a single one.
  const handleZoneDrop = (dataTransfer) => {
    const files = Array.from(dataTransfer.files || []).filter((f) => f.type.startsWith('image/'));
    if (files.length) { distributeFiles(files); return; }
    distributeUrls(extractImageUrlsFromDataTransfer(dataTransfer));
  };

  const submit = async () => {
    setError('');
    if (!form.display_name.trim()) return setError('Display name is required.');
    if (!form.phone.trim()) return setError('Phone number is required.');

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
        account_status: form.account_status,
        modes: form.modes,
      };
      if (form.modes.sparks) {
        payload.dating_profile = Object.fromEntries(Object.entries(form.dating_profile).filter(([, v]) => v !== ''));
      }
      if (form.modes.professional) {
        payload.professional_profile = Object.fromEntries(Object.entries(form.professional_profile).filter(([, v]) => v !== ''));
      }

      const res = isEdit
        ? await adminAPI.accountUpdate(account.id, payload)
        : await adminAPI.accountCreate(payload);
      const saved = dataOf(res);

      const newSlots = photos.filter((p) => p?.kind === 'new' || p?.kind === 'new-url');
      let photoFailures = 0;
      // URL-based photos have real, specific ways to fail (blocked host,
      // not actually an image, too large…) that a bare "N failed" count
      // would hide — worth surfacing verbatim rather than a generic message.
      const photoErrors = [];
      for (let i = 0; i < photos.length; i++) {
        const slot = photos[i];
        if (!slot || (slot.kind !== 'new' && slot.kind !== 'new-url')) continue;
        try {
          const fd = new FormData();
          if (slot.kind === 'new') fd.append('photo', slot.file);
          else fd.append('photo_url', slot.url);
          if (i === 0) fd.append('is_profile_photo', 'true');
          await adminAPI.accountPhotoUpload(saved.id, fd);
        } catch (e) {
          photoFailures++;
          const msg = e.response?.data?.message;
          if (msg) photoErrors.push(slot.kind === 'new-url' ? `${slot.url}: ${msg}` : msg);
        }
      }

      onSaved?.();
      if (isEdit) {
        if (photoErrors.length) alert(`Some photos could not be added:\n\n${photoErrors.join('\n')}`);
        onClose();
      } else {
        setResult({ ...saved, photoFailures, photoTotal: newSlots.length, photoErrors });
      }
    } catch (e) {
      setError(e.response?.data?.message || 'Could not save the account.');
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
              ? `url(${photos[0].previewUrl || photos[0].url}) center/cover` : 'linear-gradient(135deg, #7C3AED, #DB2777)',
            color: '#fff', fontSize: 26, fontWeight: 800, boxShadow: '0 10px 28px rgba(124,58,237,0.3)',
          }}>{!photos[0] && (result.display_name || '?').trim()[0]?.toUpperCase()}</div>
          <div style={{ fontWeight: 800, fontSize: 16.5 }}>{result.display_name}</div>
          <div style={{ color: '#9a9aa3', fontSize: 13, marginBottom: 14 }}>@{result.handle}</div>
        </div>

        {result.photoTotal > 0 && (
          <div style={{ marginBottom: 14 }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5,
              color: result.photoFailures ? '#C2410C' : '#059669',
            }}>
              {result.photoFailures ? <FiAlertTriangle /> : <FiCheck />}
              {result.photoFailures
                ? `${result.photoTotal - result.photoFailures} of ${result.photoTotal} photos uploaded — ${result.photoFailures} failed. You can add them later by editing this account.`
                : `${result.photoTotal} photo${result.photoTotal > 1 ? 's' : ''} uploaded.`}
            </div>
            {result.photoErrors?.length > 0 && (
              <ul style={{ margin: '6px 0 0', paddingLeft: 18, fontSize: 11.5, color: '#9a9aa3' }}>
                {result.photoErrors.map((msg, i) => <li key={i}>{msg}</li>)}
              </ul>
            )}
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

  const bothModes = form.modes.sparks && form.modes.professional;

  const datingFields = (
    <>
      <Field label="Bio">
        <textarea style={{ ...compactInput, minHeight: 46, resize: 'vertical' }} value={form.dating_profile.bio}
          onChange={(e) => setDating('bio', e.target.value)} placeholder="A short bio…" />
      </Field>
      <Grid cols={bothModes ? 3 : 4}>
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
        {/* Everything below is collected by profile_wizard_screen.dart's
            "Family & dating" and "Personality" steps but was missing from
            this form until this audit — an admin editing a member's account
            couldn't represent what the member's own wizard could. */}
        <Field label="Here for"><Select value={form.dating_profile.intent} onChange={(v) => setDating('intent', v)} options={INTENT_OPTIONS} /></Field>
        <Field label="Has children"><Select value={form.dating_profile.has_children} onChange={(v) => setDating('has_children', v)} options={optionsFor('has_children')} /></Field>
        <Field label="Wants children"><Select value={form.dating_profile.wants_children} onChange={(v) => setDating('wants_children', v)} options={optionsFor('wants_children')} /></Field>
        <Field label="Pets"><Select value={form.dating_profile.pets} onChange={(v) => setDating('pets', v)} options={optionsFor('pets')} /></Field>
        <Field label="Religiosity"><Select value={form.dating_profile.religiosity} onChange={(v) => setDating('religiosity', v)} options={optionsFor('religiosity')} /></Field>
        <Field label="Politics"><Select value={form.dating_profile.politics} onChange={(v) => setDating('politics', v)} options={optionsFor('politics')} /></Field>
        <Field label="Star sign"><Select value={form.dating_profile.zodiac} onChange={(v) => setDating('zodiac', v)} options={optionsFor('zodiac')} /></Field>
        <Field label="Personality (MBTI)"><Select value={form.dating_profile.personality_type} onChange={(v) => setDating('personality_type', v)} options={optionsFor('personality_type')} /></Field>
        <Field label="Communication"><Select value={form.dating_profile.communication_style} onChange={(v) => setDating('communication_style', v)} options={optionsFor('communication_style')} /></Field>
      </Grid>
      <Field label="Languages spoken"><MultiChipSelect value={form.dating_profile.languages_spoken} onChange={(v) => setDating('languages_spoken', v)} options={optionsFor('languages')} /></Field>
      <Field label="Love languages"><MultiChipSelect value={form.dating_profile.love_languages} onChange={(v) => setDating('love_languages', v)} options={optionsFor('love_languages')} /></Field>
    </>
  );

  const professionalFields = (
    <>
      <Grid cols={bothModes ? 1 : 3}>
        <Field label="Headline"><input style={compactInput} value={form.professional_profile.headline} onChange={(e) => setPro('headline', e.target.value)} placeholder="Software Engineer at Acme" /></Field>
        {!bothModes && <Field label="Current role"><input style={compactInput} value={form.professional_profile.current_role} onChange={(e) => setPro('current_role', e.target.value)} placeholder="Backend Engineer" /></Field>}
        {!bothModes && <Field label="Tagline"><input style={compactInput} value={form.professional_profile.tagline} onChange={(e) => setPro('tagline', e.target.value)} placeholder="Building things that matter" /></Field>}
      </Grid>
      {bothModes && (
        <Grid cols={2}>
          <Field label="Current role"><input style={compactInput} value={form.professional_profile.current_role} onChange={(e) => setPro('current_role', e.target.value)} placeholder="Backend Engineer" /></Field>
          <Field label="Tagline"><input style={compactInput} value={form.professional_profile.tagline} onChange={(e) => setPro('tagline', e.target.value)} placeholder="Building things that matter" /></Field>
        </Grid>
      )}
      <Field label="Bio">
        <textarea style={{ ...compactInput, minHeight: 46, resize: 'vertical' }} value={form.professional_profile.bio}
          onChange={(e) => setPro('bio', e.target.value)} placeholder="A short professional bio…" />
      </Field>
      <Grid cols={bothModes ? 2 : 4}>
        <Field label="Seniority"><Select value={form.professional_profile.seniority} onChange={(v) => setPro('seniority', v)} options={SENIORITY.map((s) => ({ value: s, label: s[0].toUpperCase() + s.slice(1) }))} /></Field>
        <Field label="Industry"><Select value={form.professional_profile.industry} onChange={(v) => setPro('industry', v)} options={optionsFor('industry')} /></Field>
        <Field label="Years exp."><input style={compactInput} type="number" min="0" max="60" value={form.professional_profile.years_experience} onChange={(e) => setPro('years_experience', e.target.value ? Number(e.target.value) : '')} placeholder="5" /></Field>
        <Field label="Pronouns"><input style={compactInput} value={form.professional_profile.pronouns} onChange={(e) => setPro('pronouns', e.target.value)} placeholder="she/her" /></Field>
        <Field label="Availability"><Select value={form.professional_profile.availability_status} onChange={(v) => setPro('availability_status', v)} options={AVAILABILITY} /></Field>
      </Grid>
    </>
  );

  return (
    <Modal open={open} onClose={onClose} title={isEdit ? `Edit ${account.display_name || 'account'}` : 'New account'} width={1520}
      footer={<>
        <button style={btn(false)} onClick={onClose} disabled={saving}>Cancel</button>
        <button style={btn(true)} onClick={submit} disabled={saving}>{saving ? 'Saving…' : isEdit ? 'Save changes' : 'Create account'}</button>
      </>}>
      {error && (
        <div style={{
          background: '#fef2f2', color: '#DC2626', border: '1px solid #f3c4c4',
          borderRadius: 8, padding: '9px 12px', fontSize: 12.5, marginBottom: 14,
        }}>{error}</div>
      )}

      <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start' }}>
        {/* LEFT: photos + basic info — narrow, fixed width to free up the
            rest of this now-much-wider modal for the profile field grids. */}
        <div style={{ width: 380, flexShrink: 0 }}>
          <SectionHeading color="#7C3AED">Photos</SectionHeading>
          <div
            onDragOver={(e) => { e.preventDefault(); setDropAreaOver(true); }}
            onDragLeave={() => setDropAreaOver(false)}
            onDrop={(e) => { e.preventDefault(); setDropAreaOver(false); handleZoneDrop(e.dataTransfer); }}
            onPaste={(e) => handleZoneDrop(e.clipboardData)}
            tabIndex={0}
            style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10, padding: 14,
              borderRadius: 12, background: dropAreaOver ? '#F5F3FF' : '#fafafa',
              border: `1.5px dashed ${dropAreaOver ? '#7C3AED' : '#ececf1'}`, marginBottom: 16,
              transition: 'all 0.15s ease', outline: 'none',
            }}
          >
            <PhotoSlot slot={photos[0]} primary onFile={(f) => fillSlot(0, f)} onUrl={(u) => fillSlotFromUrl(0, u)} onRemove={() => removeSlot(0)} />
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center' }}>
              {photos.slice(1).map((slot, i) => (
                <PhotoSlot key={i + 1} slot={slot} onFile={(f) => fillSlot(i + 1, f)} onUrl={(u) => fillSlotFromUrl(i + 1, u)} onRemove={() => removeSlot(i + 1)} />
              ))}
            </div>
            <div style={{ fontSize: 10.5, color: '#9a9aa3', textAlign: 'center' }}>
              Drag & drop up to {PHOTO_SLOTS} photos — from your computer or straight off another website — or paste (Ctrl+V). First is the profile photo.
            </div>
          </div>

          <SectionHeading>Basic info</SectionHeading>
          <Field label="Display name" required><IconInput icon={FiUser} value={form.display_name} onChange={(e) => set('display_name', e.target.value)} placeholder="Jane Doe" /></Field>
          <Field label="Phone" required><IconInput icon={FiPhone} value={form.phone} onChange={(e) => set('phone', cleanPhone(e.target.value))} placeholder="+256700000000" /></Field>
          <Field label="Email"><IconInput icon={FiMail} type="email" value={form.email} onChange={(e) => set('email', e.target.value)} placeholder="jane@example.com" /></Field>
          <Field label="Handle" hint="Auto-generated if blank"><input style={compactInput} value={form.handle} onChange={(e) => set('handle', e.target.value.toLowerCase())} placeholder="jane-doe" /></Field>
          <Field label="App">
            <Select value={form.app_id} onChange={(v) => set('app_id', v)} options={[{ value: 'linkup', label: 'LinkUp' }, { value: 'abanoonya', label: 'Abanoonya Pro' }, { value: 'uganda_dating', label: 'Uganda Dating App' }]} />
          </Field>
          <Field label="Status">
            <StatusRadioGroup value={form.account_status} onChange={(v) => set('account_status', v)} />
          </Field>
          <Field label="Premium">
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, height: 20 }}>
              <input type="checkbox" checked={form.is_premium} onChange={(e) => set('is_premium', e.target.checked)} /> Grant LinkUp+ premium
            </label>
          </Field>
          {isEdit && (
            <Field label="GPS location">
              {account.last_lat && account.last_lng ? (
                <a href={`https://www.google.com/maps?q=${account.last_lat},${account.last_lng}`} target="_blank" rel="noreferrer"
                  style={{ fontSize: 12, color: '#7C3AED', fontWeight: 600 }}>
                  {Number(account.last_lat).toFixed(4)}, {Number(account.last_lng).toFixed(4)} — view on map
                </a>
              ) : <span style={{ fontSize: 12, color: '#c4c4cc' }}>No GPS recorded yet</span>}
            </Field>
          )}
          <Field label="Password" hint={isEdit ? 'Leave blank to keep the current password' : 'Auto-generated if blank'}>
            <div style={{ display: 'flex', gap: 6 }}>
              <div style={{ flex: 1 }}><IconInput icon={FiLock} value={form.password} onChange={(e) => set('password', e.target.value)} placeholder="•••••••••" /></div>
              <button type="button" style={{ ...btn(false), padding: '6px 9px' }} onClick={() => set('password', generatePassword())} title="Generate now"><FiShuffle size={12} /></button>
            </div>
          </Field>
        </div>

        {/* RIGHT: modes + profile sections — dating and professional sit
            side by side when both are enabled, instead of stacking, so the
            extra width this modal now has actually shortens the form. */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <SectionHeading>Modes</SectionHeading>
          <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
            <ModeToggle active={form.modes.sparks} icon={FiHeart} title="Sparks (dating)" color="#DB2777" onClick={() => setMode('sparks', !form.modes.sparks)} />
            <ModeToggle active={form.modes.professional} icon={FiBriefcase} title="Professional" color="#7C3AED" onClick={() => setMode('professional', !form.modes.professional)} />
          </div>

          <div style={{ display: 'flex', gap: 28 }}>
            {form.modes.sparks && (
              <div style={{ flex: 1, minWidth: 0 }}>
                <SectionHeading color="#DB2777">Dating profile</SectionHeading>
                {datingFields}
              </div>
            )}
            {form.modes.professional && (
              <div style={{ flex: 1, minWidth: 0 }}>
                <SectionHeading>Professional profile</SectionHeading>
                {professionalFields}
              </div>
            )}
            {!form.modes.sparks && !form.modes.professional && (
              <div style={{ fontSize: 13, color: '#9a9aa3', padding: '20px 0' }}>
                Enable Sparks or Professional above to add a profile.
              </div>
            )}
          </div>
        </div>
      </div>
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

// Single-select pill group — a radio button in spirit (exactly one of N
// statuses is ever selected, all options visible at once) without the
// visual weight of native <input type="radio"> circles.
function StatusRadioGroup({ value, onChange }) {
  return (
    <div role="radiogroup" style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
      {ACCOUNT_STATUSES.map((s) => {
        const active = value === s.value;
        const color = STATUS_COLORS[s.value];
        return (
          <button
            key={s.value} type="button" role="radio" aria-checked={active}
            onClick={() => onChange(s.value)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6, padding: '6px 13px', borderRadius: 20, cursor: 'pointer',
              border: active ? `1.5px solid ${color}` : '1.5px solid #ececf1',
              background: active ? `${color}14` : '#fff', color: active ? color : '#8a8a93',
              fontSize: 12, fontWeight: 700, transition: 'all 0.15s ease',
            }}
          >
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: active ? color : '#d8d8e0', flexShrink: 0 }} />
            {s.label}
          </button>
        );
      })}
    </div>
  );
}

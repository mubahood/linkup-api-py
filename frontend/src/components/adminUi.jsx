import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { FiChevronLeft, FiChevronRight, FiMoreVertical } from 'react-icons/fi';

const STATUS = {
  active:    { bg: '#ecfdf5', color: '#059669' },
  suspended: { bg: '#fef2f2', color: '#DC2626' },
  closed:    { bg: '#f3f4f6', color: '#6b7280' },
  pending:   { bg: '#fff7ed', color: '#C2410C' },
  resolved:  { bg: '#ecfdf5', color: '#059669' },
  dismissed: { bg: '#f3f4f6', color: '#6b7280' },
  escalated: { bg: '#fef2f2', color: '#DC2626' },
};

export function Badge({ value, children }) {
  const cfg = STATUS[value] || { bg: '#EDE9FE', color: '#5B21B6' };
  return (
    <span style={{
      background: cfg.bg, color: cfg.color, padding: '2px 9px',
      borderRadius: 4, fontSize: 11, fontWeight: 700, whiteSpace: 'nowrap',
      textTransform: 'capitalize', display: 'inline-block',
    }}>{children ?? value ?? '—'}</span>
  );
}

export function Avatar({ name, avatar, size = 34 }) {
  const [failed, setFailed] = React.useState(false);
  const init = (name || '?').trim()[0]?.toUpperCase() || '?';
  if (avatar && !failed) {
    return (
      <img src={avatar} alt={name || ''} onError={() => setFailed(true)}
        style={{ width: size, height: size, borderRadius: '50%', objectFit: 'cover' }} />
    );
  }
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%', background: '#EDE9FE',
      color: '#5B21B6', display: 'grid', placeItems: 'center', fontWeight: 800,
      fontSize: size * 0.42,
    }}>{init}</div>
  );
}

export const fmtDate = (s) => {
  if (!s) return '—';
  const d = new Date(s);
  if (isNaN(d)) return '—';
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
};

export const tableStyle = {
  width: '100%', borderCollapse: 'collapse', background: '#fff',
  border: '1px solid #ececf1', borderRadius: 10, overflow: 'hidden',
};
export const thStyle = {
  textAlign: 'left', padding: '11px 14px', fontSize: 11.5, fontWeight: 700,
  textTransform: 'uppercase', letterSpacing: 0.5, color: '#8a8a93',
  borderBottom: '1px solid #ececf1', background: '#fafafb', whiteSpace: 'nowrap',
};
export const tdStyle = {
  padding: '11px 14px', fontSize: 13.5, borderBottom: '1px solid #f3f3f6',
  verticalAlign: 'middle',
};

export function Toolbar({ children }) {
  return (
    <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
      marginBottom: 14 }}>{children}</div>
  );
}

export function Pager({ page, lastPage, total, onPage }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      marginTop: 14, fontSize: 13, color: '#6b6b76' }}>
      <span>{total} total</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <button className="btn-icon" disabled={page <= 1}
          onClick={() => onPage(page - 1)}><FiChevronLeft /></button>
        <span>Page {page} / {lastPage}</span>
        <button className="btn-icon" disabled={page >= lastPage}
          onClick={() => onPage(page + 1)}><FiChevronRight /></button>
      </div>
    </div>
  );
}

export function EmptyRow({ colSpan, text = 'Nothing here yet.' }) {
  return (
    <tr><td colSpan={colSpan} style={{ ...tdStyle, textAlign: 'center', color: '#9a9aa3',
      padding: '32px 14px' }}>{text}</td></tr>
  );
}

export function btn(primary, danger) {
  return {
    display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 12px',
    borderRadius: 8, fontSize: 12.5, fontWeight: 700, cursor: 'pointer',
    border: primary ? 'none' : `1px solid ${danger ? '#f3c4c4' : '#d8d8e0'}`,
    background: primary ? (danger ? '#DC2626' : '#7C3AED') : '#fff',
    color: primary ? '#fff' : (danger ? '#DC2626' : '#444'),
  };
}

/** Slide-over drawer, used for detail/review views. Click the backdrop or
 * the X to close. */
export function Drawer({ open, onClose, title, width = 480, children }) {
  if (!open) return null;
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 200 }}>
      <div onClick={onClose} style={{
        position: 'absolute', inset: 0, background: 'rgba(15,15,20,0.35)',
      }} />
      <div style={{
        position: 'absolute', top: 0, right: 0, bottom: 0, width,
        maxWidth: '92vw', background: '#fff', boxShadow: '-8px 0 32px rgba(0,0,0,0.14)',
        display: 'flex', flexDirection: 'column',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '16px 20px', borderBottom: '1px solid #ececf1',
        }}>
          <div style={{ fontWeight: 800, fontSize: 15.5 }}>{title}</div>
          <button onClick={onClose} style={{
            border: 'none', background: 'transparent', cursor: 'pointer',
            fontSize: 18, color: '#8a8a93', lineHeight: 1,
          }}>×</button>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: 20 }}>{children}</div>
      </div>
    </div>
  );
}

export function SectionTitle({ children }) {
  return (
    <div style={{
      fontSize: 11.5, fontWeight: 800, textTransform: 'uppercase', letterSpacing: 0.5,
      color: '#8a8a93', margin: '18px 0 8px',
    }}>{children}</div>
  );
}

export function KeyVal({ k, v }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0',
      borderBottom: '1px solid #f3f3f6', fontSize: 13 }}>
      <span style={{ color: '#8a8a93' }}>{k}</span>
      <span style={{ fontWeight: 600, textAlign: 'right', maxWidth: '60%' }}>{v ?? '—'}</span>
    </div>
  );
}

/** Centered modal for create/edit forms — distinct from Drawer (a side
 * panel meant for read-mostly detail views). Click the backdrop or the X
 * to close; pass `footer` for the action-button row. */
export function Modal({ open, onClose, title, width = 720, children, footer }) {
  if (!open) return null;
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 300, display: 'flex',
      alignItems: 'flex-start', justifyContent: 'center', padding: '5vh 16px', overflowY: 'auto',
    }}>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(15,15,20,0.45)' }} />
      <div style={{
        position: 'relative', width, maxWidth: '100%', background: '#fff', borderRadius: 14,
        boxShadow: '0 24px 64px rgba(0,0,0,0.25)', display: 'flex', flexDirection: 'column',
        maxHeight: '90vh',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '18px 22px', borderBottom: '1px solid #ececf1', flexShrink: 0,
        }}>
          <div style={{ fontWeight: 800, fontSize: 16.5 }}>{title}</div>
          <button onClick={onClose} style={{
            border: 'none', background: 'transparent', cursor: 'pointer',
            fontSize: 20, color: '#8a8a93', lineHeight: 1,
          }}>×</button>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: 22 }}>{children}</div>
        {footer && (
          <div style={{
            padding: '16px 22px', borderTop: '1px solid #ececf1', display: 'flex',
            justifyContent: 'flex-end', gap: 10, flexShrink: 0,
          }}>{footer}</div>
        )}
      </div>
    </div>
  );
}

export const inputStyle = {
  width: '100%', padding: '9px 12px', borderRadius: 8, border: '1px solid #d8d8e0',
  fontSize: 13.5, fontFamily: 'inherit', boxSizing: 'border-box', background: '#fff', color: '#18181b',
};

export function FormRow({ label, required, children, hint }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <label style={{ display: 'block', fontSize: 12.5, fontWeight: 700, color: '#52525b', marginBottom: 5 }}>
        {label}{required && <span style={{ color: '#DC2626' }}> *</span>}
      </label>
      {children}
      {hint && <div style={{ fontSize: 11.5, color: '#9a9aa3', marginTop: 4 }}>{hint}</div>}
    </div>
  );
}

export function FormGrid({ children, cols = 2 }) {
  return <div style={{ display: 'grid', gridTemplateColumns: `repeat(${cols}, minmax(0,1fr))`, gap: '0 16px' }}>{children}</div>;
}

export function FormSection({ title, description, children, right }) {
  return (
    <div style={{ marginBottom: 24, paddingBottom: 20, borderBottom: '1px solid #f3f3f6' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: description ? 2 : 12 }}>
        <div style={{ fontWeight: 800, fontSize: 14 }}>{title}</div>
        {right}
      </div>
      {description && <div style={{ fontSize: 12, color: '#9a9aa3', marginBottom: 12 }}>{description}</div>}
      {children}
    </div>
  );
}
/**
 * Kebab-menu action dropdown for table rows. `items` is
 * [{label, icon?, onClick, danger?}] — falsy entries are skipped so callers
 * can conditionally include an action inline (e.g. `status === 'active' &&
 * {...}`). Closes on outside click, Escape, or scroll.
 *
 * Renders through a portal into document.body rather than as a normal
 * absolutely-positioned child: this button typically sits inside a table
 * styled with `overflow: hidden` (tableStyle, for rounded corners), which
 * would silently clip a same-subtree dropdown to the table's bounding box —
 * exactly the kind of bug that only shows up once you actually open the
 * menu and look, not from reading the code.
 */
export function ActionMenu({ items }) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const btnRef = useRef(null);
  const menuRef = useRef(null);

  const openMenu = () => {
    const rect = btnRef.current.getBoundingClientRect();
    const width = 180;
    setPos({ top: rect.bottom + 6, left: Math.max(8, rect.right - width) });
    setOpen(true);
  };

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e) => {
      if (btnRef.current?.contains(e.target) || menuRef.current?.contains(e.target)) return;
      setOpen(false);
    };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    const onScroll = () => setOpen(false);
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onKey);
    window.addEventListener('scroll', onScroll, true);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onKey);
      window.removeEventListener('scroll', onScroll, true);
    };
  }, [open]);

  const visible = items.filter(Boolean);

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        onClick={(e) => { e.stopPropagation(); open ? setOpen(false) : openMenu(); }}
        className="btn-icon"
        style={{
          width: 30, height: 30, display: 'grid', placeItems: 'center', borderRadius: 8,
          border: '1px solid #d8d8e0', background: open ? '#f3f3f6' : '#fff', cursor: 'pointer', color: '#52525b',
        }}
      ><FiMoreVertical size={15} /></button>

      {open && createPortal(
        <div
          ref={menuRef}
          onClick={(e) => e.stopPropagation()}
          style={{
            position: 'fixed', top: pos.top, left: pos.left, zIndex: 1000, minWidth: 180,
            background: '#fff', border: '1px solid #ececf1', borderRadius: 10,
            boxShadow: '0 10px 30px rgba(0,0,0,0.16)', padding: 6, display: 'flex', flexDirection: 'column',
          }}
        >
          {visible.map((item, i) => (
            <button
              key={i}
              type="button"
              onClick={() => { setOpen(false); item.onClick(); }}
              style={{
                display: 'flex', alignItems: 'center', gap: 9, padding: '8px 10px', borderRadius: 7,
                border: 'none', background: 'transparent', cursor: 'pointer', textAlign: 'left',
                fontSize: 12.5, fontWeight: 600, color: item.danger ? '#DC2626' : '#27272a',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = item.danger ? '#fef2f2' : '#f5f5f7'; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
            >
              {item.icon && <item.icon size={13} />} {item.label}
            </button>
          ))}
        </div>,
        document.body
      )}
    </>
  );
}


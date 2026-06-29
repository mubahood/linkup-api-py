import React from 'react';
import { FiChevronLeft, FiChevronRight } from 'react-icons/fi';

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

export function btn(primary) {
  return {
    display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 12px',
    borderRadius: 8, fontSize: 12.5, fontWeight: 700, cursor: 'pointer',
    border: primary ? 'none' : '1px solid #d8d8e0',
    background: primary ? '#7C3AED' : '#fff', color: primary ? '#fff' : '#444',
  };
}

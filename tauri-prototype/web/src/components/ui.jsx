// ── Composants UI de base (prototype) ────────────────────────────────

import React from 'react';

export const Spinner = ({ size = 8 }) => (
  <span className="spinner" style={{ display: 'inline-block', width: size + 'em', height: size + 'em', border: size / 8 + 'em solid var(--border)', borderTopColor: 'var(--primary)', borderRadius: '50%' }} />
);

export const Button = ({ children, loading = false, className = '', ...props }) => (
  <button
    className={`btn ${loading ? 'loading' : ''} ${className}`}
    disabled={loading}
    {...props}
  >
    {loading && <Spinner size={1} style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: 6 }} />}
    <span className="btn-label">{children}</span>
  </button>
);

export const Input = ({ className = '', ...props }) => (
  <input className={`input ${className}`} {...props} />
);

export const Card = ({ children, className = '' }) => (
  <div className={`card ${className}`}>{children}</div>
);

export const Text = ({ className = '', ...props }) => (
  <p className={`text ${className}`} {...props} />
);

export const Badge = ({ status = 'info', children, className = '' }) => {
  const map = {
    success: 'badge-success',
    warning: 'badge-warning',
    danger: 'badge-error',
    info: 'badge-info',
    primary: 'badge-primary',
  };
  return (
    <span className={`badge ${map[status] || map.info} ${className}`}>{children}</span>
  );
};

export const Table = ({ children, className = '' }) => (
  <table className={`table ${className}`}>{children}</table>
);

export const Modal = ({ children, ...props }) => (
  <div className="modal-overlay">
    <div className="modal" {...props}>{children}</div>
  </div>
);

export const Stat = ({ label, value, icon = 'folder', color = '#2F4255' }) => (
  <div className="stat" style={{ borderColor: color }}>
    <div className="stat-icon" style={{ color: color }}>{icon}</div>
    <p className="stat-label">{label}</p>
    <p className="stat-value">{value}</p>
  </div>
);

export const toast = {
  error: (m) => console.error('[tpg toast error]', m),
  success: (m) => console.log('[tpg toast ok]', m),
};

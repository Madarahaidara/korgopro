import React from 'react';

export function DemoNotice() {
  return (
    <div className="demo-notice" role="note">
      <span className="demo-notice-dot" />
      Mode démonstration : ces données sont fictives et ne sont pas enregistrées dans Supabase.
    </div>
  );
}

export function PageHeader({ title, subtitle, action }) {
  return (
    <div className="erp-page-heading">
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {action && <div className="erp-heading-actions">{action}</div>}
    </div>
  );
}

export function MetricCard({ label, value, detail, icon, tone = 'blue' }) {
  return (
    <article className={`erp-metric erp-metric-${tone}`}>
      <div className="erp-metric-top">
        <span>{label}</span>
        <span className="erp-metric-icon" aria-hidden="true">{icon}</span>
      </div>
      <strong>{value}</strong>
      {detail && <small>{detail}</small>}
    </article>
  );
}

export function Panel({ title, description, action, children, className = '' }) {
  return (
    <section className={`erp-panel ${className}`}>
      {(title || action) && (
        <div className="erp-panel-heading">
          <div>
            {title && <h2>{title}</h2>}
            {description && <p>{description}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Tabs({ items, value, onChange }) {
  return (
    <div className="erp-tabs" role="tablist">
      {items.map((item) => (
        <button
          key={item}
          type="button"
          role="tab"
          aria-selected={value === item}
          className={value === item ? 'is-active' : ''}
          onClick={() => onChange(item)}
        >
          {item}
        </button>
      ))}
    </div>
  );
}

export function StatusBadge({ children }) {
  const status = String(children).toLowerCase();
  const tone = status.includes('inactif') || status.includes('suspendu')
    ? 'danger'
    : status.includes('payée') || status.includes('acceptée') || status.includes('actif')
    ? 'success'
    : status.includes('partielle') || status.includes('envoyée') || status.includes('brouillon')
      ? 'warning'
      : status.includes('payer') || status.includes('inactif')
        ? 'danger'
        : 'neutral';
  return <span className={`erp-badge erp-badge-${tone}`}>{children}</span>;
}

export function DataTable({ columns, rows = [], emptyMessage = 'Aucun résultat.', pageSize = 25 }) {
  const [page, setPage] = React.useState(0);
  React.useEffect(() => setPage(0), [rows]);
  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
  const first = rows.length ? page * pageSize + 1 : 0;
  const last = Math.min((page + 1) * pageSize, rows.length);
  const visibleRows = rows.slice(page * pageSize, (page + 1) * pageSize);
  return (
    <>
      <div className="erp-table-wrap">
        <table className="erp-table">
          <thead>
            <tr>{columns.map((column) => <th key={column.key}>{column.label}</th>)}</tr>
          </thead>
          <tbody>
            {rows.length ? visibleRows.map((row, index) => (
              <tr key={row.id || row.email || `${page}-${index}`}>
                {columns.map((column) => (
                  <td key={column.key}>
                    {column.render ? column.render(row[column.key], row) : row[column.key]}
                  </td>
                ))}
              </tr>
            )) : (
              <tr><td className="erp-empty" colSpan={columns.length}>{emptyMessage}</td></tr>
            )}
          </tbody>
        </table>
      </div>
      {rows.length > pageSize && <div className="erp-pagination" aria-label="Pagination du tableau">
        <span>{first}–{last} sur {rows.length}</span>
        <button type="button" className="erp-button erp-button-secondary" disabled={page === 0} onClick={() => setPage((current) => current - 1)}>Précédent</button>
        <span>Page {page + 1}/{pageCount}</span>
        <button type="button" className="erp-button erp-button-secondary" disabled={page + 1 >= pageCount} onClick={() => setPage((current) => current + 1)}>Suivant</button>
      </div>}
    </>
  );
}

export function Field({ label, value, onChange, type = 'text', placeholder, options, ...props }) {
  return (
    <label className="erp-field">
      <span>{label}</span>
      {options ? (
        <select value={value} onChange={(event) => onChange(event.target.value)} {...props}>
          {options.map((option) => {
            const optionValue = typeof option === 'string' ? option : option.value;
            const optionLabel = typeof option === 'string' ? option : option.label;
            return <option key={optionValue} value={optionValue}>{optionLabel}</option>;
          })}
        </select>
      ) : (
        <input
          type={type}
          value={value}
          placeholder={placeholder}
          onChange={(event) => onChange(event.target.value)}
          {...props}
        />
      )}
    </label>
  );
}

export function Modal({ title, onClose, children, footer }) {
  return (
    <div className="erp-modal-backdrop" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <section className="erp-modal" role="dialog" aria-modal="true" aria-labelledby="erp-modal-title">
        <header>
          <h2 id="erp-modal-title">{title}</h2>
          <button type="button" className="erp-icon-button" aria-label="Fermer" onClick={onClose}>×</button>
        </header>
        <div className="erp-modal-body">{children}</div>
        {footer && <footer>{footer}</footer>}
      </section>
    </div>
  );
}

export function ActionButton({ children, variant = 'primary', ...props }) {
  const { className = '', ...buttonProps } = props;
  return <button type="button" className={`erp-button erp-button-${variant} ${className}`} {...buttonProps}>{children}</button>;
}

export function InlineMessage({ children, tone = 'info' }) {
  if (!children) return null;
  return <div className={`erp-message erp-message-${tone}`} role="status">{children}</div>;
}

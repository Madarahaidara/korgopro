// ============================================================================
// Petits composants UI réutilisables (badges, modale).
// ============================================================================
import { useEffect } from 'react';
import Icon from './Icon';

export function Badge({ status }) {
  const s = String(status || '').toUpperCase();
  const success = ['ACTIF', 'PAID', 'PAYEE', 'COMPLETED', 'EMISE', 'ACCEPTEE', 'ACTIVE', 'EN_STOCK', 'RESOLU'];
  const danger = ['INACTIF', 'EXPIRED', 'REFUSEE', 'ANNULEE', 'RUPTURE', 'DESACTIVE', 'OUT_OF_STOCK', 'EN_RETARD', 'NON_PAYEE'];
  const warning = ['EN_ATTENTE', 'BROUILLON', 'PENDING', 'PARTIAL', 'PARTIELLEMENT', 'PARTIELLEMENT_PAYEE', 'ENVOYEE', 'LOW_STOCK', 'LOW'];
  const info = ['CONVERTIE', 'EN_ATTENTE_RECU'];
  let cls = 'badge-gray';
  if (success.includes(s)) cls = 'badge-success';
  else if (danger.includes(s)) cls = 'badge-danger';
  else if (warning.includes(s)) cls = 'badge-warning';
  else if (info.includes(s)) cls = 'badge-info';
  return <span className={`badge ${cls}`}>{status || '—'}</span>;
}

export function Modal({ title, onClose, width = 640, children }) {
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ maxWidth: width }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{title}</h3>
          <button className="modal-close" onClick={onClose} aria-label="Fermer"><Icon name="cancel" size={14} /></button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

export function Stat({ icon, label, value, color }) {
  return (
    <div className="card stat-card">
      <div
        className="stat-icon"
        style={{ background: `${color}1f`, color }}
      >
        {icon}
      </div>
      <div>
        <div className="stat-value">{value}</div>
        <div className="stat-label">{label}</div>
      </div>
    </div>
  );
}

export function ConfirmDelete({ message = 'Confirmer la suppression ?', onConfirm, onCancel }) {
  return (
    <Modal title="Confirmation" onClose={onCancel} width={400}>
      <p>{message}</p>
      <div className="form-actions">
        <button className="btn" onClick={onCancel}>Annuler</button>
        <button className="btn btn-danger" onClick={onConfirm}>Supprimer</button>
      </div>
    </Modal>
  );
}

export function toast(message, type = 'success') {
  const div = document.createElement('div');
  div.className = `toast toast-${type}`;
  div.textContent = message;
  document.body.appendChild(div);
  setTimeout(() => div.classList.add('show'), 10);
  setTimeout(() => {
    div.classList.remove('show');
    setTimeout(() => div.remove(), 300);
  }, 2600);
}
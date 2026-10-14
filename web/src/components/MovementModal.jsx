import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { createMovement } from '../api/treasuryApi';
import { Modal, toast } from './ui';
import Icon from './Icon';

// Catégories de mouvement de trésorerie (électricité, eau, internet, etc.).
// Aligné sur ui/views/treasury_view.py (mv_category).
const CATEGORIES = [
  'ELECTRICITE',
  'EAU',
  'INTERNET',
  'TRANSPORT',
  'MEUBLE',
  'MAINTENANCE',
  'DIVERS',
  'AUTRE',
];

export default function MovementModal({ accounts, onSave, onClose }) {
  const { user } = useAuth();
  const [form, setForm] = useState({
    account_id: accounts[0]?.id || '',
    movement_type: 'IN',
    amount: 0,
    reference: '',
    description: '',
    category: 'AUTRE',
  });
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const save = () => {
    if (!form.account_id || Number(form.amount) <= 0) {
      toast('Montant ou compte invalide.', 'danger');
      return;
    }
    createMovement({ ...form, amount: Number(form.amount), user_id: user?.id });
    onSave();
  };

  return (
    <Modal title="Nouveau mouvement" onClose={onClose} width={480}>
      <div className="field">
        <label>Compte</label>
        <select className="select" value={form.account_id} onChange={set('account_id')}>
          <option value="">— Sélectionner —</option>
          {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
      </div>
      <div className="field">
        <label>Type</label>
        <select className="select" value={form.movement_type} onChange={set('movement_type')}>
          <option value="IN">Entrée (+)</option>
          <option value="OUT">Sortie ()</option>
        </select>
      </div>
      <div className="field">
        <label>Montant</label>
        <input className="input" type="number" min="0" value={form.amount} onChange={set('amount')} />
      </div>
      <div className="field">
        <label>Référence</label>
        <input className="input" value={form.reference} onChange={set('reference')} />
      </div>
      <div className="field">
        <label>Catégorie</label>
        <select className="select" value={form.category} onChange={set('category')}>
          {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
      <div className="field">
        <label>Description</label>
        <textarea className="textarea" value={form.description} onChange={set('description')} />
      </div>
      <div className="form-actions">
        <button className="btn" onClick={onClose}>Annuler</button>
        <button className="btn btn-primary" onClick={save}>Enregistrer</button>
      </div>
    </Modal>
  );
}
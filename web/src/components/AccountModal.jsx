import { useState } from 'react';
import { saveAccount } from '../api/treasuryApi';
import { Modal, toast } from './ui';

const ACCOUNT_TYPES = ['CASH', 'BANK', 'MOBILE_MONEY'];
const TYPE_LABELS = { CASH: 'Caisse', BANK: 'Banque', MOBILE_MONEY: 'Mobile Money' };

export default function AccountModal({ onSave, onClose }) {
  const [form, setForm] = useState({ name: '', account_type: 'CASH', initial_balance: 0 });
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const save = () => {
    if (!form.name.trim()) { toast('Nom du compte requis.', 'danger'); return; }
    saveAccount(form);
    onSave();
  };

  return (
    <Modal title="Nouveau compte" onClose={onClose} width={480}>
      <div className="field">
        <label>Nom du compte</label>
        <input className="input" value={form.name} onChange={set('name')} />
      </div>
      <div className="field">
        <label>Type</label>
        <select className="select" value={form.account_type} onChange={set('account_type')}>
          {ACCOUNT_TYPES.map((t) => <option key={t} value={t}>{TYPE_LABELS[t]}</option>)}
        </select>
      </div>
      <div className="field">
        <label>Solde initial</label>
        <input className="input" type="number" value={form.initial_balance} onChange={set('initial_balance')} />
      </div>
      <div className="form-actions">
        <button className="btn" onClick={onClose}>Annuler</button>
        <button className="btn btn-primary" onClick={save}>Créer</button>
      </div>
    </Modal>
  );
}
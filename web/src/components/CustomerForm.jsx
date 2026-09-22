import { useState } from 'react';
import { saveCustomer } from '../api/catalogApi';
import { Modal, toast } from './ui';

export default function CustomerForm({ customer, onSave, onClose }) {
  const [form, setForm] = useState({
    first_name: customer?.first_name || '',
    last_name: customer?.last_name || '',
    company: customer?.company || '',
    email: customer?.email || '',
    phone: customer?.phone || '',
    address: customer?.address || '',
    city: customer?.city || '',
    customer_type: customer?.customer_type || 'RETAIL',
    credit_limit: customer?.credit_limit ?? 0,
  });
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const save = () => {
    if (!form.first_name.trim() || !form.last_name.trim()) {
      toast('Prénom et nom requis.', 'danger');
      return;
    }
    if (customer) saveCustomer({ ...customer, ...form });
    else saveCustomer(form);
    onSave();
  };

  return (
    <Modal title={customer ? 'Modifier le client' : 'Nouveau client'} onClose={onClose} width={560}>
      <div className="form-grid">
        <div className="field">
          <label>Prénom *</label>
          <input className="input" value={form.first_name} onChange={set('first_name')} />
        </div>
        <div className="field">
          <label>Nom *</label>
          <input className="input" value={form.last_name} onChange={set('last_name')} />
        </div>
        <div className="field">
          <label>Société</label>
          <input className="input" value={form.company} onChange={set('company')} />
        </div>
        <div className="field">
          <label>Type</label>
          <select className="select" value={form.customer_type} onChange={set('customer_type')}>
            <option value="RETAIL">Détail</option>
            <option value="WHOLESALE">Gros</option>
            <option value="CORPORATE">Société</option>
          </select>
        </div>
        <div className="field">
          <label>Téléphone</label>
          <input className="input" value={form.phone} onChange={set('phone')} />
        </div>
        <div className="field">
          <label>Email</label>
          <input className="input" value={form.email} onChange={set('email')} />
        </div>
        <div className="field">
          <label>Ville</label>
          <input className="input" value={form.city} onChange={set('city')} />
        </div>
        <div className="field">
          <label>Limite de crédit</label>
          <input className="input" type="number" min="0" value={form.credit_limit} onChange={set('credit_limit')} />
        </div>
      </div>
      <div className="field">
        <label>Adresse</label>
        <textarea className="textarea" value={form.address} onChange={set('address')} />
      </div>
      <div className="form-actions">
        <button className="btn" onClick={onClose}>Annuler</button>
        <button className="btn btn-primary" onClick={save}>{customer ? 'Enregistrer' : 'Créer'}</button>
      </div>
    </Modal>
  );
}
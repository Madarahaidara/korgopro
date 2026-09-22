import { useState } from 'react';
import { Modal, toast } from './ui';

/** Modale de création / édition d'un magasin. */
export default function StoreModal({ store, onSave, onClose }) {
  const [form, setForm] = useState({
    name: store?.name || '',
    address: store?.address || '',
    phone: store?.phone || '',
  });

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const save = () => {
    if (!form.name.trim()) {
      toast('Le nom du magasin est requis.', 'danger');
      return;
    }
    onSave(form);
  };

  return (
    <Modal title={store ? 'Modifier le magasin' : 'Nouveau magasin'} onClose={onClose} width={480}>
      <div className="form-grid">
        <div className="field">
          <label>Nom du magasin *</label>
          <input
            className="input"
            value={form.name}
            onChange={set('name')}
            placeholder="Ex : Magasin Cotonou"
          />
        </div>
        <div className="field">
          <label>Téléphone</label>
          <input className="input" value={form.phone} onChange={set('phone')} />
        </div>
      </div>
      <div className="field">
        <label>Adresse</label>
        <input className="input" value={form.address} onChange={set('address')} />
      </div>
      <div className="form-actions">
        <button className="btn" onClick={onClose}>Annuler</button>
        <button className="btn btn-primary" onClick={save}>
          {store ? 'Enregistrer' : 'Créer le magasin'}
        </button>
      </div>
    </Modal>
  );
}
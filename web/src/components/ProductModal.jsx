import { useState } from 'react';
import { saveProduct } from '../api/catalogApi';
import { Modal, toast } from './ui';

const CATEGORIES = ['GENERAL', 'ALIMENTATION', 'BOISSON', 'ELECTRONIQUE', 'VETEMENT', 'COSMETIQUE', 'QUINCAILLERIE', 'AUTRE'];

export default function ProductModal({ product, onSave, onClose }) {
  const [form, setForm] = useState({
    name: product?.name || '',
    category: product?.category || 'GENERAL',
    description: product?.description || '',
    quantity: product?.quantity ?? 0,
    min_stock: product?.min_stock ?? 5,
    purchase_price: product?.purchase_price ?? 0,
    sale_price: product?.sale_price ?? 0,
    location: product?.location || '',
  });

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const save = () => {
    if (!form.name.trim()) {
      toast('Le nom du produit est requis.', 'danger');
      return;
    }
    if (product) {
      saveProduct({ ...product, ...form });
    } else {
      saveProduct({ ...form });
    }
    onSave();
  };

  return (
    <Modal title={product ? 'Modifier le produit' : 'Nouveau produit'} onClose={onClose} width={560}>
      <div className="form-grid">
        <div className="field">
          <label>Nom du produit *</label>
          <input className="input" value={form.name} onChange={set('name')} />
        </div>
        <div className="field">
          <label>Catégorie</label>
          <select className="select" value={form.category} onChange={set('category')}>
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Quantité</label>
          <input className="input" type="number" min="0" value={form.quantity} onChange={set('quantity')} />
        </div>
        <div className="field">
          <label>Seuil d'alerte</label>
          <input className="input" type="number" min="0" value={form.min_stock} onChange={set('min_stock')} />
        </div>
        <div className="field">
          <label>Prix d'achat</label>
          <input className="input" type="number" min="0" value={form.purchase_price} onChange={set('purchase_price')} />
        </div>
        <div className="field">
          <label>Prix de vente</label>
          <input className="input" type="number" min="0" value={form.sale_price} onChange={set('sale_price')} />
        </div>
      </div>
      <div className="field">
        <label>Emplacement</label>
        <input className="input" value={form.location} onChange={set('location')} />
      </div>
      <div className="field">
        <label>Description</label>
        <textarea className="textarea" value={form.description} onChange={set('description')} />
      </div>
      <div className="form-actions">
        <button className="btn" onClick={onClose}>Annuler</button>
        <button className="btn btn-primary" onClick={save}>{product ? 'Enregistrer' : 'Créer'}</button>
      </div>
    </Modal>
  );
}
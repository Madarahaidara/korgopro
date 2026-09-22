import { useState } from 'react';
import { createProforma } from '../api/proformaApi';
import { listProducts, listCustomers } from '../api/catalogApi';
import { getSettings } from '../api/settingsApi';
import { formatMoney } from '../api/db';
import { Modal, toast } from './ui';
import Icon from './Icon';

export default function ProformaForm({ user, onSave, onClose }) {
  const [products] = useState(() => listProducts());
  const [customers] = useState(() => listCustomers());
  const [settings] = useState(() => getSettings());
  const [customerId, setCustomerId] = useState('');
  const [validUntil, setValidUntil] = useState('');
  const [discountPercent, setDiscountPercent] = useState(0);
  const [terms, setTerms] = useState('');
  const [lines, setLines] = useState([]);

  const taxRate = Number(settings.tax_rate) || 0;

  const addLine = () => {
    if (!products.length) { toast('Aucun produit.', 'danger'); return; }
    const p = products[0];
    setLines([...lines, {
      key: Date.now(), product_id: p.id, name: p.name,
      description: p.name, unit_price: p.sale_price, quantity: 1, line_total: p.sale_price,
    }]);
  };

  const updateLine = (key, patch) => {
    setLines(lines.map((l) => {
      if (l.key !== key) return l;
      const next = { ...l, ...patch };
      next.line_total = Number(next.unit_price) * Number(next.quantity);
      return next;
    }));
  };

  const subtotal = lines.reduce((s, l) => s + Number(l.line_total || 0), 0);
  const discount = (subtotal * (Number(discountPercent) || 0)) / 100;
  const tax = ((subtotal - discount) * taxRate) / 100;
  const total = subtotal - discount + tax;

  const save = () => {
    if (!lines.length) { toast('Ajoutez au moins une ligne.', 'danger'); return; }
    createProforma({
      customer_id: customerId ? Number(customerId) : null,
      created_by: user.id,
      valid_until: validUntil,
      discount_percent: Number(discountPercent),
      terms_and_conditions: terms,
      items: lines.map((l) => ({
        product_id: l.product_id,
        description: l.description,
        quantity: Number(l.quantity),
        unit_price: Number(l.unit_price),
        line_total: Number(l.line_total),
      })),
    });
    onSave();
  };

  return (
    <Modal title="Nouvelle proforma" onClose={onClose} width={720}>
      <div className="form-grid">
        <div className="field">
          <label>Client</label>
          <select className="select" value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
            <option value="">— Aucun —</option>
            {customers.map((c) => <option key={c.id} value={c.id}>{c.full_name}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Valable jusqu'au</label>
          <input className="input" type="date" value={validUntil} onChange={(e) => setValidUntil(e.target.value)} />
        </div>
      </div>

      <div className="flex justify-between mb-12">
        <div className="field" style={{ marginBottom: 0 }}>
          <label>Remise (%)</label>
          <input className="input" type="number" min="0" max="100" style={{ width: 120 }} value={discountPercent} onChange={(e) => setDiscountPercent(e.target.value)} />
        </div>
        <button className="btn btn-sm" onClick={addLine}>+ Ajouter</button>
      </div>

      <div className="card mb-12" style={{ background: '#fafbfc' }}>
        {lines.map((l, i) => (
          <div className="line-row" key={l.key}>
            <span className="text-muted" style={{ width: 20, alignSelf: 'center' }}>{i + 1}</span>
            <select
              className="select grow"
              value={l.product_id}
              onChange={(e) => {
                const p = products.find((x) => x.id === Number(e.target.value));
                updateLine(l.key, { product_id: p.id, description: p.name, name: p.name, unit_price: p.sale_price, quantity: 1 });
              }}
            >
              {products.map((p) => (
                <option key={p.id} value={p.id}>{p.name} ({formatMoney(p.sale_price, settings.currency)})</option>
              ))}
            </select>
            <input className="input" type="number" min="1" style={{ width: 90 }} value={l.quantity} onChange={(e) => updateLine(l.key, { quantity: e.target.value })} />
            <span style={{ alignSelf: 'center', minWidth: 130, textAlign: 'right' }}><b>{formatMoney(l.line_total, settings.currency)}</b></span>
            <button className="btn btn-sm btn-danger" onClick={() => setLines(lines.filter((x) => x.key !== l.key))}><Icon name="cancel" size={14} /></button>
          </div>
        ))}
        {!lines.length && <div className="empty" style={{ padding: 20 }}>Cliquez sur « + Ajouter ».</div>}
      </div>

      <div className="field">
        <label>Conditions</label>
        <textarea className="textarea" value={terms} onChange={(e) => setTerms(e.target.value)} />
      </div>

      <div className="flex justify-between align-end">
        <button className="btn" onClick={onClose}>Annuler</button>
        <div className="text-right">
          <div className="align-end"><span className="text-muted">Sous-total</span> <b style={{ minWidth: 110, display: 'inline-block', textAlign: 'right' }}>{formatMoney(subtotal, settings.currency)}</b></div>
          <div className="align-end"><span className="text-muted">Remise</span> <b style={{ minWidth: 110, display: 'inline-block', textAlign: 'right' }}>-{formatMoney(discount, settings.currency)}</b></div>
          <div className="align-end"><span className="text-muted">Taxe ({taxRate}%)</span> <b style={{ minWidth: 110, display: 'inline-block', textAlign: 'right' }}>{formatMoney(tax, settings.currency)}</b></div>
          <div style={{ fontSize: 20, fontWeight: 800 }}>Total : {formatMoney(total, settings.currency)}</div>
        </div>
      </div>

      <div className="form-actions">
        <button className="btn btn-success btn-lg" onClick={save}>Créer la proforma</button>
      </div>
    </Modal>
  );
}
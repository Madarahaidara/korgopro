import { useMemo, useRef, useState } from 'react';
import { createSale } from '../api/salesApi';
import { listProducts, listCustomers } from '../api/catalogApi';
import { getSettings } from '../api/settingsApi';
import { formatMoney } from '../api/db';
import { Modal, toast } from './ui';
import Icon from './Icon';

/**
 * Caisse rapide : recherche/clic produit, panier avec quantités +/-,
 * prix éditable, contrôle du stock, remise globale et calcul du rendu
 * de monnaie pour les paiements en espèces.
 */
export default function NewSaleModal({ user, onSave, onClose }) {
  const [products] = useState(() => listProducts());
  const [customers] = useState(() => listCustomers());
  const [settings] = useState(() => getSettings());
  const [customerId, setCustomerId] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('CASH');
  const [lines, setLines] = useState([]);
  const [note, setNote] = useState('');
  const [query, setQuery] = useState('');
  const [discount, setDiscount] = useState('');
  const [amountPaid, setAmountPaid] = useState('');
  const searchRef = useRef(null);

  const taxRate = Number(settings.tax_rate) || 0;

  /** Produits correspondant à la recherche (nom, code, code-barres). */
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const base = !q
      ? products
      : products.filter((p) =>
          (p.name || '').toLowerCase().includes(q) ||
          String(p.code || '').toLowerCase().includes(q) ||
          String(p.barcode || '').includes(q));
    // Les produits disponibles d'abord, puis par nom.
    return base
      .slice()
      .sort((a, b) => Number(b.quantity > 0) - Number(a.quantity > 0) ||
        String(a.name).localeCompare(String(b.name)))
      .slice(0, 12);
  }, [products, query]);

  /** Ajoute un produit au panier (incrémente s'il y est déjà), en respectant le stock. */
  const addToCart = (p) => {
    if (!p) return;
    if (p.isOutOfStock) {
      toast(`« ${p.name} » est en rupture de stock.`, 'danger');
      return;
    }
    setLines((prev) => {
      const existing = prev.find((l) => l.product_id === p.id);
      if (existing) {
        if (existing.quantity + 1 > (p.quantity || 0)) {
          toast(`Stock insuffisant : ${p.quantity} unité(s) de « ${p.name} ».`, 'danger');
          return prev;
        }
        return prev.map((l) => (l.product_id === p.id
          ? { ...l, quantity: l.quantity + 1, line_total: (l.quantity + 1) * Number(l.unit_price) }
          : l));
      }
      return [...prev, {
        key: `${p.id}-${Date.now()}`,
        product_id: p.id,
        name: p.name,
        unit_price: Number(p.sale_price) || 0,
        quantity: 1,
        line_total: Number(p.sale_price) || 0,
        max_qty: p.quantity || 0,
      }];
    });
  };

  /** Entrée dans la recherche : ajoute le premier résultat (compatible lecteur code-barres). */
  const onSearchKeyDown = (e) => {
    if (e.key === 'Enter' && filtered.length > 0) {
      addToCart(filtered[0]);
      setQuery('');
      searchRef.current && searchRef.current.focus();
    }
  };

  const updateLine = (key, patch) => {
    setLines(lines.map((l) => {
      if (l.key !== key) return l;
      const next = { ...l, ...patch };
      if (patch.quantity !== undefined) {
        const qty = Math.max(1, Number(patch.quantity) || 1);
        if (next.max_qty > 0 && qty > next.max_qty) {
          toast(`Stock insuffisant : ${next.max_qty} unité(s) de « ${next.name} ».`, 'danger');
          next.quantity = next.max_qty;
        } else {
          next.quantity = qty;
        }
      }
      next.line_total = (Number(next.unit_price) || 0) * (Number(next.quantity) || 0);
      return next;
    }));
  };

  const removeLine = (key) => setLines(lines.filter((l) => l.key !== key));

  const subtotal = lines.reduce((s, l) => s + Number(l.line_total || 0), 0);
  const discountValue = Math.min(Math.max(Number(discount) || 0, 0), subtotal);
  const taxable = subtotal - discountValue;
  const tax = (taxable * taxRate) / 100;
  const total = taxable + tax;
  const paid = paymentMethod === 'CASH' ? Math.max(Number(amountPaid) || 0, 0) : total;
  const change = Math.max(paid - total, 0);

  const save = () => {
    if (lines.length === 0) {
      toast('Ajoutez au moins un produit.', 'danger');
      return;
    }
    if (paymentMethod === 'CASH' && paid > 0 && paid < total) {
      toast('Le montant reçu est inférieur au total.', 'danger');
      return;
    }
    const sale = createSale({
      customer_id: customerId ? Number(customerId) : null,
      cashier_id: user.id,
      payment_method: paymentMethod,
      notes: note,
      discount_amount: discountValue,
      subtotal,
      tax_amount: tax,
      amount_paid: paid,
      items: lines.map((l) => ({
        product_id: l.product_id,
        quantity: Number(l.quantity),
        unit_price: Number(l.unit_price),
        line_total: Number(l.line_total),
      })),
    });
    toast(change > 0
      ? `Vente ${sale.number} enregistrée. Monnaie à rendre : ${formatMoney(change, settings.currency)}`
      : `Vente ${sale.number} enregistrée avec succès.`);
    onSave();
  };

  return (
    <Modal title="Nouvelle vente" onClose={onClose} width={1020}>
      <div style={{ display: 'flex', gap: 16, alignItems: 'stretch' }}>
        {/* ===== Colonne gauche : sélection des produits ===== */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="flex justify-between mb-12">
            <b>Produits</b>
            <span className="text-muted" style={{ fontSize: 12 }}>
              Cliquez un produit ou Entrée pour l'ajouter
            </span>
          </div>
          <input
            ref={searchRef}
            className="input mb-12"
            placeholder="Rechercher (nom, code, code-barres)…"
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onSearchKeyDown}
          />
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8,
            maxHeight: 340, overflowY: 'auto', paddingRight: 4,
          }}>
            {filtered.map((p) => (
              <button
                key={p.id}
                className="card"
                style={{
                  textAlign: 'left', cursor: p.isOutOfStock ? 'not-allowed' : 'pointer',
                  padding: 10, border: '1px solid #e5e7eb', opacity: p.isOutOfStock ? 0.45 : 1,
                }}
                onClick={() => addToCart(p)}
              >
                <div style={{
                  fontWeight: 700, fontSize: 13, marginBottom: 4,
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                }}>{p.name}</div>
                <div className="flex justify-between" style={{ fontSize: 12 }}>
                  <b style={{ color: '#059669' }}>{formatMoney(p.sale_price, settings.currency)}</b>
                  <span className={p.isOutOfStock ? 'text-muted' : ''}>
                    {p.isOutOfStock ? 'Rupture' : `Stock : ${p.quantity}`}
                  </span>
                </div>
              </button>
            ))}
            {filtered.length === 0 && (
              <div className="empty" style={{ gridColumn: '1 / -1', padding: 20 }}>
                Aucun produit ne correspond.
              </div>
            )}
          </div>
        </div>

        {/* ===== Colonne droite : panier + encaissement ===== */}
        <div style={{ width: 380, display: 'flex', flexDirection: 'column' }}>
          <div className="form-grid mb-12">
            <div className="field">
              <label>Client</label>
              <select className="select" value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
                <option value="">Client comptoir</option>
                {customers.map((c) => <option key={c.id} value={c.id}>{c.full_name}</option>)}
              </select>
            </div>
            <div className="field">
              <label>Paiement</label>
              <select className="select" value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}>
                <option value="CASH">Espèces</option>
                <option value="MOBILE_MONEY">Mobile Money</option>
                <option value="BANK">Banque</option>
              </select>
            </div>
          </div>

          <div className="card mb-12" style={{ background: '#fafbfc', flex: 1, overflowY: 'auto', maxHeight: 220 }}>
            {lines.map((l) => (
              <div className="line-row" key={l.key}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 13, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{l.name}</div>
                  <div className="flex align-end" style={{ gap: 4 }}>
                    <button className="btn btn-sm" style={{ padding: '0 8px' }} onClick={() => updateLine(l.key, { quantity: Number(l.quantity) - 1 })}></button>
                    <input
                      className="input" type="number" min="1" style={{ width: 56, textAlign: 'center', padding: '2px 4px' }}
                      value={l.quantity}
                      onChange={(e) => updateLine(l.key, { quantity: e.target.value })}
                    />
                    <button className="btn btn-sm" style={{ padding: '0 8px' }} onClick={() => updateLine(l.key, { quantity: Number(l.quantity) + 1 })}>+</button>
                    <input
                      className="input" type="number" min="0" step="any" style={{ width: 90, padding: '2px 6px' }}
                      title="Prix unitaire"
                      value={l.unit_price}
                      onChange={(e) => updateLine(l.key, { unit_price: e.target.value })}
                    />
                  </div>
                </div>
                <span style={{ alignSelf: 'center', minWidth: 90, textAlign: 'right' }}>
                  <b>{formatMoney(l.line_total, settings.currency)}</b>
                </span>
                <button className="btn btn-sm btn-danger" onClick={() => removeLine(l.key)}><Icon name="cancel" size={14} /></button>
              </div>
            ))}
            {lines.length === 0 && (
              <div className="empty" style={{ padding: 24 }}>
                Panier vide — cliquez un produit à gauche.
              </div>
            )}
          </div>

          <div className="field">
            <label>Note (facultatif)</label>
            <input className="input" value={note} onChange={(e) => setNote(e.target.value)} />
          </div>

          <div className="flex justify-between align-end mt-8">
            <div className="field" style={{ width: 130 }}>
              <label>Remise</label>
              <input className="input" type="number" min="0" step="any" value={discount}
                onChange={(e) => setDiscount(e.target.value)} placeholder="0" />
            </div>
            {paymentMethod === 'CASH' && (
              <div className="field" style={{ width: 130 }}>
                <label>Montant reçu</label>
                <input className="input" type="number" min="0" step="any" value={amountPaid}
                  onChange={(e) => setAmountPaid(e.target.value)} placeholder={String(Math.round(total))} />
              </div>
            )}
            <div className="text-right">
              <div className="align-end"><span className="text-muted">Sous-total</span> <b style={{ minWidth: 100, display: 'inline-block', textAlign: 'right' }}>{formatMoney(subtotal, settings.currency)}</b></div>
              {discountValue > 0 && (
                <div className="align-end"><span className="text-muted">Remise</span> <b style={{ minWidth: 100, display: 'inline-block', textAlign: 'right' }}>-{formatMoney(discountValue, settings.currency)}</b></div>
              )}
              <div className="align-end"><span className="text-muted">Taxe ({taxRate}%)</span> <b style={{ minWidth: 100, display: 'inline-block', textAlign: 'right' }}>{formatMoney(tax, settings.currency)}</b></div>
              <div style={{ fontSize: 20, fontWeight: 800 }}>Total : {formatMoney(total, settings.currency)}</div>
              {paymentMethod === 'CASH' && paid > 0 && (
                <div style={{ fontWeight: 700, color: change > 0 ? '#059669' : undefined }}>
                  {change > 0 ? `À rendre : ${formatMoney(change, settings.currency)}` : 'Payé exactement '}<Icon name="check" size={16} style={{ verticalAlign: '-2px' }} />
                </div>
              )}
            </div>
          </div>

          <div className="form-actions">
            <button className="btn" onClick={onClose}>Annuler</button>
            <button className="btn btn-success btn-lg" onClick={save} disabled={lines.length === 0}>
              <Icon name="cash" size={16} style={{ verticalAlign: '-2px' }} /> Encaisser {lines.length > 0 ? formatMoney(total, settings.currency) : ''}
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
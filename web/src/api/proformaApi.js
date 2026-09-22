// ============================================================================
// Service des proformas (devis).
// Reprend la logique de core/proforma_invoice_manager.py.
// ============================================================================
import { db, nextDocumentNumber } from './db';
import { getCustomer, getProduct } from './catalogApi';

export const PROFORMA_STATUS = [
  'BROUILLON',
  'EN_ATTENTE',
  'ENVOYEE',
  'ACCEPTEE',
  'REFUSEE',
  'EXPIREE',
  'CONVERTIE',
];

/** Liste des proformas avec client enrichi, triées par date décroissante. */
export function listProformas() {
  return db.data.proformas
    .slice()
    .sort((a, b) => new Date(b.created_date) - new Date(a.created_date))
    .map(enrichProforma);
}

export function getProforma(id) {
  const p = db.data.proformas.find((x) => x.id === Number(id));
  return p ? enrichProforma(p) : null;
}

function enrichProforma(p) {
  const customer = p.customer_id ? getCustomer(p.customer_id) : null;
  const creator = db.data.users.find((u) => u.id === p.created_by);
  const items = (p.items || []).map((it) => {
    const product = it.product_id ? getProduct(it.product_id) : null;
    return { ...it, product };
  });
  return { ...p, customer, creator, items };
}

/** Crée une nouvelle proforma. */
export function createProforma({ customer_id, created_by, valid_until, items, discount_percent = 0, notes = '', terms_and_conditions = '' }) {
  const subtotal = items.reduce((sum, it) => sum + Number(it.line_total || 0), 0);
  const discount_amount = Number(discount_percent)
    ? (subtotal * Number(discount_percent)) / 100
    : 0;
  const tax_percent = Number(db.data.settings.tax_rate) || 0;
  const tax_amount = ((subtotal - discount_amount) * tax_percent) / 100;
  const total_amount = subtotal - discount_amount + tax_amount;

  const proforma = {
    id: Math.max(0, ...db.data.proformas.map((p) => p.id)) + 1,
    number: nextDocumentNumber(db.data.settings.proforma_prefix || 'PRO', db.data.proformas),
    customer_id: customer_id || null,
    created_by: Number(created_by),
    created_date: new Date().toISOString(),
    valid_until: valid_until || null,
    subtotal,
    discount_percent: Number(discount_percent) || 0,
    discount_amount,
    tax_percent,
    tax_amount,
    total_amount,
    status: 'BROUILLON',
    notes: notes || '',
    terms_and_conditions: terms_and_conditions || '',
    currency: db.data.settings.currency,
    converted_to_sale_id: null,
    items: items.map((it, i) => ({
      id: i + 1,
      product_id: it.product_id || null,
      description: it.description,
      quantity: Number(it.quantity),
      unit_price: Number(it.unit_price),
      discount_percent: Number(it.discount_percent || 0),
      discount_amount: Number(it.discount_amount || 0),
      line_total: Number(it.line_total),
    })),
  };

  db.data.proformas.push(proforma);
  db.persist();
  return enrichProforma(proforma);
}

/** Met à jour le statut d'une proforma. */
export function setProformaStatus(id, status) {
  const p = db.data.proformas.find((x) => x.id === Number(id));
  if (p) {
    p.status = status;
    db.persist();
  }
  return p ? enrichProforma(p) : null;
}

/** Convertit une proforma en vente (lien bidirectionnel). */
export function convertProformaToSale(id, cashier_id, payment_method) {
  const p = db.data.proformas.find((x) => x.id === Number(id));
  if (!p) return null;
  p.status = 'CONVERTIE';

  const sale = {
    id: Math.max(0, ...db.data.sales.map((s) => s.id)) + 1,
    number: nextDocumentNumber(db.data.settings.invoice_prefix || 'FAC', db.data.sales),
    customer_id: p.customer_id,
    cashier_id: Number(cashier_id),
    sale_date: new Date().toISOString(),
    subtotal: p.subtotal,
    discount_amount: p.discount_amount,
    tax_amount: p.tax_amount,
    total_amount: p.total_amount,
    amount_paid: p.total_amount,
    change_amount: 0,
    payment_method: payment_method || 'CASH',
    payment_status: 'PAID',
    sale_status: 'COMPLETED',
    type_document: 'FACTURE',
    origine_proforma_id: p.id,
    date_conversion: new Date().toISOString(),
    statut: 'EMISE',
    currency: p.currency,
    items: p.items.map((it, i) => ({
      id: i + 1,
      product_id: it.product_id,
      quantity: it.quantity,
      unit_price: it.unit_price,
      discount_percent: it.discount_percent,
      discount_amount: it.discount_amount,
      line_total: it.line_total,
    })),
  };

  db.data.sales.push(sale);
  p.converted_to_sale_id = sale.id;
  db.persist();
  return sale;
}
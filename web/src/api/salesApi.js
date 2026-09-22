// ============================================================================
// Service des ventes (factures définitives).
// Reprend le modèle sale_models.py (Sale, SaleItem) et la logique de caisse.
// ============================================================================
import { db, nextDocumentNumber } from './db';
import { getCustomer, getProduct } from './catalogApi';
import { getActiveStoreId } from './storesApi';

/** Liste les ventes avec relations client/caissier enrichies (magasin actif). */
export function listSales(storeId = null) {
  const sid = storeId === 'all' ? null : storeId != null ? Number(storeId) : getActiveStoreId();
  return db.data.sales
    .filter((s) => sid == null || s.store_id === sid)
    .slice()
    .sort((a, b) => new Date(b.sale_date) - new Date(a.sale_date))
    .map(enrichSale);
}

export function getSale(id) {
  const sale = db.data.sales.find((s) => s.id === Number(id));
  return sale ? enrichSale(sale) : null;
}

function enrichSale(sale) {
  const customer = sale.customer_id ? getCustomer(sale.customer_id) : null;
  const cashier = db.data.users.find((u) => u.id === sale.cashier_id);
  const items = (sale.items || []).map((it) => {
    const product = it.product_id ? getProduct(it.product_id) : null;
    return { ...it, product };
  });
  return { ...sale, customer, cashier, items };
}

/** Crée une vente, débite le stock et enregistre un mouvement de trésorerie. */
export function createSale({ customer_id, items, discount_amount = 0, tax_amount = 0, cashier_id, payment_method = 'CASH', notes = '', amount_paid = 0 }) {
  const subtotal = items.reduce((sum, it) => sum + Number(it.line_total || 0), 0);
  const total_amount = subtotal - Number(discount_amount) + Number(tax_amount);
  const paid = Math.max(Number(amount_paid) || 0, 0);
  // Statut de paiement : soldé si le montant reçu couvre le total,
  // partiel s'il en couvre une partie, en attente sinon.
  const payment_status = paid >= total_amount && paid > 0
    ? 'PAID'
    : paid > 0 ? 'PARTIAL' : 'PENDING';
  const sale = {
    id: Math.max(0, ...db.data.sales.map((s) => s.id)) + 1,
    store_id: getActiveStoreId(),
    number: nextDocumentNumber('FAC', db.data.sales),
    customer_id: customer_id || null,
    cashier_id: Number(cashier_id),
    sale_date: new Date().toISOString(),
    subtotal,
    discount_amount: Number(discount_amount),
    tax_amount: Number(tax_amount),
    total_amount,
    amount_paid: paid,
    change_amount: Math.max(paid - total_amount, 0),
    payment_method,
    payment_status,
    sale_status: 'COMPLETED',
    type_document: 'FACTURE',
    statut: 'EMISE',
    currency: db.data.settings.currency,
    notes,
    created_at: new Date().toISOString(),
    items: items.map((it, i) => ({
      id: i + 1,
      product_id: it.product_id,
      quantity: Number(it.quantity),
      unit_price: Number(it.unit_price),
      discount_percent: Number(it.discount_percent || 0),
      discount_amount: Number(it.discount_amount || 0),
      line_total: Number(it.line_total),
    })),
  };

  db.data.sales.push(sale);

  // Débite le stock
  items.forEach((it) => {
    const p = getProduct(it.product_id);
    if (p && it.product_id) {
      const target = db.data.products.find((x) => x.id === Number(it.product_id));
      if (target) target.quantity = Math.max(0, (target.quantity || 0) - Number(it.quantity));
    }
  });

  // Enregistre l'entrée de trésorerie sur le compte par défaut
  recordCashIn(sale, total_amount);

  db.persist();
  return enrichSale(sale);
}

/** Enregistre un mouvement de trésorerie (entrée de caisse) pour une vente. */
function recordCashIn(sale, amount) {
  const account = db.data.treasuryAccounts.find((a) => a.is_default) || db.data.treasuryAccounts[0];
  if (!account) return;
  account.current_balance = (account.current_balance || 0) + amount;
  db.data.treasuryMovements.unshift({
    id: Math.max(0, ...(db.data.treasuryMovements || []).map((m) => m.id)) + 1,
    account_id: account.id,
    movement_type: 'IN',
    amount,
    date: sale.sale_date,
    reference: sale.number,
    description: `Vente ${sale.number}`,
    category: 'Ventes',
    reference_type: 'SALE',
    reference_id: sale.id,
    created_at: new Date().toISOString(),
  });
}

/** Calcule les sous-totaux d'une vente unitée (prix, remise, ligne). */
export function computeLine(line) {
  const unit_price = Number(line.unit_price) || 0;
  const quantity = Number(line.quantity) || 0;
  const discount_percent = Number(line.discount_percent) || 0;
  const lineSubtotal = unit_price * quantity;
  const discount_amount =
    Number(line.discount_amount) || 0 + (lineSubtotal * discount_percent) / 100;
  const line_total = lineSubtotal - discount_amount;
  return { lineSubtotal, discount_amount, line_total };
}
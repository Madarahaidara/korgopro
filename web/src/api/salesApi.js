// ============================================================================
// Service des ventes (factures définitives).
// Reprend le modèle sale_models.py (Sale, SaleItem) et la logique de caisse.
// ============================================================================
import { db, nextDocumentNumber, formatMoney } from './db';
import { getCustomer, getProduct } from './catalogApi';
import { getActiveStoreId } from './storesApi';

/** Tolérance des arrondis sur les montants (identique au mobile et au RPC). */
const EPSILON = 0.001;

/**
 * Un paiement est « différé » quand il laisse obligatoirement un reste dû
 * possible : c'est le cas du crédit, où ce qui est saisi est un acompte.
 * Les autres moyens (Mobile Money, carte, virement…) sont réputés immédiats.
 */
export function isCreditPayment(method) {
  const value = String(method || '').toUpperCase();
  return value === 'CRÉDIT' || value === 'CREDIT' || value === 'A_TERME';
}

/** Reste dû d'une vente (0 si elle est soldée ou surpayée). */
export function saleDue(sale) {
  return Math.max(Number(sale?.total_amount || 0) - Number(sale?.amount_paid || 0), 0);
}

/** Liste des ventes restant à encaisser (crédits + paiements partiels). */
export function listCreditSales(storeId = null) {
  return listSales(storeId).filter((s) => s.sale_status !== 'CANCELLED' && s.due > EPSILON);
}

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
  return { ...sale, customer, cashier, items, due: saleDue(sale) };
}

/** Crée une vente, débite le stock et enregistre un mouvement de trésorerie. */
export function createSale({ customer_id, items, discount_amount = 0, tax_amount = 0, cashier_id, payment_method = 'CASH', notes = '', amount_paid = 0 }) {
  const subtotal = items.reduce((sum, it) => sum + Number(it.line_total || 0), 0);
  const total_amount = subtotal - Number(discount_amount) + Number(tax_amount);
  // Un crédit accepte un acompte (0 = vente à terme) ; les autres moyens sont
  // réputés encaissés en totalité lorsqu'aucun montant n'est saisi.
  const credit = isCreditPayment(payment_method);
  const requested = Math.max(Number(amount_paid) || 0, 0);
  const paid = credit ? Math.min(requested, total_amount) : (requested > 0 ? requested : total_amount);
  const change_amount = Math.max(paid - total_amount, 0);
  const due = Math.max(total_amount - paid, 0);
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
    change_amount,
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

  // Trésorerie : uniquement l'argent réellement reçu. Un crédit sans acompte
  // ne doit donc rien faire entrer en caisse (avant, la totalité y entrait).
  const cashIn = Math.max(paid - change_amount, 0);
  if (cashIn > EPSILON) recordCashIn(sale, cashIn);

  // Le reste dû devient la dette du client (compteur `customers.balance`).
  if (due > EPSILON && sale.customer_id) {
    const target = db.data.customers.find((c) => c.id === Number(sale.customer_id));
    if (target) target.balance = Number(target.balance || 0) + due;
  }

  db.persist();
  return enrichSale(sale);
}

/**
 * Encaisse (totalement ou partiellement) une facture impayée : met à jour la
 * vente, la trésorerie et le solde dû du client.
 */
export function receivePayment({ sale_id, amount, payment_method = null, notes = '' }) {
  const sale = db.data.sales.find((s) => s.id === Number(sale_id));
  if (!sale) throw new Error('Vente introuvable.');
  if (sale.sale_status === 'CANCELLED') throw new Error('Cette vente est annulée.');

  const due = saleDue(sale);
  const value = Math.max(Number(amount) || 0, 0);
  if (value <= 0) throw new Error('Le montant encaissé doit être supérieur à 0.');
  if (value > due + EPSILON) {
    throw new Error(`Montant supérieur au reste dû (${formatMoney(due, db.data.settings.currency)}).`);
  }

  sale.amount_paid = Number(sale.amount_paid || 0) + value;
  const settled = saleDue(sale) <= EPSILON;
  sale.payment_status = settled ? 'PAID' : 'PARTIAL';
  sale.statut = settled ? 'PAYEE' : 'PARTIELLEMENT_PAYEE';
  if (payment_method) sale.payment_method = payment_method;
  if (notes) sale.notes = [sale.notes, notes].filter(Boolean).join(' • ');

  recordCashIn(sale, value, `Encaissement facture ${sale.number}`);

  // La dette du client diminue d'autant.
  if (sale.customer_id) {
    const target = db.data.customers.find((c) => c.id === Number(sale.customer_id));
    if (target) target.balance = Math.max(Number(target.balance || 0) - value, 0);
  }

  db.persist();
  return enrichSale(sale);
}

/** Enregistre un mouvement de trésorerie (entrée de caisse) pour une vente. */
function recordCashIn(sale, amount, description = null) {
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
    description: description || `Vente ${sale.number}`,
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
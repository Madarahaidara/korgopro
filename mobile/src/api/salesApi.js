// ============================================================================
// Ventes : lecture Supabase + écritures via les RPC `app_create_sale` et
// `app_register_payment`. Les écrans passent par ici, jamais par rpc.js.
// Miroir de web/src/api/salesApi.js
// (listSales/getSale/createSale/receivePayment/computeLine/isCreditPayment).
// ============================================================================
import {
  getSale as getSaleRaw,
  listOpenSales,
  listRecentSales,
  listTodaySales,
} from './dataApi';
import { cancelSale as cancelSaleRpc, createSale as createSaleRpc, registerPayment as registerPaymentRpc } from './rpc';
import { todayBounds } from '../lib/format';

/** Ventes récentes du magasin actif (tri décroissant). */
export async function listSales({ storeId = null, limit = 60 } = {}) {
  return listRecentSales({ storeId, limit });
}

/** Une vente par identifiant — requête ciblée (pas de scan de liste). */
export async function getSale(id, { storeId = null } = {}) {
  return getSaleRaw(id, { storeId });
}

/** Ventes du jour (stats caisse). */
export async function listSalesToday(storeId) {
  return listTodaySales(storeId, todayBounds());
}

/** Factures à encaisser (crédits / partiels). */
export async function listSalesOpen(args) {
  return listOpenSales(args);
}

/** Crée une vente via la RPC transactionnelle (recalcule tout côté serveur). */
export async function createSale(payload) {
  return createSaleRpc(payload);
}

/**
 * Encaisse un paiement sur une facture (crédit ou paiement partiel).
 * `app_register_payment` refuse tout montant supérieur au reste dû, crédite la
 * trésorerie et recalcule le statut de la facture (comme
 * core/invoice_register_manager.py côté desktop).
 */
export async function registerPayment(payload) {
  return registerPaymentRpc(payload);
}

/**
 * Annule une vente : la RPC `app_cancel_sale` remet le stock, efface la dette
 * du client (crédit), compense les encaissements en trésorerie et marque la
 * facture ANNULEE / CANCELLED dans UNE transaction.
 *
 * Refus serveur (exception portant le message) si le rôle n'a pas la
 * permission `cancel_sales` (42501) ou si la facture est déjà annulée.
 */
export async function cancelSale(saleId, reason = null) {
  return cancelSaleRpc({ saleId, reason });
}

/**
 * Un paiement est « différé » quand il laisse obligatoirement un reste dû
 * possible : c'est le cas du crédit, où ce qui est saisi est un acompte.
 * Les autres moyens (Mobile Money, carte…) sont réputés immédiats.
 * Miroir de web/src/api/salesApi.js (isCreditPayment) : mêmes valeurs.
 */
export function isCreditPayment(method) {
  const value = String(method || '').toUpperCase();
  return value === 'CRÉDIT' || value === 'CREDIT' || value === 'A_TERME';
}

/** Reste dû d'une vente (0 si elle est soldée ou surpayée). */
export function saleDue(sale) {
  return Math.max(
    Number(sale?.total_amount || 0) - Number(sale?.amount_paid || 0),
    0
  );
}

/** Sous-totaux d'une ligne (copie de web salesApi.computeLine). */
export function computeLine(line) {
  const unitPrice = Number(line.unit_price) || 0;
  const quantity = Number(line.quantity) || 0;
  const discountPercent = Number(line.discount_percent) || 0;
  const lineSubtotal = unitPrice * quantity;
  const discountAmount = Number(line.discount_amount) || (0 + (lineSubtotal * discountPercent) / 100);
  const lineTotal = lineSubtotal - discountAmount;
  return { lineSubtotal, discount_amount: discountAmount, line_total: lineTotal };
}

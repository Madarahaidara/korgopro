// ============================================================================
// Écritures métier (mobile) — appels des RPC PostgreSQL `app_*`.
//
// POURQUOI PAS D'INSERT DIRECT ?
//   supabase_rls_policies.sql réserve l'écriture de `sales`, `sale_items`,
//   `payments`, `products`, `treasury_*` et `inventory_movements` aux
//   administrateurs (`app_security.is_admin()`). Un caissier reçoit donc une
//   erreur 42501 s'il écrit en direct — ce qui est le comportement voulu.
//
//   Les RPC `app_*` (supabase_mobile_rpc.sql) vérifient le rôle côté serveur,
//   recalculent les montants, et exécutent vente + stock + trésorerie + journal
//   dans UNE SEULE transaction : aucune donnée à moitié écrite.
//
// CONTRAT DE RETOUR COMMUN : jsonb { ok: bool, message: text, ... }
//   * ok = false  -> refus métier (message affichable), la transaction n'a rien
//                    écrit ;
//   * erreur HTTP -> droits insuffisants, réseau, schéma non installé.
// ============================================================================
import { friendlyError, requireClient } from './supabase';
import { config } from '../config';

/** Appelle une RPC et transforme tout refus en exception porteuse de message. */
async function callRpc(name, params) {
  const client = requireClient();
  const { data, error } = await client.rpc(name, params);
  if (error) {
    const err = new Error(friendlyError(error));
    err.code = error.code;
    err.rpc = name;
    throw err;
  }
  if (data && typeof data === 'object' && data.ok === false) {
    const err = new Error(data.message || `Opération refusée par ${name}.`);
    err.rpc = name;
    err.refused = true;
    throw err;
  }
  return data;
}

/**
 * Enregistre une vente (caisse).
 * `items` : [{ product_id, quantity, unit_price, discount_percent?, discount_amount?, notes? }]
 */
export function createSale({
  items,
  storeId = null,
  customerId = null,
  discountAmount = 0,
  taxAmount = 0,
  paymentMethod = 'CASH',
  amountPaid = 0,
  notes = '',
  accountId = null,
}) {
  return callRpc('app_create_sale', {
    p_items: items,
    p_store_id: storeId,
    p_customer_id: customerId,
    p_discount_amount: discountAmount,
    p_tax_amount: taxAmount,
    p_payment_method: paymentMethod,
    p_amount_paid: amountPaid,
    p_notes: notes,
    p_currency: config.currency,
    p_account_id: accountId,
  });
}

/** Encaisse un paiement sur une facture (crédit ou paiement partiel). */
export function registerPayment({
  saleId,
  amount,
  paymentMethod = null,
  accountId = null,
  notes = '',
}) {
  return callRpc('app_register_payment', {
    p_sale_id: saleId,
    p_amount: amount,
    p_payment_method: paymentMethod,
    p_account_id: accountId,
    p_notes: notes,
  });
}

/**
 * Annule une vente : remet le stock, efface la dette du client (crédit),
 * compense les encaissements en trésorerie et passe la facture en
 * ANNULEE / CANCELLED — même effet que cancel_sale côté desktop.
 *
 * Droits serveur : `cancel_sales` (ADMIN, GESTIONNAIRE, SUPERVISEUR). Un
 * caissier reçoit une erreur 42501 (matrice core/permissions.py).
 *
 * `reason` : motif obligatoire côté UI (3 caractères minimum) — il est repris
 * dans `sales.notes` et dans le journal `sale_logs`.
 */
export function cancelSale({ saleId, reason = null }) {
  return callRpc('app_cancel_sale', {
    p_sale_id: saleId,
    p_reason: reason,
  });
}

/**
 * Mouvement de stock.
 * `type` : IN (entrée), OUT (sortie), ADJUST (ajustement positif), LOSS (perte).
 */
export function stockMovement({
  productId,
  type,
  quantity,
  reason = null,
  unitCost = null,
  reference = null,
  notes = null,
  storeId = null,
}) {
  return callRpc('app_stock_movement', {
    p_product_id: productId,
    p_movement_type: type,
    p_quantity: quantity,
    p_reason: reason,
    p_unit_cost: unitCost,
    p_reference: reference,
    p_notes: notes,
    p_store_id: storeId,
  });
}

/**
 * Droits vus par le serveur (écran Compte). Sert à détecter une divergence
 * entre mobile/src/lib/permissions.js et la matrice SQL `app_security.can`.
 */
export function mobileContext() {
  return callRpc('app_mobile_context', {});
}

// ===========================================================================
// Trésorerie (miroir web/src/api/treasuryApi.js -> saveAccount / createMovement
// / closeMonth). Garde serveur : `manage_treasury` (ADMIN, GESTIONNAIRE,
// SUPERVISEUR) pour les comptes/mouvements/transferts, ADMIN strict pour la
// clôture mensuelle — matrice core/permissions.py appliquée en SQL.
// ===========================================================================

/**
 * Crée ou modifie un compte de trésorerie.
 * `account.id` absent -> création (solde initial = solde courant) ;
 * présent -> modification (le solde courant n'est jamais touché par cette RPC).
 */
export function saveTreasuryAccount({
  id = null,
  name,
  accountType = 'CASH',
  currency = null,
  initialBalance = 0,
  bankName = '',
  accountNumber = '',
  phoneNumber = '',
  isActive = true,
  isDefault = false,
  notes = '',
}) {
  return callRpc('app_treasury_save_account', {
    p_id: id,
    p_name: name,
    p_account_type: accountType,
    p_currency: currency,
    p_initial_balance: initialBalance,
    p_bank_name: bankName,
    p_account_number: accountNumber,
    p_phone_number: phoneNumber,
    p_is_active: isActive,
    p_is_default: isDefault,
    p_notes: notes,
  });
}

/**
 * Mouvement manuel IN/OUT : le serveur contrôle le montant (> 0), le compte
 * (actif) et ajuste `current_balance` dans la même transaction.
 */
export function createTreasuryMovement({
  accountId,
  movementType,
  amount,
  reference = '',
  description = '',
  category = '',
  date = null,
}) {
  return callRpc('app_treasury_move', {
    p_account_id: accountId,
    p_movement_type: movementType,
    p_amount: amount,
    p_reference: reference,
    p_description: description,
    p_category: category,
    p_movement_date: date,
  });
}

/** Transfert entre comptes : OUT sur l'origine + IN sur la destination. */
export function transferTreasury({ fromAccountId, toAccountId, amount, description = '' }) {
  return callRpc('app_treasury_transfer', {
    p_from_account_id: fromAccountId,
    p_to_account_id: toAccountId,
    p_amount: amount,
    p_description: description,
  });
}

/**
 * Aperçu des totaux d'une période 'YYYY-MM' (ventes, encaissé, crédit,
 * dépenses, net + statut de clôture). Lecture seule.
 */
export function treasuryMonthPreview(period) {
  return callRpc('app_treasury_month_preview', { p_period: period });
}

/**
 * Clôture mensuelle : recalcule les totaux côté serveur et les fige.
 * Droits serveur : ADMIN strict (comme le bouton web réservé aux admins).
 */
export function closeTreasuryMonth(period, notes = '') {
  return callRpc('app_treasury_close_month', {
    p_period: period,
    p_notes: notes,
  });
}

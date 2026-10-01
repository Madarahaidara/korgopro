// ============================================================================
// Catalogue : produits, fournisseurs, clients, mouvements de stock (lecture).
// Miroir de web/src/api/catalogApi.js — même noms, version async Supabase.
//
// Écritures : RLS admin-only -> refusées pour les rôles terrain. Les mutations
// passent par les RPC app_* (voir rpc.js) : addInventoryMovement les encapsule,
// les stubs save* lèvent une erreur explicite au lieu d'un 42501 brut.
// ============================================================================
import {
  getProduct as getProductRaw,
  listProductMovements as listProductMovementsRaw,
  listStockAlerts as listStockAlertsRaw,
  searchCustomers as searchCustomersRaw,
  searchProducts as searchProductsRaw,
} from './dataApi';
import { stockMovement as stockMovementRpc } from './rpc';

export const CATEGORIES = [
  'GENERAL',
  'ALIMENTATION',
  'BOISSON',
  'ELECTRONIQUE',
  'VETEMENT',
  'COSMETIQUE',
  'QUINCAILLERIE',
  'AUTRE',
];

export const CUSTOMER_TYPES = ['RETAIL', 'WHOLESALE', 'CORPORATE'];

function writeBlocked(label) {
  throw new Error(
    `${label} : écriture directe refusée par RLS (admin uniquement). ` +
      'Utilisez le desktop/web ou une RPC app_* (voir mobile/src/api/rpc.js).'
  );
}

// --- Produits (lecture) ------------------------------------------------------
export async function listProducts({ storeId = null, query = '', limit = 60 } = {}) {
  return searchProductsRaw({ storeId, query, limit });
}

export async function searchProducts(args) {
  return searchProductsRaw(args);
}

export async function getProduct(id) {
  return getProductRaw(id);
}

export async function listStockAlerts(args) {
  return listStockAlertsRaw(args);
}

/** Mouvements de stock d'un produit (nom identique au web). */
export async function listInventoryMovements(productId, limit = 8) {
  return listProductMovementsRaw(productId, limit);
}

/**
 * Écrit un mouvement de stock (IN, OUT, ADJUST, LOSS) — nom identique au web.
 *
 * Contrairement aux autres écritures du catalogue (admin-only via RLS), celle-ci
 * est ouverte aux rôles terrain : elle passe par la RPC `app_stock_movement`,
 * qui contrôle le droit côté serveur et met à jour le stock + le journal dans
 * une seule transaction.
 */
export async function addInventoryMovement(movement) {
  return stockMovementRpc(movement);
}

// --- Produits (écriture bloquée RLS) -----------------------------------------
export async function saveProduct() {
  writeBlocked('saveProduct');
}

export async function deleteProduct() {
  writeBlocked('deleteProduct');
}

export async function toggleProductActive() {
  writeBlocked('toggleProductActive');
}

// --- Clients (lecture) --------------------------------------------------------
export async function listCustomers({ query = '', limit = 60 } = {}) {
  return searchCustomersRaw({ query, limit });
}

export async function searchCustomers(args) {
  return searchCustomersRaw(args);
}

export function getCustomerName(c) {
  if (!c) return 'Client de passage';
  return [c.first_name, c.last_name].filter(Boolean).join(' ') || c.company || 'Client';
}

// --- Clients / fournisseurs (écriture bloquée RLS) -----------------------------
export async function saveCustomer() {
  writeBlocked('saveCustomer');
}

export async function deleteCustomer() {
  writeBlocked('deleteCustomer');
}

/**
 * Fournisseurs : aucune table `suppliers` n'est définie côté Supabase (voir les
 * SQL du dépôt / supabase_mobile_rpc.sql) — le web ne les stocke que dans son
 * cache local. On conserve donc le contrat du web (tableau / chaîne, synchrone)
 * sans inventer une colonne `supplier` inexistante en base.
 */
export function listSuppliers() {
  return [];
}

export function getSupplierName() {
  return '';
}

export async function saveSupplier() {
  writeBlocked('saveSupplier');
}

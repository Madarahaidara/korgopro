// ============================================================================
// Service des magasins (multi-stock).
// Chaque produit / vente / mouvement est rattaché à un magasin (store_id).
// Le magasin « actif » est mémorisé dans le localStorage.
// ============================================================================
import { db, ensureStores } from './db';

const ACTIVE_STORE_KEY = 'korgo_pro_active_store';

/** Liste tous les magasins triés par code. */
export function listStores(includeInactive = false) {
  ensureStores(db.data);
  return (db.data.stores || [])
    .filter((s) => includeInactive || s.active !== false)
    .slice()
    .sort((a, b) => a.code.localeCompare(b.code));
}

/** Retourne l'identifiant du magasin actif (par défaut : le premier). */
export function getActiveStoreId() {
  const stores = listStores(true);
  let id = Number(localStorage.getItem(ACTIVE_STORE_KEY));
  if (!stores.some((s) => s.id === id)) {
    id = stores[0] ? stores[0].id : null;
  }
  return id;
}

/** Définit le magasin actif. */
export function setActiveStoreId(id) {
  localStorage.setItem(ACTIVE_STORE_KEY, String(Number(id)));
}

/** Retourne l'objet du magasin actif. */
export function getActiveStore() {
  const id = getActiveStoreId();
  return (db.data.stores || []).find((s) => s.id === id) || null;
}

/** Crée un nouveau magasin. Retourne la liste mise à jour. */
export function createStore({ name, address = '', phone = '' }) {
  ensureStores(db.data);
  const items = db.data.stores;
  const maxCode = items.reduce((max, s) => {
    const m = String(s.code || '').match(/(\d+)$/);
    return m ? Math.max(max, parseInt(m[1], 10)) : max;
  }, 0);
  const store = {
    id: Math.max(0, ...items.map((s) => s.id)) + 1,
    code: `MAG-${String(maxCode + 1).padStart(4, '0')}`,
    name,
    address,
    phone,
    active: true,
    created_at: new Date().toISOString(),
  };
  items.push(store);
  db.persist();
  return store;
}

/** Modifie un magasin existant. */
export function updateStore(id, changes) {
  const s = (db.data.stores || []).find((x) => x.id === Number(id));
  if (s) {
    Object.assign(s, changes, { id: s.id, updated_at: new Date().toISOString() });
    db.persist();
  }
  return s;
}

/** Active / désactive un magasin (impossible pour le dernier actif). */
export function toggleStoreActive(id) {
  const stores = db.data.stores || [];
  const s = stores.find((x) => x.id === Number(id));
  if (!s) return false;
  if (s.active !== false && stores.filter((x) => x.active !== false).length <= 1) {
    throw new Error('Impossible de désactiver le dernier magasin actif.');
  }
  s.active = s.active === false;
  db.persist();
  return s;
}

/**
 * Supprime un magasin. Refusé s'il contient encore des produits ou des ventes.
 * Retourne true si la suppression a eu lieu.
 */
export function deleteStore(id) {
  const storeId = Number(id);
  const hasProducts = (db.data.products || []).some((p) => p.store_id === storeId);
  const hasSales = (db.data.sales || []).some((s) => s.store_id === storeId);
  if (hasProducts || hasSales) {
    throw new Error(
      'Ce magasin contient encore des produits ou des ventes. Désactivez-le plutôt que de le supprimer.'
    );
  }
  if ((db.data.stores || []).filter((s) => s.active !== false).length <= 1) {
    throw new Error('Impossible de supprimer le dernier magasin.');
  }
  db.data.stores = db.data.stores.filter((s) => s.id !== storeId);
  db.persist();
  return true;
}

/** Statistiques rapides d'un magasin (produits, valeur du stock, alertes). */
export function getStoreSummary(storeId) {
  const products = (db.data.products || []).filter(
    (p) => p.store_id === Number(storeId) && p.active !== false
  );
  return {
    productCount: products.length,
    stockValue: products.reduce((sum, p) => sum + (p.quantity || 0) * (p.purchase_price || 0), 0),
    lowStock: products.filter((p) => (p.quantity || 0) <= (p.min_stock || 0)).length,
  };
}
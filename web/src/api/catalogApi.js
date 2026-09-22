// ============================================================================
// Service catalogue : produits, fournisseurs, clients, mouvements de stock.
// Reprend les modèles stock_models.py et customer.py de la version desktop.
// ============================================================================
import { db } from './db';
import { getActiveStoreId } from './storesApi';

/** Retourne l'identifiant du magasin utilisé pour le filtrage (ou null = tous). */
function scopeStoreId(storeId) {
  if (storeId === 'all' || storeId === '*') return null;
  return storeId != null ? Number(storeId) : getActiveStoreId();
}

// ---------------------------------------------------------------------------
// Produits
// ---------------------------------------------------------------------------
export function listProducts(includeInactive = false, storeId = null) {
  const sid = scopeStoreId(storeId);
  return db.data.products
    .filter((p) => (includeInactive || p.active !== false) && (sid == null || p.store_id === sid))
    .map((p) => ({
      ...p,
      stockValue: (p.quantity || 0) * (p.purchase_price || 0),
      profitPerUnit: (p.sale_price || 0) - (p.purchase_price || 0),
      isLowStock: (p.quantity || 0) <= (p.min_stock || 0) && p.active !== false,
      isOutOfStock: (p.quantity || 0) <= 0 && p.active !== false,
      supplierName: getSupplierName(p.supplier_id),
    }));
}

export function getProduct(id) {
  return db.data.products.find((p) => p.id === Number(id)) || null;
}

export function saveProduct(product) {
  const items = db.data.products;
  if (product.id) {
    const idx = items.findIndex((p) => p.id === Number(product.id));
    if (idx >= 0) {
      items[idx] = { ...items[idx], ...product, updated_at: new Date().toISOString() };
    }
  } else {
    const maxCode = items.reduce((max, p) => {
      const m = String(p.code || '').match(/(\d+)$/);
      return m ? Math.max(max, parseInt(m[1], 10)) : max;
    }, 0);
    items.push({
      id: Math.max(0, ...items.map((p) => p.id)) + 1,
      store_id: product.store_id || getActiveStoreId(),
      code: `PRD-${String(maxCode + 1).padStart(4, '0')}`,
      name: product.name,
      category: product.category || 'GENERAL',
      description: product.description || '',
      quantity: Number(product.quantity) || 0,
      min_stock: Number(product.min_stock) || 5,
      max_stock: Number(product.max_stock) || 100,
      purchase_price: Number(product.purchase_price) || 0,
      sale_price: Number(product.sale_price) || 0,
      supplier_id: product.supplier_id || null,
      location: product.location || '',
      barcode: product.barcode || '',
      active: product.active !== false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
  }
  db.persist();
  return listProducts();
}

export function deleteProduct(id) {
  db.data.products = db.data.products.filter((p) => p.id !== Number(id));
  db.persist();
  return listProducts();
}

export function toggleProductActive(id) {
  const p = db.data.products.find((x) => x.id === Number(id));
  if (p) {
    p.active = !p.active;
    db.persist();
  }
  return listProducts();
}

// ---------------------------------------------------------------------------
// Mouvements de stock
// ---------------------------------------------------------------------------
export function listInventoryMovements(storeId = null) {
  const sid = scopeStoreId(storeId);
  return (db.data.inventoryMovements || []).filter(
    (m) => sid == null || m.store_id === sid
  );
}

export function addInventoryMovement(movement) {
  db.data.inventoryMovements = db.data.inventoryMovements || [];
  db.data.inventoryMovements.unshift({
    id: Math.max(0, ...(db.data.inventoryMovements || []).map((m) => m.id)) + 1,
    date: new Date().toISOString(),
    store_id: movement.store_id || getActiveStoreId(),
    ...movement,
  });
  db.persist();
}
// ---------------------------------------------------------------------------
// Fournisseurs
// ---------------------------------------------------------------------------
export function listSuppliers() {
  return (db.data.suppliers || []).filter((s) => s.active !== false);
}

export function getSupplierName(id) {
  const s = (db.data.suppliers || []).find((x) => x.id === Number(id));
  return s ? s.name : '';
}

export function saveSupplier(supplier) {
  const items = db.data.suppliers || [];
  if (supplier.id) {
    const idx = items.findIndex((s) => s.id === Number(supplier.id));
    if (idx >= 0) items[idx] = { ...items[idx], ...supplier };
  } else {
    items.push({
      id: Math.max(0, ...items.map((s) => s.id)) + 1,
      code: `FRN-${String(items.length + 1).padStart(4, '0')}`,
      name: supplier.name,
      contact_person: supplier.contact_person || '',
      email: supplier.email || '',
      phone: supplier.phone || '',
      address: supplier.address || '',
      city: supplier.city || '',
      country: supplier.country || '',
      active: true,
      created_at: new Date().toISOString(),
    });
  }
  db.persist();
  return items;
}

// ---------------------------------------------------------------------------
// Clients
// ---------------------------------------------------------------------------
export function listCustomers(includeInactive = false) {
  return db.data.customers
    .filter((c) => includeInactive || c.active !== false)
    .map((c) => ({ ...c, full_name: `${c.first_name} ${c.last_name}` }));
}

export function getCustomer(id) {
  const c = db.data.customers.find((x) => x.id === Number(id));
  return c ? { ...c, full_name: `${c.first_name} ${c.last_name}` } : null;
}

export function saveCustomer(customer) {
  const items = db.data.customers;
  if (customer.id) {
    const idx = items.findIndex((c) => c.id === Number(customer.id));
    if (idx >= 0) {
      items[idx] = { ...items[idx], ...customer, updated_at: new Date().toISOString() };
    }
  } else {
    items.push({
      id: Math.max(0, ...items.map((c) => c.id)) + 1,
      code: `CLI-${String(items.length + 1).padStart(4, '0')}`,
      first_name: customer.first_name,
      last_name: customer.last_name,
      company: customer.company || '',
      email: customer.email || '',
      phone: customer.phone || '',
      mobile: customer.mobile || '',
      address: customer.address || '',
      city: customer.city || '',
      country: customer.country || '',
      customer_type: customer.customer_type || 'RETAIL',
      credit_limit: Number(customer.credit_limit) || 0,
      balance: Number(customer.balance) || 0,
      loyalty_points: Number(customer.loyalty_points) || 0,
      active: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
  }
  db.persist();
  return listCustomers();
}

export function deleteCustomer(id) {
  db.data.customers = db.data.customers.filter((c) => c.id !== Number(id));
  db.persist();
  return listCustomers();
}

// ---------------------------------------------------------------------------
// Catégories utiles pour les formulaires
// ---------------------------------------------------------------------------
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
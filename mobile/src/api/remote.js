// ============================================================================
// remote.js (mobile) — miroir de web/src/api/remote.js.
//
// Le web hydrate TOUT en mémoire (db.js) ; le mobile lit À LA DEMANDE.
// Ce module expose la même table de correspondance collection <-> table SQL
// (source de documentation + helpers de renommage), sans cache mémoire.
// ============================================================================

export const COLLECTIONS = [
  { name: 'users', table: 'users', rename: { password: 'password_hash' }, order: 'id', readOnly: true },
  { name: 'customers', table: 'customers', order: 'id' },
  { name: 'suppliers', table: 'suppliers', order: 'id' },
  { name: 'products', table: 'products', order: 'id' },
  { name: 'stores', table: 'stores', order: 'id' },
  {
    name: 'sales', table: 'sales', rename: { number: 'sale_number' }, order: 'id',
    items: { key: 'items', table: 'sale_items', foreignKey: 'sale_id', order: 'id' },
  },
  {
    name: 'proformas', table: 'proforma_invoices', rename: { number: 'proforma_number' }, order: 'id',
    items: { key: 'items', table: 'proforma_invoice_items', foreignKey: 'proforma_id', order: 'id' },
  },
  { name: 'inventoryMovements', table: 'inventory_movements', order: 'id' },
  { name: 'treasuryAccounts', table: 'treasury_accounts', order: 'id' },
  { name: 'treasuryMovements', table: 'treasury_movements', order: 'id' },
  { name: 'monthlyClosures', table: 'monthly_closures', order: 'id' },
  { name: 'expenses', table: 'expenses', order: 'id' },
  {
    name: 'activityLogs', table: 'activity_logs',
    rename: { user: 'username', timestamp: 'created_at' }, order: 'id',
  },
];

export function getCollection(name) {
  return COLLECTIONS.find((c) => c.name === name) || null;
}

const VIRTUAL_FIELDS = new Set([
  'items', 'customer', 'cashier', 'creator', 'product',
  'full_name', 'stockValue', 'profitPerUnit', 'isLowStock',
  'isOutOfStock', 'supplierName', 'accountName', 'balance',
]);

/** web -> SQL : renomme les clés et retire les champs virtuels. */
export function toSqlRow(collection, row) {
  const rename = collection.rename || {};
  const out = {};
  Object.entries(row || {}).forEach(([key, value]) => {
    if (VIRTUAL_FIELDS.has(key)) return;
    if (value === undefined) return;
    out[rename[key] || key] = value;
  });
  return out;
}

/** SQL -> web : applique le renommage inverse. */
export function toWebRow(collection, row) {
  const rename = collection.rename || {};
  const inverse = {};
  Object.entries(rename).forEach(([webKey, col]) => { inverse[col] = webKey; });
  const out = {};
  Object.entries(row || {}).forEach(([col, value]) => { out[inverse[col] || col] = value; });
  return out;
}

export function sortById(rows) {
  return rows.slice().sort((a, b) => (a.id || 0) - (b.id || 0));
}

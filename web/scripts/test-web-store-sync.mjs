/**
 * Test de coherence magasin / synchronisation web <-> Supabase.
 *
 * Reproduit le defaut constate en production : l'interface affiche
 * « Magasin principal » alors que la liste des produits est vide.
 *
 * Cause : StoreProvider est initialise AVANT l'hydratation Supabase, donc sur
 * le magasin de secours fabrique localement (`ensureStores`, id 1). Le
 * magasin reellement utilise pour filtrer les listes est, lui, lu a chaque
 * appel dans `korgo_pro_active_store` (localStorage). Les deux divergent :
 *   - l'interface affiche le magasin fantome id 1 « Magasin principal » ;
 *   - les services filtrent sur le magasin reellement memorise (ex. id 5).
 * D'ou une liste vide et un selecteur qui ne propose que le fantome (donc
 * aucune possibilite de revenir sur le magasin principal).
 *
 * Le faux serveur PostgREST reproduit le schema reel : toute colonne inconnue
 * est refusee (erreur 42703 « column ... does not exist »), comme le ferait la
 * base Supabase (cf. proforma_invoices qui n'a PAS de colonne store_id).
 *
 * Fixture relevee sur la base de production le 28/09/2026 :
 *   stores   : id 3 (MAG-0001, is_default), id 4 (MAG-0002), id 5 (MAG-0003)
 *   products : rattaches au magasin 3
 *
 * Usage : node scripts/test-web-store-sync.mjs
 */
import { createServer } from 'vite';

// ---------------------------------------------------------------------------
// 1. localStorage : magasin actif memorise = 5 (cas bloquant constate)
// ---------------------------------------------------------------------------
const localStore = new Map([['korgo_pro_active_store', '5']]);
globalThis.localStorage = {
  getItem: (k) => (localStore.has(k) ? localStore.get(k) : null),
  setItem: (k, v) => localStore.set(k, String(v)),
  removeItem: (k) => localStore.delete(k),
  key: (i) => Array.from(localStore.keys())[i] ?? null,
  clear: () => localStore.clear(),
  get length() { return localStore.size; },
};

// ---------------------------------------------------------------------------
// 2. Fausse base PostgREST (etat reel de production)
// ---------------------------------------------------------------------------
const DB = {
  stores: [
    { id: 3, code: 'MAG-0001', name: 'Magasin principal', active: true, is_default: true },
    { id: 4, code: 'MAG-0002', name: 'Magasin lome', active: true, is_default: false },
    { id: 5, code: 'MAG-0003', name: 'mag2', active: true, is_default: null },
  ],
  products: [
    { id: 1, code: 'PRD-0001', name: 'Riz parfume 25kg', category: 'ALIMENTATION', quantity: 120, min_stock: 20, max_stock: 300, purchase_price: 14000, sale_price: 16500, active: true, store_id: 3 },
    { id: 2, code: 'PRD-0002', name: 'Huile vegetale 5L', category: 'ALIMENTATION', quantity: 45, min_stock: 15, max_stock: 150, purchase_price: 5000, sale_price: 6200, active: true, store_id: 3 },
    { id: 3, code: 'PRD-0003', name: 'Eau minerale 1,5L', category: 'BOISSON', quantity: 300, min_stock: 50, max_stock: 600, purchase_price: 1800, sale_price: 2200, active: true, store_id: 3 },
  ],
  sales: [
    { id: 1, sale_number: 'FAC-0001', customer_id: null, cashier_id: 1, sale_date: '2026-09-01T10:00:00', subtotal: 16500, discount_amount: 0, tax_amount: 0, total_amount: 16500, amount_paid: 16500, payment_method: 'CASH', payment_status: 'PAID', sale_status: 'COMPLETED', statut: 'EMISE', currency: 'FCFA', store_id: 3 },
  ],
  sale_items: [
    { id: 1, sale_id: 1, product_id: 1, quantity: 1, unit_price: 16500, discount_percent: 0, discount_amount: 0, line_total: 16500 },
  ],
  proforma_invoices: [],
  proforma_invoice_items: [],
  inventory_movements: [],
  treasury_accounts: [],
  treasury_movements: [],
  monthly_closures: [],
  expenses: [],
  activity_logs: [],
  customers: [],
  suppliers: [],
  users: [{ id: 1, username: 'admin', email: 'admin@korgo-pro.com', role: 'ADMIN', active: true }],
};

/**
 * Colonnes reelles des tables ecrites par le web (releve du schema Supabase).
 * `proforma_invoices` n'a PAS de colonne store_id : un envoi de cette colonne
 * doit etre refuse, comme par PostgREST / PostgreSQL (42703).
 */
const COLUMNS = {
  stores: ['id', 'code', 'name', 'address', 'phone', 'manager_name', 'notes', 'active', 'is_default', 'created_at', 'updated_at'],
  products: ['id', 'code', 'name', 'category', 'description', 'quantity', 'min_stock', 'max_stock', 'purchase_price', 'sale_price', 'supplier_id', 'location', 'barcode', 'active', 'created_at', 'updated_at', 'store_id'],
  sales: ['id', 'sale_number', 'customer_id', 'cashier_id', 'sale_date', 'subtotal', 'discount_amount', 'tax_amount', 'total_amount', 'amount_paid', 'change_amount', 'payment_method', 'payment_status', 'sale_status', 'notes', 'created_at', 'currency', 'type_document', 'origine_proforma_id', 'date_conversion', 'utilisateur_conversion', 'statut', 'date_expiration', 'version', 'store_id'],
  sale_items: ['id', 'sale_id', 'product_id', 'quantity', 'unit_price', 'discount_percent', 'discount_amount', 'line_total', 'notes'],
  proforma_invoices: ['id', 'proforma_number', 'customer_id', 'created_by', 'created_date', 'valid_until', 'subtotal', 'discount_amount', 'discount_percent', 'tax_amount', 'tax_percent', 'total_amount', 'status', 'notes', 'terms_and_conditions', 'currency', 'converted_to_sale_id'],
  proforma_invoice_items: ['id', 'proforma_id', 'product_id', 'description', 'quantity', 'unit_price', 'discount_percent', 'discount_amount', 'line_total', 'notes'],
  inventory_movements: ['id', 'product_id', 'movement_type', 'quantity', 'unit_price', 'total_value', 'reference', 'reason', 'notes', 'user_id', 'date', 'created_at', 'store_id'],
  treasury_accounts: ['id', 'name', 'account_type', 'currency', 'initial_balance', 'current_balance', 'bank_name', 'account_number', 'phone_number', 'is_active', 'is_default', 'notes', 'created_at', 'updated_at'],
  treasury_movements: ['id', 'account_id', 'movement_type', 'amount', 'date', 'reference', 'description', 'category', 'reference_type', 'reference_id', 'user_id', 'created_at'],
  monthly_closures: ['id', 'period', 'sales_count', 'total_sales', 'total_collected', 'total_credit', 'total_out', 'net', 'balances', 'status', 'closed_by', 'closed_at', 'notes', 'created_at'],
  expenses: ['id', 'category_id', 'amount', 'description', 'payment_method', 'reference', 'supplier_id', 'user_id', 'date', 'created_at'],
  customers: ['id', 'code', 'first_name', 'last_name', 'company', 'email', 'phone', 'mobile', 'address', 'city', 'country', 'customer_type', 'credit_limit', 'balance', 'loyalty_points', 'notes', 'active', 'created_at', 'updated_at'],
  suppliers: ['id', 'code', 'name', 'contact_person', 'email', 'phone', 'address', 'city', 'country', 'website', 'notes', 'payment_terms', 'active', 'created_at', 'updated_at'],
  users: ['id', 'username', 'password_hash', 'email', 'role', 'active', 'created_at', 'last_login', 'last_ip', 'must_change_password'],
};

const calls = [];
const writeErrors = [];

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function headersToObject(headers) {
  if (!headers) return {};
  if (typeof headers.forEach === 'function' && !Array.isArray(headers)) {
    const out = {};
    headers.forEach((v, k) => { out[String(k).toLowerCase()] = v; });
    return out;
  }
  return Object.fromEntries(Object.entries(headers).map(([k, v]) => [k.toLowerCase(), v]));
}

/** Applique les filtres `colonne=eq.valeur` d'une URL PostgREST. */
function applyFilters(rows, url) {
  let out = rows;
  for (const [key, raw] of url.searchParams.entries()) {
    if (!raw.startsWith('eq.')) continue;
    const value = raw.slice(3);
    out = out.filter((r) => String(r[key]) === value);
  }
  return out;
}

/** Refuse une colonne inconnue, comme PostgreSQL (42703). */
function unknownColumn(table, row) {
  const known = COLUMNS[table] || [];
  return Object.keys(row || {}).find((k) => !known.includes(k)) || null;
}

globalThis.fetch = async (input, init = {}) => {
  const url = new URL(typeof input === 'string' ? input : input.url);
  const method = String(init.method || 'GET').toUpperCase();
  const body = init.body ? JSON.parse(init.body) : null;
  calls.push({ method, path: url.pathname, search: url.search, body });

  if (url.pathname.startsWith('/auth/v1/')) return json({});

  const table = url.pathname.replace('/rest/v1/', '');
  if (method === 'GET') {
    return json(applyFilters(DB[table] || [], url));
  }
  if (method === 'DELETE') return new Response(null, { status: 204 });

  // POST / upsert : controle des colonnes comme le ferait la base.
  const rows = Array.isArray(body) ? body : [body];
  for (const row of rows) {
    const bad = unknownColumn(table, row);
    if (bad) {
      writeErrors.push({ table, column: bad });
      return json({ code: '42703', message: `column ${table}.${bad} does not exist` }, 400);
    }
  }
  return new Response(null, { status: 201 });
};

// ---------------------------------------------------------------------------
// 3. Utilitaires de test
// ---------------------------------------------------------------------------
let failures = 0;
function check(label, condition, detail = '') {
  const ok = Boolean(condition);
  if (!ok) failures += 1;
  console.log(`${ok ? 'OK   ' : 'ECHEC'} ${label}${detail ? `  (${detail})` : ''}`);
}

const server = await createServer({
  server: { middlewareMode: true },
  appType: 'custom',
  logLevel: 'error',
});

try {
  const { db, hydrate, syncState } = await server.ssrLoadModule('/src/api/db.js');
  const storesApi = await server.ssrLoadModule('/src/api/storesApi.js');
  const { listProducts } = await server.ssrLoadModule('/src/api/catalogApi.js');

  console.log('\n== 1. Avant hydratation (etat initial du navigateur) ==');
  check('mode Supabase actif', syncState.mode === 'supabase');
  const bootStores = storesApi.listStores(true);
  check('liste de secours locale utilisee avant hydratation',
    bootStores.length === 1 && bootStores[0].name === 'Magasin principal',
    bootStores.map((s) => `${s.id}:${s.name}`).join(','));
  // Reproduction du symptome : l'interface affiche « Magasin principal »
  // (magasin de secours, id 1) alors que ce magasin n'existe pas dans la base
  // Supabase -> aucun produit, puisque tous les produits sont rattaches au
  // magasin 3.
  const bootId = storesApi.getActiveStoreId();
  check("magasin de secours (id 1) affiche comme « Magasin principal »",
    bootStores.find((s) => s.id === bootId)?.name === 'Magasin principal', String(bootId));
  check("ce magasin de secours ne filtre AUCUN produit (liste vide constatee)",
    listProducts(true).length === 0, `${listProducts(true).length} produit(s)`);

  console.log('\n== 2. Hydratation ==');
  const result = await hydrate();
  check('hydratation reussie', result.ok, result.message);

  console.log('\n== 3. Liste des magasins apres hydratation ==');
  const stores = storesApi.listStores(true);
  const ids = stores.map((s) => s.id);
  check('les 3 magasins reels sont presents', ids.join(',') === '3,4,5', ids.join(','));
  check('aucun magasin fantome (id 1 fabrique localement) dans la liste UI',
    !ids.includes(1), ids.join(','));
  check('magasin par defaut = MAG-0001 (id 3)',
    storesApi.defaultStore(stores)?.id === 3, String(storesApi.defaultStore(stores)?.id));

  console.log('\n== 4. Magasin actif : interface et filtrage doivent coincider ==');
  const activeId = storesApi.getActiveStoreId();
  const activeStore = stores.find((s) => s.id === activeId) || null;
  check('le magasin actif memorise (5) existe cote Supabase', activeId === 5, String(activeId));
  check("l'interface affiche le magasin reellement utilise (mag2), pas un magasin fantome",
    activeStore?.name === 'mag2', String(activeStore?.name));
  check('aucun produit pour ce magasin (magasin reellement vide)',
    listProducts(true).length === 0, String(listProducts(true).length));

  console.log('\n== 5. Retour sur le magasin principal ==');
  storesApi.setActiveStoreId(3);
  const mainId = storesApi.getActiveStoreId();
  const mainStore = stores.find((s) => s.id === mainId);
  check('magasin principal selectionnable (id 3)', mainId === 3, String(mainId));
  check('nom affiche = Magasin principal', mainStore?.name === 'Magasin principal',
    String(mainStore?.name));
  const mainProducts = listProducts(true);
  check('liste des produits du magasin principal disponible',
    mainProducts.length === DB.products.length, `${mainProducts.length} produit(s)`);

  console.log('\n== 6. Proformas : aucune colonne inexistante en base (store_id) ==');
  db.data.proformas.push({
    id: 1, number: 'PRO-0001', customer_id: null, created_by: 1,
    created_date: '2026-09-10T09:00:00', valid_until: null, subtotal: 1000,
    discount_percent: 0, discount_amount: 0, tax_percent: 0, tax_amount: 0,
    total_amount: 1000, status: 'BROUILLON', currency: 'FCFA',
    items: [{ id: 1, product_id: 1, description: 'Riz', quantity: 1, unit_price: 1000, line_total: 1000 }],
  });
  db.persist();
  await db.flush();
  const proformaRows = calls
    .filter((c) => c.method === 'POST' && c.path === '/rest/v1/proforma_invoices')
    .flatMap((c) => c.body || []);
  check('proforma envoyee a Supabase', proformaRows.length === 1, String(proformaRows.length));
  check("aucune colonne 'store_id' sur proforma_invoices (colonne absente en base)",
    proformaRows.every((r) => !('store_id' in r)), JSON.stringify(proformaRows[0] || {}));
  check('aucun refus de colonne inconnue', writeErrors.length === 0,
    writeErrors.map((w) => `${w.table}.${w.column}`).join(','));

  console.log("\n== 7. Lignes enfants (sale_items) : ids uniques, jamais d'ecrasement ==");
  const remoteChildIds = new Set(DB.sale_items.map((r) => r.id));
  db.data.sales.push({
    id: 2, number: 'FAC-0002', customer_id: null, cashier_id: 1,
    sale_date: '2026-09-11T09:00:00', subtotal: 1000, discount_amount: 0,
    tax_amount: 0, total_amount: 1000, amount_paid: 1000, change_amount: 0,
    payment_method: 'CASH', payment_status: 'PAID', sale_status: 'COMPLETED',
    statut: 'EMISE', currency: 'FCFA', store_id: 3,
    items: [{ id: 1, product_id: 1, quantity: 1, unit_price: 1000, line_total: 1000 }],
  });
  db.persist();
  await db.flush();
  const itemRows = calls
    .filter((c) => c.method === 'POST' && c.path === '/rest/v1/sale_items')
    .flatMap((c) => c.body || []);
  const newItems = itemRows.filter((r) => r.sale_id === 2);
  check('ligne enfant de la nouvelle vente envoyee', newItems.length === 1, String(newItems.length));
  check("l'id enfant local n'ecrase pas une ligne existante (id distant reutilise)",
    newItems.every((r) => !remoteChildIds.has(r.id)),
    `id envoye=${newItems[0]?.id} / ids existants=${Array.from(remoteChildIds).join(',')}`);
  check('id enfant non nul et idempotent', newItems.every((r) => r.id != null));
  check('aucune erreur de synchronisation',
    syncState.lastError === null, String(syncState.lastError));

  console.log("\n== 7 bis. Ligne ajoutee puis retiree (nettoyage sans rechargement) ==");
  const deletesBefore = calls.filter(
    (c) => c.method === 'DELETE' && c.path === '/rest/v1/sale_items'
  ).length;
  db.data.sales.find((s) => s.id === 2).items = [];
  db.persist();
  await db.flush();
  const removed = calls
    .filter((c) => c.method === 'DELETE' && c.path === '/rest/v1/sale_items')
    .slice(deletesBefore);
  check('ligne locale retiree supprimee cote Supabase', removed.length === 1,
    String(removed.length));
  check("seule la ligne locale (id negatif) est supprimee",
    /id=in\.\(-2001\)|id=in\.%28-2001%29/.test(removed[0]?.search || ''),
    removed[0]?.search || '');
  check('aucune ligne distante (id positif) supprimee',
    !/id=in\.\(1\)|%281%29/.test(removed[0]?.search || ''), removed[0]?.search || '');

  console.log('\n== 8. Non-regression : le contexte magasin relit la base hydratee ==');
  // Sans cette relecture, l'interface reste figee sur le magasin de secours
  // (id 1) : c'est la cause exacte de la liste de produits vide constatee.
  const { readFileSync } = await import('node:fs');
  const { fileURLToPath } = await import('node:url');
  const { dirname, join } = await import('node:path');
  const here = dirname(fileURLToPath(import.meta.url));
  const contextSrc = readFileSync(join(here, '..', 'src', 'context', 'StoreContext.jsx'), 'utf8');
  check('StoreContext observe les evenements de synchronisation',
    /onSyncStatus|useSyncExternalStore/.test(contextSrc));
  check("StoreContext relit le magasin actif via getActiveStoreId()",
    /getActiveStoreId\(\)/.test(contextSrc));
  check("StoreContext n'utilise plus d'etat fige (plus de useState(() => listStores))",
    !/useState\(\(\) => listStores/.test(contextSrc));
} finally {
  await server.close();
}

console.log(`\n${failures === 0 ? 'TOUS LES TESTS SONT PASSES' : `${failures} TEST(S) EN ECHEC`}`);
process.exitCode = failures === 0 ? 0 : 1;


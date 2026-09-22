/**
 * Test d'intégration de la liaison web <-> Supabase (sans réseau réel).
 *
 * Les modules de l'application (`web/src/api/*`) sont chargés par Vite (donc
 * avec `import.meta.env` correctement injecté), puis tous les appels HTTP sont
 * interceptés et simulés : Supabase Auth + API PostgREST.
 *
 * Vérifie :
 *   1. la connexion (signInWithPassword + chargement du profil public.users) ;
 *   2. l'hydratation (mapping SQL -> web, lignes enfants imbriquées) ;
 *   3. l'écriture (renommage web -> SQL, seules collections modifiées) ;
 *   4. la sécurité des suppressions (index des identifiants distants connus) ;
 *   5. `db.clearRemote()` à la déconnexion (purge locale, aucune écriture).
 *
 * Usage : node scripts/test-web-supabase-link.mjs
 */
import { createServer } from 'vite';

// Node n'a pas de localStorage : stub en mémoire (db.js s'en sert comme cache).
const localStore = new Map();
globalThis.localStorage = {
  getItem: (k) => (localStore.has(k) ? localStore.get(k) : null),
  setItem: (k, v) => localStore.set(k, String(v)),
  removeItem: (k) => localStore.delete(k),
  key: (i) => Array.from(localStore.keys())[i] ?? null,
  clear: () => localStore.clear(),
  get length() { return localStore.size; },
};


// ---------------------------------------------------------------------------
// 1. Fausse base PostgREST + fausse authentification Supabase
// ---------------------------------------------------------------------------
const DB = {
  users: [{
    id: 1, username: 'admin', email: 'admin@korgo-pro.com', role: 'ADMIN',
    active: true, must_change_password: false, last_login: null, password_hash: 'hash',
  }],
  customers: [{ id: 1, name: 'Client A' }, { id: 2, name: 'Client B' }],
  suppliers: [{ id: 3, name: 'Fournisseur X' }],
  products: [{
    id: 1, name: 'Produit', sale_price: 1000, purchase_price: 800,
    quantity: 5, store_id: 1,
  }],
  stores: [{ id: 1, code: 'MAG-0001', name: 'Magasin principal', active: true }],
  sales: [{
    id: 1, sale_number: 'FAC-0001', customer_id: 1, store_id: 1, total: 1000,
    created_at: '2026-01-01T00:00:00',
  }],
  sale_items: [{
    id: 1, sale_id: 1, product_id: 1, quantity: 2, unit_price: 500, subtotal: 1000,
  }],
  proforma_invoices: [],
  proforma_invoice_items: [],
  inventory_movements: [],
  treasury_accounts: [],
  treasury_movements: [],
  expenses: [],
  activity_logs: [],
};

const calls = [];

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

globalThis.fetch = async (input, init = {}) => {
  const url = new URL(typeof input === 'string' ? input : input.url);
  const method = String(init.method || 'GET').toUpperCase();
  const headers = headersToObject(init.headers);
  calls.push({
    method,
    path: url.pathname,
    search: url.search,
    body: init.body ? JSON.parse(init.body) : null,
  });

  // --- Supabase Auth ---
  if (url.pathname.startsWith('/auth/v1/')) {
    if (url.pathname.includes('/token')) {
      return json({
        access_token: 'fake.jwt', token_type: 'bearer', expires_in: 3600,
        expires_at: Math.floor(Date.now() / 1000) + 3600, refresh_token: 'refresh',
        user: { id: 'uuid-1', email: 'admin@korgo-pro.com' },
      });
    }
    return json({});
  }

  // --- PostgREST ---
  const table = url.pathname.replace('/rest/v1/', '');
  const rows = applyFilters(DB[table] || [], url);
  if (method === 'GET') {
    if ((headers.accept || '').includes('vnd.pgrst.object+json')) {
      return rows.length ? json(rows[0]) : new Response(null, { status: 200 });
    }
    return json(rows);
  }
  if (method === 'DELETE') return new Response(null, { status: 204 });
  return new Response(null, { status: 201 });
};


// ---------------------------------------------------------------------------
// 2. Utilitaires de test
// ---------------------------------------------------------------------------
let failures = 0;
function check(label, condition, detail = '') {
  const ok = Boolean(condition);
  if (!ok) failures += 1;
  console.log(`${ok ? 'OK   ' : 'ECHEC'} ${label}${detail ? `  (${detail})` : ''}`);
}
function callsFor(method, table) {
  return calls.filter((c) => c.method === method && c.path === `/rest/v1/${table}`);
}

// ---------------------------------------------------------------------------
// 3. Exécution
// ---------------------------------------------------------------------------
const server = await createServer({
  server: { middlewareMode: true },
  appType: 'custom',
  logLevel: 'error',
});

try {
  const { supabase, isSupabaseConfigured } = await server.ssrLoadModule('/src/api/supabase.js');
  const { authenticateRemote } = await server.ssrLoadModule('/src/api/remoteAuth.js');
  const remote = await server.ssrLoadModule('/src/api/remote.js');
  const { db, hydrate, clearRemote, syncState } = await server.ssrLoadModule('/src/api/db.js');

  console.log('\n== 1. Configuration ==');
  check('mode supabase actif (web/.env lu)', isSupabaseConfigured() && syncState.mode === 'supabase');

  console.log('\n== 2. Connexion (Supabase Auth + profil public.users) ==');
  const profile = await authenticateRemote(supabase, 'admin@korgo-pro.com', 'motdepasse');
  check('profil charge depuis public.users', profile?.username === 'admin', profile?.role);
  check('filtre active=eq.true envoye a PostgREST',
    callsFor('GET', 'users').some((c) => c.search.includes('active=eq.true')));

  console.log('\n== 3. Hydratation (SQL -> web) ==');
  const result = await hydrate();
  check('hydratation reussie', result.ok, result.message);
  check('renommage sale_number -> number', db.data.sales[0]?.number === 'FAC-0001');
  check('lignes enfants imbriquees (sale_items -> items)',
    db.data.sales[0]?.items?.length === 1);
  check('renommage password_hash -> password', db.data.users[0]?.password === 'hash');
  check('toutes les collections presentes',
    remote.COLLECTIONS.every((c) => Array.isArray(db.data[c.name])));

  console.log('\n== 4. Ecriture (web -> SQL) ==');
  const beforeWrites = calls.length;
  db.data.products[0].sale_price = 2000;
  db.persist();
  await db.flush();
  const upserts = calls.slice(beforeWrites).filter((c) => c.method === 'POST');
  check('une seule collection modifiee envoyee', upserts.length === 1,
    upserts.map((u) => u.path).join(','));
  check('upsert products avec on_conflict=id',
    upserts[0]?.path === '/rest/v1/products' && upserts[0]?.search.includes('on_conflict=id'));
  check('colonne envoyee en snake_case', upserts[0]?.body?.[0]?.sale_price === 2000);

  console.log('\n== 5. Securite des suppressions ==');
  const { pushCollection, getCollection } = remote;

  remote.rememberRemoteIds('customers', [1, 2, 3]);
  await pushCollection(getCollection('customers'), [{ id: 1 }]);
  const delCustomers = callsFor('DELETE', 'customers').pop();
  check('ligne distante disparue supprimee', Boolean(delCustomers), delCustomers?.search);
  check('seuls les ids connus et absents sont supprimes',
    /id=in\.\(2,3\)|id=in\.%282%2C3%29/.test(delCustomers?.search || ''), delCustomers?.search);

  const beforeSuppliers = callsFor('DELETE', 'suppliers').length;
  remote.forgetRemoteIds('suppliers');
  await pushCollection(getCollection('suppliers'), []);
  check('collection jamais hydratee : aucune suppression',
    callsFor('DELETE', 'suppliers').length === beforeSuppliers);

  const beforePurge = callsFor('DELETE', 'customers').length;
  remote.forgetRemoteIds();
  await pushCollection(getCollection('customers'), []);
  check('apres purge (deconnexion) : aucune suppression',
    callsFor('DELETE', 'customers').length === beforePurge);

  console.log('\n== 6. Deconnexion (clearRemote) ==');
  const beforeLogout = calls.length;
  clearRemote();
  check('aucune ecriture emise vers Supabase', calls.length === beforeLogout);
  check('cache local purge (valeurs par defaut)', db.data.users.length === 3);
  check('etat de synchronisation reinitialise',
    syncState.hydrated === false && syncState.lastError === null && syncState.pending === 0);

  db.persist();
  await db.flush();
  check('aucune ecriture apres purge', calls.length === beforeLogout);
} finally {
  await server.close();
}

console.log(`\n${failures === 0 ? 'TOUS LES TESTS SONT PASSES' : `${failures} TEST(S) EN ECHEC`}`);
process.exitCode = failures === 0 ? 0 : 1;

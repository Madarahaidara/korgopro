/**
 * Test de bout en bout : vente a credit cote web.
 *
 * Valide la regle de gestion implementee dans `src/api/salesApi.js` (meme
 * regle que la RPC Supabase `app_create_sale` et le desktop) :
 *
 *   1. CREDIT sans acompte -> PENDING, reste du = total, dette du client
 *      creditree, AUCUNE entree de tresorerie ;
 *   2. CREDIT avec acompte -> PARTIAL, seule la part non encaissee est duee ;
 *   3. encaissement        -> diminue le reste du et la dette du client,
 *      credite la tresorerie ; refuse si montant > reste du ;
 *   4. facture soldee      -> PAID, dette du client remise a zero ;
 *   5. ESPERES avec monnaie-> tresorerie = total (pas la monnaie rendue) ;
 *   6. synchronisation     -> `customers.balance` est envoye a Supabase
 *      (regression : cette cle etait filtree comme champ virtuel).
 *
 * Meme harness que `test-web-store-sync.mjs` : Vite (transformation ESM) +
 * faux serveur PostgREST. Aucune donnee reelle n'est ecrite.
 *
 * Usage : node scripts/test-web-credit-sale.mjs
 */
import { createServer } from 'vite';

// ---------------------------------------------------------------------------
// 1. localStorage : magasin actif = 3 (magasin par defaut du fixture)
// ---------------------------------------------------------------------------
const store = new Map([['korgo_pro_active_store', '3']]);
globalThis.localStorage = {
  getItem: (k) => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: (k) => store.delete(k),
  key: (i) => Array.from(store.keys())[i] ?? null,
  clear: () => store.clear(),
  get length() { return store.size; },
};

// ---------------------------------------------------------------------------
// 2. Fausse base PostgREST (schema reel Supabase)
// ---------------------------------------------------------------------------
const DB = {
  stores: [
    { id: 3, code: 'MAG-0001', name: 'Magasin principal', active: true, is_default: true },
  ],
  users: [{ id: 1, username: 'admin', email: 'admin@korgo-pro.com', role: 'ADMIN', active: true }],
  customers: [
    { id: 7, code: 'CLI-0007', first_name: 'Moussa', last_name: 'Diallo', customer_type: 'RETAIL', credit_limit: 150000, balance: 0, loyalty_points: 0, active: true },
  ],
  suppliers: [],
  products: [
    { id: 11, code: 'PRD-0011', name: 'Ciment CPA', category: 'MATERIEL', quantity: 50, min_stock: 5, max_stock: 200, purchase_price: 4000, sale_price: 5000, active: true, store_id: 3 },
  ],
  sales: [],
  sale_items: [],
  proformas: [],
  proforma_invoice_items: [],
  inventory_movements: [],
  treasury_accounts: [
    { id: 4, name: 'Caisse principale', account_type: 'CASH', currency: 'FCFA', initial_balance: 0, current_balance: 0, is_active: true, is_default: true },
  ],
  treasury_movements: [],
  monthly_closures: [],
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

globalThis.fetch = async (input, init = {}) => {
  const url = new URL(typeof input === 'string' ? input : input.url);
  const method = String(init.method || 'GET').toUpperCase();
  const body = init.body ? JSON.parse(init.body) : null;
  calls.push({ method, path: url.pathname, search: url.search, body });

  if (url.pathname.startsWith('/auth/v1/')) return json({});
  const table = url.pathname.replace('/rest/v1/', '');
  if (method === 'GET') return json(DB[table] || []);
  if (method === 'DELETE') return new Response(null, { status: 204 });
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
const money = (v) => Number(v || 0);

const server = await createServer({
  server: { middlewareMode: true },
  appType: 'custom',
  logLevel: 'error',
});

try {
  const { db, hydrate, syncState } = await server.ssrLoadModule('/src/api/db.js');
  const { createSale, receivePayment, listCreditSales, saleDue, isCreditPayment } =
    await server.ssrLoadModule('/src/api/salesApi.js');

  console.log('\n== 0. Hydratation ==');
  const hydrated = await hydrate();
  check('hydratation reussie', hydrated.ok, hydrated.message);

  const customer = db.data.customers.find((c) => c.id === 7);
  const item = [{ product_id: 11, quantity: 1, unit_price: 5000, line_total: 5000 }];
  const balanceOf = () => money(customer.balance);
  const movementsOf = (saleId) => db.data.treasuryMovements.filter(
    (m) => m.reference_type === 'SALE' && m.reference_id === saleId);

  console.log('\n== 1. Vocabulaire de paiement ==');
  check('CREDIT (avec accent) est un moyen differe', isCreditPayment('CRÉDIT'));
  check('CREDIT (sans accent) accepte', isCreditPayment('CREDIT'));
  check('ESPECES n\'est pas du credit', !isCreditPayment('ESPÈCES') && !isCreditPayment('CASH'));

  console.log('\n== 2. Credit sans acompte (vente a terme) ==');
  const sale1 = createSale({
    customer_id: 7, cashier_id: 1, payment_method: 'CRÉDIT',
    amount_paid: 0, items: item, tax_amount: 0,
  });
  check('statut de paiement PENDING', sale1.payment_status === 'PENDING', sale1.payment_status);
  check('reste du = total (5000)', money(sale1.due) === 5000 && money(sale1.amount_paid) === 0,
    `due=${sale1.due}`);
  check('dette du client = total', balanceOf() === 5000, `balance=${balanceOf()}`);
  check('aucune entree de tresorerie (rien recu)', movementsOf(sale1.id).length === 0,
    `${movementsOf(sale1.id).length}`);
  check('stock debite une unite', money(db.data.products[0].quantity) === 49,
    String(db.data.products[0].quantity));
  check('facture presente dans les credits a encaisser',
    listCreditSales(3).length === 1 && saleDue(sale1) === 5000,
    `n=${listCreditSales(3).length}`);

  console.log('\n== 3. Encaissement partiel ==');
  const part = receivePayment({ sale_id: sale1.id, amount: 2000, payment_method: 'CASH' });
  check('statut PARTIAL apres acompte de 2000', part.payment_status === 'PARTIAL', part.payment_status);
  check('reste du = 3000', money(part.due) === 3000, `due=${part.due}`);
  check('dette du client diminue de 2000', balanceOf() === 3000, `balance=${balanceOf()}`);
  const mv1 = movementsOf(sale1.id);
  check('tresorerie creditee de 2000', mv1.length === 1 && money(mv1[0].amount) === 2000,
    `${mv1.length}`);
  check('compte de caisse mis a jour', money(db.data.treasuryAccounts[0].current_balance) === 2000,
    String(db.data.treasuryAccounts[0].current_balance));

  console.log('\n== 4. Encaissement superieur au reste du refuse ==');
  let refused = null;
  try { receivePayment({ sale_id: sale1.id, amount: 999999, payment_method: 'CASH' }); }
  catch (err) { refused = err; }
  check('exception levec', refused instanceof Error, refused ? refused.message : 'aucune');
  check('dette inchangee apres tentative refusee', balanceOf() === 3000, `balance=${balanceOf()}`);

  console.log('\n== 5. Solde du credit total ==');
  const rest = receivePayment({ sale_id: sale1.id, amount: 3000, payment_method: 'MOBILE_MONEY' });
  check('facture soldee (PAID)', rest.payment_status === 'PAID' && rest.statut === 'PAYEE',
    `${rest.payment_status}/${rest.statut}`);
  check('dette du client remise a zero', balanceOf() === 0, `balance=${balanceOf()}`);
  check('plus aucune facture a encaisser', listCreditSales(3).length === 0,
    `${listCreditSales(3).length}`);

  console.log('\n== 6. Credit avec acompte de 30 % ==');
  const sale2 = createSale({
    customer_id: 7, cashier_id: 1, payment_method: 'CREDIT',
    amount_paid: 1500, items: item, tax_amount: 0,
  });
  check('statut PARTIAL', sale2.payment_status === 'PARTIAL', sale2.payment_status);
  check('acompte non change', money(sale2.amount_paid) === 1500 && money(sale2.change_amount) === 0);
  check('reste du = 3500 (part impayee seulement)', money(sale2.due) === 3500, `due=${sale2.due}`);
  check('dette du client = 3500 (pas 5000)', balanceOf() === 3500, `balance=${balanceOf()}`);
  const mv2 = movementsOf(sale2.id);
  check('tresorerie = acompte 1500 uniquement', mv2.length === 1 && money(mv2[0].amount) === 1500,
    `${mv2.map((m) => m.amount).join(',')}`);

  console.log('\n== 7. ESPERES : monnaie rendue, tresorerie = total ==');
  const sale3 = createSale({
    customer_id: null, cashier_id: 1, payment_method: 'ESPÈCES',
    amount_paid: 7000, items: item, tax_amount: 0,
  });
  check('vente payee (PAID)', sale3.payment_status === 'PAID', sale3.payment_status);
  check('monnaie a rendre = 2000', money(sale3.change_amount) === 2000, `change=${sale3.change_amount}`);
  const mv3 = movementsOf(sale3.id);
  check('tresorerie = 5000 (total, pas la monnaie rendue)',
    mv3.length === 1 && money(mv3[0].amount) === 5000, `${mv3.map((m) => m.amount).join(',')}`);

  console.log('\n== 8. Moyen immediat sans montant saisi ==');
  const sale4 = createSale({
    customer_id: null, cashier_id: 1, payment_method: 'MOBILE_MONEY',
    amount_paid: 0, items: item, tax_amount: 0,
  });
  check('paye en totalite', sale4.payment_status === 'PAID' && money(sale4.amount_paid) === 5000,
    `${sale4.payment_status}/${sale4.amount_paid}`);

  console.log('\n== 9. Synchronisation Supabase ==');
  const before = balanceOf();
  db.persist();
  await db.flush();
  const customerRows = calls
    .filter((c) => c.method === 'POST' && c.path === '/rest/v1/customers')
    .flatMap((c) => c.body || []);
  const pushed = customerRows.find((r) => r.id === 7);
  check('clients envoyes a Supabase', Boolean(pushed), `n=${customerRows.length}`);
  check('customers.balance pousse (dette visible des autres applications)',
    pushed && money(pushed.balance) === before, `balance envoyee=${pushed ? pushed.balance : 'absent'}`);
  const saleRows = calls
    .filter((c) => c.method === 'POST' && c.path === '/rest/v1/sales')
    .flatMap((c) => c.body || []);
  check('ventes envoyees avec la colonne sale_number (rename number)',
    saleRows.length > 0 && saleRows.every((r) => 'sale_number' in r), `n=${saleRows.length}`);
  check('aucune erreur de synchronisation', syncState.lastError === null,
    String(syncState.lastError));
} finally {
  await server.close();
}

console.log(`\n${failures === 0 ? 'TOUS LES TESTS SONT PASSES' : `${failures} TEST(S) EN ECHEC`}`);
process.exitCode = failures === 0 ? 0 : 1;

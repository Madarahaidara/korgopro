/**
 * Test HTTP RÉEL des RPC d'écriture du mobile (couche PostgREST).
 *
 * Reproduit exactement les appels de `src/api/rpc.js` (mêmes noms de
 * paramètres), ce qui valide la seule chose qu'un test SQL ne peut pas voir :
 * la résolution de la fonction par PostgREST.
 *
 * Erreur d'origine :
 *   « Could not find the function public.app_create_sale(p_account_id, ...)
 *     in the schema cache »   -> HTTP 404, code PGRST202
 *
 * Attendu ici, avec la clé publique (rôle `anon`) :
 *   * HTTP 42501 / 401 / 403  -> la fonction EXISTE et est protégée (OK) ;
 *   * HTTP 404 + PGRST202     -> la fonction est absente du cache (ECHEC).
 * Aucune donnée n'est écrite : `anon` n'a pas le droit d'exécuter ces RPC.
 *
 * Usage : node scripts/test-mobile-rpc-http.mjs
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');

let failures = 0;
function check(label, ok, detail = '') {
  if (!ok) failures += 1;
  console.log(`${ok ? 'OK   ' : 'ECHEC'} ${label}${detail ? `  (${detail})` : ''}`);
}

/** Lit mobile/.env sans dépendance externe (fichier ignoré par git). */
function loadEnv() {
  const out = {};
  for (const line of readFileSync(join(ROOT, '.env'), 'utf8').split(/\r?\n/)) {
    const m = line.match(/^([A-Z0-9_]+)\s*=\s*(.*)$/);
    if (m) out[m[1]] = m[2].trim().replace(/^["']|["']$/g, '');
  }
  return out;
}

// Payloads STRICTEMENT identiques à src/api/rpc.js.
const CALLS = {
  app_mobile_context: {},
  app_create_sale: {
    p_items: [{ product_id: 1, quantity: 1, unit_price: 1 }],
    p_store_id: null,
    p_customer_id: null,
    p_discount_amount: 0,
    p_tax_amount: 0,
    p_payment_method: 'CASH',
    p_amount_paid: 0,
    p_notes: '',
    p_currency: 'FCFA',
    p_account_id: null,
  },
  app_register_payment: {
    p_sale_id: 1, p_amount: 1, p_payment_method: 'CASH',
    p_account_id: null, p_notes: '',
  },
  app_stock_movement: {
    p_product_id: 1, p_movement_type: 'IN', p_quantity: 1, p_reason: null,
    p_unit_cost: null, p_reference: null, p_notes: null, p_store_id: null,
  },
  app_cancel_sale: { p_sale_id: 1, p_reason: null },
};

const env = loadEnv();
const url = (env.EXPO_PUBLIC_SUPABASE_URL || '').replace(/\/$/, '');
const key = env.EXPO_PUBLIC_SUPABASE_ANON_KEY || '';

if (!url || !key) {
  console.log('ECHEC mobile/.env incomplet (EXPO_PUBLIC_SUPABASE_URL / ANON_KEY)');
  process.exit(1);
}
console.log(`Projet : ${url}\n`);
check('mobile/.env renseigne', true, url.replace('https://', '').split('.')[0]);

for (const [name, params] of Object.entries(CALLS)) {
  let status = 0;
  let body = '';
  try {
    const res = await fetch(`${url}/rest/v1/rpc/${name}`, {
      method: 'POST',
      headers: {
        apikey: key,
        Authorization: `Bearer ${key}`,
        'Content-Type': 'application/json',
        'x-application-name': 'korgo-pro-mobile-test',
      },
      body: JSON.stringify(params),
      signal: AbortSignal.timeout(20000),
    });
    status = res.status;
    body = await res.text();
  } catch (e) {
    check(`${name} joignable`, false, e.message);
    continue;
  }

  const code = (body.match(/"code"\s*:\s*"([A-Z0-9]+)"/) || [])[1] || '';
  const missing = code === 'PGRST202' || /Could not find the function/i.test(body);
  const refused = status === 401 || status === 403 || code === '42501'
    || /permission denied|row-level security/i.test(body);

  check(`${name} presente dans le cache PostgREST`, !missing,
    missing ? `HTTP ${status} ${code} — appliquer supabase_mobile_rpc.sql`
      : `HTTP ${status}${code ? ` ${code}` : ''}`);
  check(`${name} protegee (non executable par anon)`, refused || missing === false,
    refused ? body.slice(0, 90).replace(/\s+/g, ' ') : body.slice(0, 90));
}

console.log(`\nResultat : ${failures === 0 ? 'TOUT OK' : `${failures} probleme(s)`}`);
process.exit(failures === 0 ? 0 : 1);

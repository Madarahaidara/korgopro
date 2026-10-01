// ============================================================================
// Lectures PostgREST (mobile).
//
// STRATÉGIE DE CHARGEMENT — différente du web, volontairement :
//   * le web télécharge TOUTES les tables dans un cache mémoire au login
//     (web/src/api/db.js -> hydrateAll) : acceptable sur un PC, coûteux sur un
//     téléphone en réseau mobile ;
//   * le mobile interroge Supabase À LA DEMANDE, avec recherche côté serveur et
//     des limites strictes (30 à 200 lignes). Rien n'est mis en cache hors
//     ligne : une écriture ne peut donc pas partir d'un état périmé.
//
// Les noms de colonnes sont ceux de PostgreSQL (sale_number, amount_paid…),
// sans la couche de renommage du web.
// ============================================================================
import { requireClient, run } from './supabase';

const PRODUCT_COLUMNS =
  'id,code,name,category,quantity,min_stock,max_stock,purchase_price,sale_price,' +
  'barcode,location,active,store_id,supplier_id';

const SALE_COLUMNS =
  'id,sale_number,sale_date,total_amount,amount_paid,change_amount,payment_status,' +
  'payment_method,sale_status,statut,customer_id,store_id,currency,' +
  'customers(first_name,last_name,phone)';

/** Ajoute les indicateurs dérivés utilisés par l'interface (comme le web). */
export function enrichProduct(product) {
  const quantity = Number(product.quantity) || 0;
  const minStock = Number(product.min_stock) || 0;
  return {
    ...product,
    quantity,
    isOutOfStock: quantity <= 0,
    isLowStock: quantity <= minStock,
    stockValue: quantity * (Number(product.purchase_price) || 0),
  };
}

/** Normalise une vente + le nom du client imbriqué. */
export function enrichSale(sale) {
  const total = Number(sale.total_amount) || 0;
  const paid = Number(sale.amount_paid) || 0;
  const customer = sale.customers
    ? [sale.customers.first_name, sale.customers.last_name].filter(Boolean).join(' ')
    : '';
  return {
    ...sale,
    total_amount: total,
    amount_paid: paid,
    due: Math.max(total - paid, 0),
    customer_name: customer || 'Client de passage',
    is_credit: sale.payment_status === 'PENDING' || sale.payment_status === 'PARTIAL',
  };
}

/** Supprime les caractères qui casseraient un filtre PostgREST (`or`). */
function sanitizeTerm(term) {
  return String(term || '').replace(/[%,()*]/g, ' ').trim();
}

// ---------------------------------------------------------------------------
// Magasins
// ---------------------------------------------------------------------------
export async function listStores(includeInactive = false) {
  const client = requireClient();
  let query = client.from('stores').select('id,code,name,address,phone,active');
  if (!includeInactive) query = query.eq('active', true);
  return run(query.order('code', { ascending: true }));
}

// ---------------------------------------------------------------------------
// Produits
// ---------------------------------------------------------------------------
/**
 * Recherche des produits (nom, code, code-barres) — recherche côté serveur.
 * `limit` est volontairement bas : on scrolle, on ne télécharge pas tout.
 */
export async function searchProducts({ storeId = null, query = '', limit = 30 } = {}) {
  const client = requireClient();
  let request = client.from('products').select(PRODUCT_COLUMNS).eq('active', true);
  if (storeId != null) request = request.eq('store_id', storeId);

  const term = sanitizeTerm(query);
  if (term) {
    request = request.or(
      `name.ilike.%${term}%,code.ilike.%${term}%,barcode.ilike.%${term}%`
    );
  }

  const rows = await run(request.order('name', { ascending: true }).limit(limit));
  return rows.map(enrichProduct);
}

/**
 * Produits en alerte (quantité <= seuil). Le seuil est une colonne, donc la
 * comparaison se fait côté client sur une page bornée.
 */
export async function listStockAlerts({ storeId = null, limit = 200 } = {}) {
  const client = requireClient();
  let request = client.from('products').select(PRODUCT_COLUMNS).eq('active', true);
  if (storeId != null) request = request.eq('store_id', storeId);
  const rows = await run(request.order('quantity', { ascending: true }).limit(limit));
  return rows.map(enrichProduct).filter((p) => p.isLowStock);
}

/** Un produit par identifiant (rafraîchissement ciblé après mouvement). */
export async function getProduct(id) {
  const client = requireClient();
  const rows = await run(
    client.from('products').select(PRODUCT_COLUMNS).eq('id', id).limit(1)
  );
  return rows.length ? enrichProduct(rows[0]) : null;
}

/** Derniers mouvements de stock d'un produit (historique de l'écran Inventaire). */
export async function listProductMovements(productId, limit = 8) {
  const client = requireClient();
  return run(
    client
      .from('inventory_movements')
      .select('id,product_id,movement_type,quantity,unit_price,total_value,reference,reason,date,user_id,store_id')
      .eq('product_id', productId)
      .order('date', { ascending: false })
      .limit(limit)
  );
}

// ---------------------------------------------------------------------------
// Clients
// ---------------------------------------------------------------------------
export async function searchCustomers({ query = '', limit = 30 } = {}) {
  const client = requireClient();
  let request = client
    .from('customers')
    .select('id,code,first_name,last_name,company,phone,mobile,balance,credit_limit,active')
    .eq('active', true);

  const term = sanitizeTerm(query);
  if (term) {
    request = request.or(
      `first_name.ilike.%${term}%,last_name.ilike.%${term}%,company.ilike.%${term}%,` +
        `phone.ilike.%${term}%,mobile.ilike.%${term}%`
    );
  }

  const rows = await run(request.order('last_name', { ascending: true }).limit(limit));
  return rows.map((c) => ({
    ...c,
    full_name:
      [c.first_name, c.last_name].filter(Boolean).join(' ') || c.company || 'Client',
  }));
}

// ---------------------------------------------------------------------------
// Ventes
// ---------------------------------------------------------------------------
/** Une vente par identifiant (écran Factures : détail / vérification ciblée). */
export async function getSale(id, { storeId = null } = {}) {
  const client = requireClient();
  let request = client.from('sales').select(SALE_COLUMNS).eq('id', id);
  if (storeId != null) request = request.eq('store_id', storeId);
  const rows = await run(request.limit(1));
  return rows.length ? enrichSale(rows[0]) : null;
}

/** Ventes du jour (magasin actif) — statistiques de caisse. */
export async function listTodaySales(storeId, bounds) {
  const client = requireClient();
  let request = client
    .from('sales')
    .select(SALE_COLUMNS)
    .gte('sale_date', bounds.start)
    .lt('sale_date', bounds.end)
    .order('sale_date', { ascending: false });
  if (storeId != null) request = request.eq('store_id', storeId);
  const rows = await run(request.limit(300));
  return rows.map(enrichSale).filter((s) => s.sale_status !== 'CANCELLED');
}

/** Factures restant à encaisser (crédits et paiements partiels). */
export async function listOpenSales({ storeId = null, limit = 100 } = {}) {
  const client = requireClient();
  let request = client
    .from('sales')
    .select(SALE_COLUMNS)
    .in('payment_status', ['PENDING', 'PARTIAL'])
    .neq('sale_status', 'CANCELLED')
    .order('sale_date', { ascending: true });
  if (storeId != null) request = request.eq('store_id', storeId);
  const rows = await run(request.limit(limit));
  return rows.map(enrichSale).filter((s) => s.due > 0.001);
}

/** Dernières ventes, tous statuts (activité récente). */
export async function listRecentSales({ storeId = null, limit = 20 } = {}) {
  const client = requireClient();
  let request = client
    .from('sales')
    .select(SALE_COLUMNS)
    .order('sale_date', { ascending: false });
  if (storeId != null) request = request.eq('store_id', storeId);
  const rows = await run(request.limit(limit));
  return rows.map(enrichSale);
}

// ---------------------------------------------------------------------------
// Trésorerie
// ---------------------------------------------------------------------------
export async function listAccounts() {
  const client = requireClient();
  return run(
    client
      .from('treasury_accounts')
      .select('id,name,account_type,currency,current_balance,is_active,is_default')
      .eq('is_active', true)
      .order('id', { ascending: true })
  );
}

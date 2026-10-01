// ============================================================================
// Stats tableau de bord (mobile). Miroir de web/src/api/statsApi.js :
// mêmes clés de retour, calculées à la demande via PostgREST (pas de cache).
// ============================================================================
import { listAccounts } from './treasuryApi';
import { listRecentSales, listStockAlerts, searchProducts } from './dataApi';
import { requireClient, run } from './supabase';

/** Agrège les stats du magasin actif (7 derniers jours inclus). */
export async function getDashboardStats({ storeId = null } = {}) {
  const [sales, products, accounts, counts] = await Promise.all([
    listRecentSales({ storeId, limit: 200 }).catch(() => []),
    searchProducts({ storeId, query: '', limit: 200 }).catch(() => []),
    listAccounts().catch(() => []),
    fetchCounts().catch(() => ({ customers: 0, proformasPending: 0 })),
  ]);

  const totalSales = sales.reduce((s, x) => s + (Number(x.total_amount) || 0), 0);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const salesToday = sales
    .filter((s) => new Date(s.sale_date) >= today)
    .reduce((s, x) => s + (Number(x.total_amount) || 0), 0);

  const stockValue = products.reduce(
    (s, p) => s + (Number(p.quantity) || 0) * (Number(p.purchase_price) || 0), 0
  );
  const stockSellValue = products.reduce(
    (s, p) => s + (Number(p.quantity) || 0) * (Number(p.sale_price) || 0), 0
  );
  const lowStock = products.filter((p) => p.isLowStock).length;
  const outOfStock = products.filter((p) => p.isOutOfStock).length;

  const cashBalance = accounts.reduce((s, a) => s + (Number(a.balance) || 0), 0);

  const alerts = await listStockAlerts({ storeId, limit: 200 }).catch(() => []);

  const last7 = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    d.setDate(d.getDate() - i);
    const next = new Date(d);
    next.setDate(next.getDate() + 1);
    const amount = sales
      .filter((s) => {
        const dt = new Date(s.sale_date);
        return dt >= d && dt < next;
      })
      .reduce((sum, s) => sum + (Number(s.total_amount) || 0), 0);
    last7.push({
      label: d.toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric' }),
      amount,
    });
  }

  const salesByStatus = sales.reduce((obj, s) => {
    const key = s.statut || 'EMISE';
    obj[key] = (obj[key] || 0) + 1;
    return obj;
  }, {});

  return {
    totalSales,
    salesToday,
    salesCount: sales.length,
    stockValue,
    stockSellValue,
    lowStock: lowStock || alerts.length,
    outOfStock,
    cashBalance,
    totalIn: null,
    totalOut: null,
    proformaPending: counts.proformasPending,
    customerCount: counts.customers,
    productCount: products.length,
    last7,
    salesByStatus,
  };
}

/** Compteurs légers : clients + proformas en attente (requêtes COUNT). */
async function fetchCounts() {
  const client = requireClient();
  const [customers, proformas] = await Promise.all([
    run(client.from('customers').select('id', { count: 'exact', head: true }).eq('active', true)),
    run(
      client.from('proforma_invoices')
        .select('id', { count: 'exact', head: true })
        .in('status', ['BROUILLON', 'EN_ATTENTE', 'ENVOYEE'])
    ),
  ]);
  const countOf = (res) => (typeof res?.count === 'number' ? res.count : 0);
  return { customers: countOf(customers) ?? 0, proformasPending: countOf(proformas) ?? 0 };
}

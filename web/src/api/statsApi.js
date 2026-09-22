// ============================================================================
// Service de statistiques pour le tableau de bord et les indicateurs.
// ============================================================================
import { db } from './db';
import { getActiveStoreId } from './storesApi';

/** Retourne toutes les statistiques du tableau de bord (magasin actif). */
export function getDashboardStats() {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const sid = getActiveStoreId();

  const sales = (db.data.sales || []).filter((s) => s.store_id === sid);
  const products = (db.data.products || []).filter((p) => p.store_id === sid);
  const customers = db.data.customers || [];
  const proformas = db.data.proformas || [];
  const accounts = db.data.treasuryAccounts || [];

  const totalSales = sales.reduce((s, x) => s + (x.total_amount || 0), 0);
  const salesToday = sales
    .filter((s) => new Date(s.sale_date) >= today)
    .reduce((s, x) => s + (x.total_amount || 0), 0);

  const stockValue = products.reduce(
    (s, p) => s + (p.quantity || 0) * (p.purchase_price || 0),
    0
  );
  const stockSellValue = products.reduce(
    (s, p) => s + (p.quantity || 0) * (p.sale_price || 0),
    0
  );
  const lowStock = products.filter(
    (p) => (p.quantity || 0) <= (p.min_stock || 0) && p.active !== false
  ).length;
  const outOfStock = products.filter(
    (p) => (p.quantity || 0) <= 0 && p.active !== false
  ).length;

  const cashBalance = accounts.reduce((s, a) => s + (a.current_balance || 0), 0);
  const totalIn = (db.data.treasuryMovements || [])
    .filter((m) => m.movement_type === 'IN')
    .reduce((s, m) => s + (m.amount || 0), 0);
  const totalOut = (db.data.treasuryMovements || [])
    .filter((m) => m.movement_type === 'OUT')
    .reduce((s, m) => s + (m.amount || 0), 0);

  const proformaPending = proformas.filter((p) =>
    ['BROUILLON', 'EN_ATTENTE', 'ENVOYEE'].includes(p.status)
  ).length;

  // Ventes des 7 derniers jours pour le graphique
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
      .reduce((sum, s) => sum + (s.total_amount || 0), 0);
    last7.push({
      label: d.toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric' }),
      amount,
    });
  }

  // Répartition des ventes par statut
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
    lowStock,
    outOfStock,
    cashBalance,
    totalIn,
    totalOut,
    proformaPending,
    customerCount: customers.length,
    productCount: products.length,
    last7,
    salesByStatus,
  };
}
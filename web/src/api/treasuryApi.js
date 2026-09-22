// ============================================================================
// Service de trésorerie.
// Reprend les modèles treasury_models.py (comptes, mouvements, sessions).
// ============================================================================
import { db } from './db';

export const ACCOUNT_TYPES = ['CASH', 'BANK', 'MOBILE_MONEY'];
export const MOVEMENT_TYPES = ['IN', 'OUT'];

/** Liste des comptes de trésorerie. */
export function listAccounts() {
  return (db.data.treasuryAccounts || []).map((a) => ({
    ...a,
    balance: a.current_balance || a.initial_balance || 0,
  }));
}

export function listAccountsData() {
  return db.data.treasuryAccounts || [];
}

/** Crée ou met à jour un compte de trésorerie. */
export function saveAccount(account) {
  const items = db.data.treasuryAccounts || [];
  if (account.id) {
    const idx = items.findIndex((a) => a.id === Number(account.id));
    if (idx >= 0) items[idx] = { ...items[idx], ...account };
  } else {
    items.push({
      id: Math.max(0, ...items.map((a) => a.id)) + 1,
      name: account.name,
      account_type: account.account_type || 'CASH',
      currency: account.currency || db.data.settings.currency,
      initial_balance: Number(account.initial_balance) || 0,
      current_balance: Number(account.initial_balance) || 0,
      bank_name: account.bank_name || '',
      account_number: account.account_number || '',
      phone_number: account.phone_number || '',
      is_active: account.is_active !== false,
      is_default: !!account.is_default,
      notes: account.notes || '',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
  }
  db.persist();
  return listAccounts();
}

/** Liste des mouvements de trésorerie, triés du plus récent au plus ancien. */
export function listMovements() {
  return (db.data.treasuryMovements || [])
    .slice()
    .sort((a, b) => new Date(b.date) - new Date(a.date))
    .map((m) => ({
      ...m,
      accountName: accountName(m.account_id),
    }));
}

function accountName(id) {
  const a = (db.data.treasuryAccounts || []).find((x) => x.id === Number(id));
  return a ? a.name : '';
}

/** Crée un mouvement (IN/OUT) et ajuste le solde du compte. */
export function createMovement(movement) {
  const m = {
    id: Math.max(0, ...(db.data.treasuryMovements || []).map((x) => x.id)) + 1,
    account_id: Number(movement.account_id),
    movement_type: movement.movement_type,
    amount: Number(movement.amount),
    date: movement.date || new Date().toISOString(),
    reference: movement.reference || '',
    description: movement.description || '',
    category: movement.category || 'Autre',
    reference_type: movement.reference_type || 'MANUAL',
    reference_id: movement.reference_id || null,
    user_id: movement.user_id || null,
    created_at: new Date().toISOString(),
  };
  db.data.treasuryMovements = db.data.treasuryMovements || [];
  db.data.treasuryMovements.unshift(m);

  const account = (db.data.treasuryAccounts || []).find((a) => a.id === m.account_id);
  if (account) {
    const delta = m.movement_type === 'IN' ? m.amount : -m.amount;
    account.current_balance = (account.current_balance || 0) + delta;
  }
  db.persist();
  return m;
}

/** Synthétise la trésorerie : total par type de compte. */
export function treasurySummary() {
  const accounts = listAccounts();
  const total = accounts.reduce((s, a) => s + (a.balance || 0), 0);
  const byType = ACCOUNT_TYPES.reduce((obj, t) => {
    obj[t] = accounts.filter((a) => a.account_type === t).reduce((s, a) => s + (a.balance || 0), 0);
    return obj;
  }, {});
  return { total, byType, count: accounts.length };
}

// ============================================================================
// Clôtures mensuelles des ventes
// ============================================================================

/** Période 'YYYY-MM' d'une date (mois courant par défaut). */
export function monthPeriod(date = new Date()) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
}

const MONTH_NAMES = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];

/** '2026-09' -> 'septembre 2026' */
export function periodLabel(period) {
  const [y, m] = String(period).split('-').map(Number);
  return `${MONTH_NAMES[m - 1] || '?'} ${y}`;
}

/** Liste des clôtures, de la plus récente à la plus ancienne. */
export function listClosures() {
  return (db.data.monthlyClosures || [])
    .slice()
    .sort((a, b) => String(b.period).localeCompare(String(a.period)));
}

/** Clôture existante d'une période (ou null). */
export function getClosure(period) {
  return (db.data.monthlyClosures || []).find((c) => c.period === period) || null;
}

/** Bornes [début, fin) du mois pour un filtrage par date. */
function monthBounds(period) {
  const [y, m] = String(period).split('-').map(Number);
  const start = new Date(y, m - 1, 1);
  const end = new Date(y, m, 1);
  return { start, end, inMonth: (iso) => { const d = new Date(iso); return d >= start && d < end; } };
}

/**
 * Calcule les totaux du mois à partir des ventes et mouvements actuels :
 * ventes (hors annulations/avoirs), encaissé (amount_paid - change),
 * crédit restant dû, dépenses (mouvements OUT hors encaissements de ventes),
 * net = encaissé - dépenses, et snapshot des soldes de comptes.
 */
export function computeMonthlyPreview(period) {
  const { inMonth } = monthBounds(period);
  const sales = (db.data.sales || []).filter(
    (s) => s.sale_status !== 'CANCELLED'
      && s.type_document !== 'AVOIR'
      && inMonth(s.sale_date || s.date)
  );
  const totalSales = sales.reduce((sum, s) => sum + (Number(s.total_amount) || 0), 0);
  const collected = sales.reduce(
    (sum, s) => sum + Math.max(0, (Number(s.amount_paid) || 0) - (Number(s.change_amount) || 0)),
    0
  );
  const out = (db.data.treasuryMovements || []).filter(
    (mv) => mv.movement_type === 'OUT'
      && mv.reference_type !== 'SALE'
      && inMonth(mv.date)
  ).reduce((sum, mv) => sum + (Number(mv.amount) || 0), 0);
  const balances = listAccounts().map((a) => ({
    id: a.id, name: a.name, account_type: a.account_type,
    currency: a.currency, balance: a.balance || 0,
  }));
  return {
    sales_count: sales.length,
    total_sales: totalSales,
    total_collected: collected,
    total_credit: totalSales - collected,
    total_out: out,
    net: collected - out,
    balances,
  };
}

/**
 * Clôture une période : fige les totaux du mois dans un enregistrement
 * CLOSED. Refus si le mois est déjà clôturé.
 */
export function closeMonth(period, user, notes = '') {
  if (getClosure(period)?.status === 'CLOSED') {
    throw new Error('Ce mois est déjà clôturé.');
  }
  const preview = computeMonthlyPreview(period);
  const existing = getClosure(period);
  const record = {
    id: existing?.id || Math.max(0, ...(db.data.monthlyClosures || []).map((c) => c.id)) + 1,
    period,
    ...preview,
    status: 'CLOSED',
    closed_by: user?.id || null,
    closed_at: new Date().toISOString(),
    notes: notes || existing?.notes || '',
  };
  db.data.monthlyClosures = db.data.monthlyClosures || [];
  if (existing) {
    const idx = db.data.monthlyClosures.findIndex((c) => c.period === period);
    db.data.monthlyClosures[idx] = record;
  } else {
    db.data.monthlyClosures.push(record);
  }
  db.persist();
  return record;
}
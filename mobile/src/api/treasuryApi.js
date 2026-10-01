// ============================================================================
// Trésorerie : lecture Supabase (+ résumés calculés comme le web).
// Miroir de web/src/api/treasuryApi.js. Écritures : RPC (ventes/encaissements)
// ou admin — pas d'insert direct (RLS 42501).
// ============================================================================
import { listAccounts as listAccountsRaw } from './dataApi';
import { requireClient, run } from './supabase';

export const ACCOUNT_TYPES = ['CASH', 'BANK', 'MOBILE_MONEY'];
export const MOVEMENT_TYPES = ['IN', 'OUT'];
export const TYPE_LABELS = { CASH: 'Caisse', BANK: 'Banque', MOBILE_MONEY: 'Mobile Money' };

/** Comptes actifs + solde normalisé (comme web listAccounts). */
export async function listAccounts() {
  const rows = await listAccountsRaw();
  return rows.map((a) => ({
    ...a,
    balance: Number(a.current_balance) || 0,
    is_default: !!a.is_default,
    is_active: a.is_active !== false,
  }));
}

export async function listMovements({ limit = 60 } = {}) {
  const client = requireClient();
  const accounts = await listAccounts().catch(() => []);
  const byId = new Map(accounts.map((a) => [a.id, a.name]));
  const rows = await run(
    client
      .from('treasury_movements')
      .select('id,account_id,movement_type,amount,date,reference,description,category,reference_type,reference_id,user_id')
      .order('date', { ascending: false })
      .limit(limit)
  );
  return rows.map((m) => ({ ...m, accountName: byId.get(m.account_id) || '' }));
}

/** Synthèse total + par type (copie web treasurySummary). */
export async function treasurySummary() {
  const accounts = await listAccounts();
  const total = accounts.reduce((s, a) => s + (Number(a.balance) || 0), 0);
  const byType = {};
  ACCOUNT_TYPES.forEach((t) => {
    byType[t] = accounts
      .filter((a) => a.account_type === t)
      .reduce((s, a) => s + (Number(a.balance) || 0), 0);
  });
  return { total, byType, count: accounts.length };
}

export async function listClosures({ limit = 24 } = {}) {
  const client = requireClient();
  return run(
    client.from('monthly_closures').select('*').order('period', { ascending: false }).limit(limit)
  );
}

export function monthPeriod(date = new Date()) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
}

const MONTH_NAMES = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];

export function periodLabel(period) {
  const [y, m] = String(period).split('-').map(Number);
  return `${MONTH_NAMES[m - 1] || '?'} ${y}`;
}

function writeBlocked(label) {
  throw new Error(
    `${label} : écriture directe refusée par RLS (admin/RPC uniquement).`
  );
}

export async function saveAccount() {
  writeBlocked('saveAccount');
}

export async function createMovement() {
  writeBlocked('createMovement (passer par app_create_sale / app_register_payment)');
}

export async function closeMonth() {
  writeBlocked('closeMonth (réservé admin)');
}

export function computeMonthlyPreview() {
  throw new Error('computeMonthlyPreview : aperçu serveur non exposé en RPC (lecture closures uniquement).');
}

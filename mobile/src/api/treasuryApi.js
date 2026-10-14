// ============================================================================
// Trésorerie (mobile) — lecture Supabase + écritures par RPC.
// Miroir de web/src/api/treasuryApi.js. Écritures : RPC app_treasury_*
// (supabase_mobile_rpc.sql) — pas d'insert direct (RLS 42501).
// ============================================================================
import { listAccounts as listAccountsRaw } from './dataApi';
import {
  closeTreasuryMonth,
  createTreasuryMovement,
  saveTreasuryAccount,
  transferTreasury,
  treasuryMonthPreview,
} from './rpc';
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

/**
 * Crée ou met à jour un compte (mirroir web saveAccount). Le solde courant
 * n'est modifiable que par les mouvements : la RPC ne touche jamais
 * `current_balance` sur une modification.
 */
export async function saveAccount(account) {
  await saveTreasuryAccount({
    id: account.id ? Number(account.id) : null,
    name: account.name,
    accountType: account.account_type || 'CASH',
    currency: account.currency || null,
    initialBalance: Number(account.initial_balance) || 0,
    bankName: account.bank_name || '',
    accountNumber: account.account_number || '',
    phoneNumber: account.phone_number || '',
    isActive: account.is_active !== false,
    isDefault: !!account.is_default,
    notes: account.notes || '',
  });
  return listAccounts();
}

/**
 * Crée un mouvement manuel IN/OUT et ajuste le solde du compte — transaction
 * unique côté serveur (RPC app_treasury_move).
 */
export async function createMovement(movement) {
  return createTreasuryMovement({
    accountId: Number(movement.account_id),
    movementType: movement.movement_type,
    amount: Number(movement.amount),
    reference: movement.reference || '',
    description: movement.description || '',
    category: movement.category || '',
    date: movement.date || null,
  });
}

/** Transfert entre deux comptes (OUT source + IN destination). */
export async function transfer({ fromAccountId, toAccountId, amount, description = '' }) {
  return transferTreasury({
    fromAccountId: Number(fromAccountId),
    toAccountId: Number(toAccountId),
    amount: Number(amount),
    description,
  });
}

/**
 * Clôture mensuelle : les totaux sont recalculés par le serveur puis figés.
 * Refus si le mois est déjà clôturé ou si le rôle n'est pas ADMIN.
 */
export async function closeMonth(period, _user = null, notes = '') {
  return closeTreasuryMonth(period, notes);
}

/**
 * Aperçu des totaux du mois (mirroir web computeMonthlyPreview) : ventes hors
 * annulations/avoirs, encaissé, crédit, dépenses, net + statut de clôture.
 * Lecture seule, calculée par le serveur (RPC app_treasury_month_preview).
 */
export async function computeMonthlyPreview(period) {
  const data = await treasuryMonthPreview(period);
  if (data && data.ok === false) {
    throw new Error(data.message || 'Aperçu de période impossible.');
  }
  return data;
}

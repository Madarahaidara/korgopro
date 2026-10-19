// ============================================================================
// Administration mobile — accès limité aux profils et journaux autorisés
// par les politiques RLS et aux RPC d'administration Supabase.
// ============================================================================
import { PERMISSIONS, CANONICAL_ROLES, ROLE_LABELS, permissionsOf } from '../lib/permissions';
import { friendlyError, requireClient, run } from './supabase';

const USER_COLUMNS = 'id,username,email,role,active,created_at,last_login';
const PAGE_SIZE = 30;

function throwIfError(error) {
  if (!error) return;
  const err = new Error(friendlyError(error));
  err.code = error.code;
  throw err;
}

async function callAdminRpc(name, params) {
  const { data, error } = await requireClient().rpc(name, params);
  throwIfError(error);
  if (data && typeof data === 'object' && data.ok === false) {
    throw new Error(data.message || `Opération refusée par ${name}.`);
  }
  return data;
}

function applyDateFilters(query, startDate, endDate, column = 'created_at') {
  if (startDate) query = query.gte(column, `${startDate}T00:00:00`);
  if (endDate) query = query.lte(column, `${endDate}T23:59:59.999`);
  return query;
}

function cleanSearch(value) {
  return String(value || '').replace(/[%,()*]/g, ' ').trim();
}

export { CANONICAL_ROLES, PAGE_SIZE, PERMISSIONS, ROLE_LABELS };

export function getRolePermissions(role) {
  return permissionsOf(role);
}

export async function listAdminUsers() {
  return run(
    requireClient()
      .from('users')
      .select(USER_COLUMNS)
      .order('created_at', { ascending: false })
  );
}

export function updateAdminUser({ email, username, role }) {
  return callAdminRpc('admin_update_user_profile', {
    p_email: email,
    p_username: username,
    p_role: role,
    p_active: null,
    p_new_email: null,
  });
}

export function setAdminUserActive(email, active) {
  return callAdminRpc('admin_set_user_active', { p_email: email, p_active: active });
}

export function setAdminUserPassword(email, password) {
  return callAdminRpc('admin_set_user_password', {
    p_email: email,
    p_password: password,
    p_must_change_password: true,
  });
}

export function deleteAdminUser(email) {
  return callAdminRpc('admin_delete_user', { p_email: email });
}

export async function listActivityLogs({
  username = '',
  action = '',
  startDate = '',
  endDate = '',
  page = 0,
} = {}) {
  let query = requireClient()
    .from('activity_logs')
    .select('id,username,action,details,ip_address,user_agent,created_at', { count: 'exact' })
    .order('created_at', { ascending: false })
    .range(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE - 1);

  const userTerm = cleanSearch(username);
  const actionTerm = cleanSearch(action);
  if (userTerm) query = query.ilike('username', `%${userTerm}%`);
  if (actionTerm) query = query.ilike('action', `%${actionTerm}%`);
  query = applyDateFilters(query, startDate, endDate);

  const { data, count, error } = await query;
  throwIfError(error);
  return { rows: data || [], total: count || 0 };
}

export async function listSaleLogs({
  saleNumber = '',
  username = '',
  customerName = '',
  action = '',
  startDate = '',
  endDate = '',
  page = 0,
} = {}) {
  let query = requireClient()
    .from('sale_logs')
    .select(
      'id,sale_id,sale_number,action,username,user_role,customer_name,total_amount,payment_method,details,ip_address,created_at',
      { count: 'exact' }
    )
    .order('created_at', { ascending: false })
    .range(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE - 1);

  const numberTerm = cleanSearch(saleNumber);
  const userTerm = cleanSearch(username);
  const customerTerm = cleanSearch(customerName);
  const actionTerm = cleanSearch(action);
  if (numberTerm) query = query.ilike('sale_number', `%${numberTerm}%`);
  if (userTerm) query = query.ilike('username', `%${userTerm}%`);
  if (customerTerm) query = query.ilike('customer_name', `%${customerTerm}%`);
  if (actionTerm) query = query.eq('action', actionTerm);
  query = applyDateFilters(query, startDate, endDate);

  const { data, count, error } = await query;
  throwIfError(error);
  return { rows: data || [], total: count || 0 };
}

export async function deleteOldActivityLogs(days = 30) {
  const cutoff = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();
  const { data, error } = await requireClient()
    .from('activity_logs')
    .delete()
    .lt('created_at', cutoff)
    .select('id');
  throwIfError(error);
  return data?.length || 0;
}

const DATABASE_TABLES = [
  'users',
  'stores',
  'customers',
  'suppliers',
  'products',
  'sales',
  'sale_items',
  'payments',
  'sale_returns',
  'sale_return_items',
  'proforma_invoices',
  'proforma_invoice_items',
  'inventory_movements',
  'purchase_orders',
  'purchase_order_items',
  'stock_alerts',
  'sale_logs',
  'activity_logs',
  'treasury_accounts',
  'treasury_movements',
  'monthly_closures',
  'cash_register_sessions',
];

export async function getDatabaseTableCounts() {
  const client = requireClient();
  const counts = await Promise.all(
    DATABASE_TABLES.map(async (table) => {
      const { count, error } = await client.from(table).select('id', {
        count: 'exact',
        head: true,
      });
      throwIfError(error);
      return { table, count: count || 0 };
    })
  );
  return counts;
}

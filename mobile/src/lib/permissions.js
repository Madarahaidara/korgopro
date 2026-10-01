// ============================================================================
// Rôles et permissions — réplique de core/permissions.py (source unique du
// dépôt, déjà partagée entre le desktop et le web).
//
// L'application mobile n'invente AUCUNE règle : elle masque les écrans avec la
// même matrice que celle appliquée par les RPC PostgreSQL
// (supabase_mobile_rpc.sql -> app_security.can). En cas de divergence, c'est le
// serveur qui a raison : les RPC refusent l'écriture avec une erreur explicite.
//
// ATTENTION : si core/permissions.py évolue, mettre à jour les 3 endroits —
// core/permissions.py, mobile/src/lib/permissions.js et la matrice SQL.
// ============================================================================

/** Rôles canoniques reconnus par l'application. */
export const CANONICAL_ROLES = ['ADMIN', 'GESTIONNAIRE', 'SUPERVISEUR', 'ASSISTANT', 'CAISSIER'];

/** Synonymes historiques (GERANT = GESTIONNAIRE). */
const ROLE_ALIASES = { GERANT: 'GESTIONNAIRE' };

/** Libellés affichés. */
export const ROLE_LABELS = {
  ADMIN: 'Administrateur',
  GESTIONNAIRE: 'Gestionnaire',
  SUPERVISEUR: 'Superviseur',
  ASSISTANT: 'Assistant',
  CAISSIER: 'Caissier',
};

/** Toutes les clés du vocabulaire (ordre d'affichage). */
export const PERMISSIONS = [
  'view_dashboard',
  'view_sales',
  'create_sales',
  'cancel_sales',
  'view_invoice_register',
  'manage_proformas',
  'view_stock',
  'manage_stock',
  'manage_stores',
  'view_treasury',
  'manage_treasury',
  'manage_customers',
  'view_reports',
  'access_admin',
  'manage_users',
  'manage_database',
  'manage_settings',
  'export_data',
  'view_audit_logs',
];

const GESTIONNAIRE = [
  'view_dashboard', 'view_sales', 'create_sales', 'cancel_sales',
  'view_invoice_register', 'manage_proformas', 'view_stock', 'manage_stock',
  'manage_stores', 'view_treasury', 'manage_treasury', 'manage_customers',
  'view_reports', 'export_data',
];

/** Matrice de référence (_MATRIX de core/permissions.py). */
const MATRIX = {
  ADMIN: PERMISSIONS,
  GESTIONNAIRE,
  SUPERVISEUR: [...GESTIONNAIRE, 'access_admin', 'view_audit_logs'],
  ASSISTANT: [
    'view_dashboard', 'create_sales', 'view_invoice_register',
    'manage_proformas', 'manage_customers',
  ],
  CAISSIER: [
    'view_dashboard', 'create_sales', 'view_invoice_register',
    'manage_proformas', 'view_treasury', 'manage_customers',
  ],
};

/** Rôle inconnu ou hérité : tableau de bord uniquement. */
export const UNKNOWN_ROLE_PERMISSIONS = ['view_dashboard'];

/** Normalise un rôle (majuscules, synonymes) — normalize_role(). */
export function normalizeRole(role) {
  const value = String(role ?? '').trim().toUpperCase();
  return ROLE_ALIASES[value] || value;
}

/** Permissions d'un rôle (permissions_of()). */
export function permissionsOf(role) {
  return MATRIX[normalizeRole(role)] || UNKNOWN_ROLE_PERMISSIONS;
}

/** ``true`` si le rôle possède la permission (can()). */
export function can(role, permission) {
  if (!PERMISSIONS.includes(permission)) return false;
  return permissionsOf(role).includes(permission);
}

/** Libellé lisible d'un rôle. */
export function roleLabel(role) {
  const normalized = normalizeRole(role);
  return ROLE_LABELS[normalized] || (role ? String(role) : '');
}

// ============================================================================
// Korgo Pro Web — Passerelle Supabase (mapping + hydratation + synchro)
//
// OBJECTIF : brancher l'application web sur la MÊME base Supabase que l'app
// desktop, SANS réécrire les composants (qui utilisent une API synchrone).
//
// PRINCIPE (cache mémoire + écriture différée) :
//   1. Au démarrage, `hydrate()` télécharge toutes les tables dans `db.data`.
//   2. Les composants continuent de lire `db.data` de façon synchrone.
//   3. Chaque `db.persist()` programme un `pushAll()` (débounce) qui réécrit
//      dans Supabase les collections modifiées.
//
// DIFFÉRENCES DE NOMMAGE web <-> base (cf. core/models) :
//   - collections camelCase -> tables snake_case ;
//   - quelques champs renommés (sale_number, proforma_number, username...) ;
//   - les lignes enfants (sale_items, proforma_invoice_items) sont imbriquées
//     dans `items` côté web.
// ============================================================================
import { run, supabase } from './supabase';

/** Délai de regroupement des écritures (ms) avant envoi à Supabase. */
export const PUSH_DEBOUNCE_MS = 600;

// ---------------------------------------------------------------------------
// Description des correspondances collection web <-> table Supabase
//
//   table   : nom de la table PostgreSQL
//   rename  : { cléWeb: colonneSQL }  (appliqué dans les 2 sens)
//   items   : configuration d'une table enfant (lignes de document)
//   keep    : colonnes à ne jamais écrire côté SQL (ex. champs virtuels)
// ---------------------------------------------------------------------------
export const COLLECTIONS = [
  {
    // PROFIL uniquement : les comptes (email + mot de passe) vivent dans
    // auth.users (Supabase Auth) et sont crees/geres via les RPC
    // `admin_*` (voir web/src/api/authApi.js).
    //
    // `readOnly` : le navigateur ne doit JAMAIS ecrire cette table
    // directement. Elle est alimentee par le trigger PostgreSQL
    // `on_auth_user_changed` ; une ecriture PostgREST ecraserait le profil
    // ou tenterait d'ecrire un mot de passe (interdit par l'architecture).
    name: 'users',
    table: 'users',
    rename: { password: 'password_hash' },
    order: 'id',
    readOnly: true,
  },
  {
    name: 'customers',
    table: 'customers',
    order: 'id',
  },
  {
    name: 'suppliers',
    table: 'suppliers',
    order: 'id',
  },
  {
    name: 'products',
    table: 'products',
    order: 'id',
  },
  {
    name: 'stores',
    table: 'stores',
    order: 'id',
  },
  {
    name: 'sales',
    table: 'sales',
    rename: { number: 'sale_number' },
    order: 'id',
    items: {
      key: 'items',
      table: 'sale_items',
      foreignKey: 'sale_id',
      order: 'id',
    },
  },
  {
    name: 'proformas',
    table: 'proforma_invoices',
    rename: { number: 'proforma_number' },
    order: 'id',
    items: {
      key: 'items',
      table: 'proforma_invoice_items',
      foreignKey: 'proforma_id',
      order: 'id',
    },
  },
  {
    name: 'inventoryMovements',
    table: 'inventory_movements',
    order: 'id',
  },
  {
    name: 'treasuryAccounts',
    table: 'treasury_accounts',
    order: 'id',
  },
  {
    name: 'treasuryMovements',
    table: 'treasury_movements',
    order: 'id',
  },
  {
    name: 'monthlyClosures',
    table: 'monthly_closures',
    order: 'id',
  },
  {
    name: 'expenses',
    table: 'expenses',
    order: 'id',
  },
  {
    name: 'activityLogs',
    table: 'activity_logs',
    rename: { user: 'username', timestamp: 'created_at' },
    order: 'id',
  },
];

/** Retrouve la description d'une collection par son nom. */
export function getCollection(name) {
  return COLLECTIONS.find((c) => c.name === name) || null;
}

/** Colonnes virtuelles purement côté web (jamais envoyées à Supabase). */
const VIRTUAL_FIELDS = new Set([
  'items', 'customer', 'cashier', 'creator', 'product',
  'full_name', 'stockValue', 'profitPerUnit', 'isLowStock',
  'isOutOfStock', 'supplierName', 'accountName', 'balance',
]);

// ---------------------------------------------------------------------------
// Conversions de nommage / format
// ---------------------------------------------------------------------------

/** web -> SQL : renomme les clés et retire les champs virtuels. */
export function toSqlRow(collection, row) {
  const rename = collection.rename || {};
  const out = {};
  Object.entries(row || {}).forEach(([key, value]) => {
    if (VIRTUAL_FIELDS.has(key)) return;
    if (value === undefined) return;
    const col = rename[key] || key;
    out[col] = value;
  });
  return out;
}

/** SQL -> web : applique le renommage inverse. */
export function toWebRow(collection, row) {
  const rename = collection.rename || {};
  const inverse = {};
  Object.entries(rename).forEach(([webKey, col]) => {
    inverse[col] = webKey;
  });
  const out = {};
  Object.entries(row || {}).forEach(([col, value]) => {
    out[inverse[col] || col] = value;
  });
  return out;
}

/** Tri ascendant par identifiant (stable, comme les listes desktop). */
export function sortById(rows) {
  return rows.slice().sort((a, b) => (a.id || 0) - (b.id || 0));
}

/** Taille des paquets d'écriture (limite la taille des requêtes PostgREST). */
const CHUNK = 400;

// ---------------------------------------------------------------------------
// Index des identifiants DISTANTS connus, par collection
//
// Capturé lors de l'hydratation, il sert de référence aux suppressions : on ne
// supprime QUE des lignes réellement vues côté Supabase. Sans cet index, une
// table masquée par les RLS (lecture vide, ex. `users`/`expenses`/
// `activity_logs` pour un non-admin) serait intégralement effacée au premier
// enregistrement — la suppression portait auparavant sur tout ce qui n'était
// pas présent en mémoire.
// ---------------------------------------------------------------------------
const remoteIds = new Map();

/**
 * Mémorise les identifiants distants connus d'une collection.
 * Accepte un tableau ou un `Set` (voir pushCollection, qui travaille en Set).
 */
export function rememberRemoteIds(name, ids) {
  const list = ids instanceof Set ? Array.from(ids) : ids || [];
  remoteIds.set(name, new Set(list.filter((id) => id != null)));
}

/** Oublie les identifiants distants connus (déconnexion / réinitialisation). */
export function forgetRemoteIds(name = null) {
  if (name) remoteIds.delete(name);
  else remoteIds.clear();
}


// ---------------------------------------------------------------------------
// Lecture (Supabase -> mémoire)
// ---------------------------------------------------------------------------

/** Télécharge les lignes d'une table (paginé : PostgREST plafonne à 1000). */
async function fetchTable(table, order) {
  const PAGE = 1000;
  const all = [];
  for (let from = 0; ; from += PAGE) {
    const rows = await run(
      supabase.from(table).select('*').order(order || 'id').range(from, from + PAGE - 1)
    );
    if (!rows || !rows.length) break;
    all.push(...rows);
    if (rows.length < PAGE) break;
  }
  return all;
}

/** Télécharge une collection complète (avec ses lignes enfants si besoin). */
export async function fetchCollection(collection) {
  const rows = await fetchTable(collection.table, collection.order);
  const web = sortById(rows.map((r) => toWebRow(collection, r)));
  // Référence des lignes réellement présentes côté distant (voir pushCollection).
  rememberRemoteIds(collection.name, web.map((r) => r.id));

  if (!collection.items) return web;

  const { key, table, foreignKey, order } = collection.items;
  const children = await fetchTable(table, order);
  const grouped = new Map();
  children.forEach((child) => {
    const parentId = child[foreignKey];
    if (!grouped.has(parentId)) grouped.set(parentId, []);
    grouped.get(parentId).push(child);
  });
  web.forEach((row) => {
    row[key] = grouped.get(row.id) || [];
  });
  return web;
}

/** Télécharge TOUTES les collections et retourne l'objet db.data complet. */
export async function hydrateAll() {
  const data = {};
  for (const collection of COLLECTIONS) {
    data[collection.name] = await fetchCollection(collection);
  }
  return data;
}

// ---------------------------------------------------------------------------
// Écriture (mémoire -> Supabase)
// ---------------------------------------------------------------------------

/** Découpe un tableau en paquets (les requêtes restent courtes). */
function chunked(arr, size = CHUNK) {
  const out = [];
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
  return out;
}

/**
 * Écrit une collection : upsert des lignes présentes, suppression des lignes
 * disparues (celles dont l'id n'existe plus côté client) et resynchronisation
 * des lignes enfants (sale_items, proforma_invoice_items).
 */
export async function pushCollection(collection, rows) {
  // Collections en lecture seule (ex. `users`) : jamais ecrites par le
  // navigateur. Leur contenu est gere cote Supabase (triggers + RPC admin_*).
  if (collection.readOnly) return 0;

  const list = Array.isArray(rows) ? rows : [];
  const payload = list
    .filter((r) => r && r.id != null)
    .map((r) => toSqlRow(collection, r));

  // 1) Insertion / mise à jour
  for (const part of chunked(payload)) {
    const cleaned = part.map((r) => {
      const copy = { ...r };
      // Les lignes enfants sont gerées séparément.
      if (collection.items) delete copy[collection.items.key];
      return copy;
    });
    await run(supabase.from(collection.table).upsert(cleaned, { onConflict: 'id' }));
  }

  // 2) Suppression des lignes retirées localement
  //    Uniquement parmi les identifiants DÉJÀ CONNUS côté distant (vus à la
  //    dernière hydratation) : une collection jamais hydratée, ou masquée par
  //    les RLS, ne peut donc pas être vidée par erreur.
  const keptIds = new Set(payload.map((r) => r.id));
  const known = remoteIds.get(collection.name);
  if (known) {
    const stale = Array.from(known).filter((id) => !keptIds.has(id));
    for (const part of chunked(stale)) {
      await run(supabase.from(collection.table).delete().in('id', part));
    }
  }

  // 3) Lignes enfants : remplacement complet par parent modifié
  if (collection.items) {
    const { key, table, foreignKey } = collection.items;
    const childRows = [];
    list.forEach((row) => {
      if (row.id == null) return;
      (row[key] || []).forEach((child, index) => {
        const clean = toSqlRow({ rename: {} }, child);
        clean[foreignKey] = row.id;
        if (clean.id == null) clean.id = index + 1;
        childRows.push(clean);
      });
    });
    if (childRows.length) {
      for (const part of chunked(childRows)) {
        await run(supabase.from(table).upsert(part, { onConflict: 'id' }));
      }
    }
  }

  // Référence mise à jour : ce qui vient d'être écrit est désormais connu
  // côté distant (une ligne créée localement pourra être supprimée ensuite).
  rememberRemoteIds(collection.name, keptIds);

  return payload.length;
}

/** Écrit plusieurs collections (celles demandées, ou toutes). */
export async function pushAll(dbData, names = null) {
  const targets = names
    ? COLLECTIONS.filter((c) => names.includes(c.name))
    : COLLECTIONS;
  const report = {};
  for (const collection of targets) {
    const rows = dbData[collection.name];
    if (!Array.isArray(rows)) continue;
    report[collection.name] = await pushCollection(collection, rows);
  }
  return report;
}
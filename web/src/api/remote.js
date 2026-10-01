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

/**
 * `balance` est virtuel UNIQUEMENT pour les comptes de trésorerie (alias local
 * calculé de `current_balance`, cf. `treasuryApi.listAccounts`). Pour les
 * clients, `balance` est une vraie colonne SQL : c'est la dette du client.
 * Filtrer cette clé ici perdait silencieusement le solde crédité d'une vente à
 * crédit : le desktop/mobile ne le voyait jamais, et la prochaine hydratation
 * remettait la dette à zéro.
 */
function isVirtualField(collection, key) {
  if (key === 'balance') return collection?.name !== 'customers';
  return VIRTUAL_FIELDS.has(key);
}

/** web -> SQL : renomme les clés et retire les champs virtuels. */
export function toSqlRow(collection, row) {
  const rename = (collection && collection.rename) || {};
  const out = {};
  Object.entries(row || {}).forEach(([key, value]) => {
    if (isVirtualField(collection, key)) return;
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
 * Identifiants des LIGNES ENFANTS (sale_items, proforma_invoice_items) connus
 * côté distant : `Map<table, Map<idEnfant, idParent>>`.
 *
 * Sert à décider si une ligne enfant existe déjà en base (mise à jour) ou si
 * elle a été saisie dans le navigateur (insertion avec un id local négatif).
 */
const remoteChildIds = new Map();

/**
 * Mémorise les identifiants distants connus d'une collection.
 * Accepte un tableau ou un `Set` (voir pushCollection, qui travaille en Set).
 */
export function rememberRemoteIds(name, ids) {
  const list = ids instanceof Set ? Array.from(ids) : ids || [];
  remoteIds.set(name, new Set(list.filter((id) => id != null)));
}

/** Mémorise les identifiants des lignes enfants d'une table distante. */
export function rememberRemoteChildIds(table, children) {
  const map = new Map();
  (children || []).forEach((child) => {
    if (child && child.id != null) map.set(child.id, child.parentId ?? null);
  });
  remoteChildIds.set(table, map);
}

/** Oublie les identifiants distants connus (déconnexion / réinitialisation). */
export function forgetRemoteIds(name = null) {
  if (name) {
    remoteIds.delete(name);
    return;
  }
  remoteIds.clear();
  remoteChildIds.clear();
}

/**
 * Identifiant d'une ligne enfant créée dans le navigateur.
 *
 * Les tables enfants partagent une clé primaire GLOBALE (séquence PostgreSQL) :
 * réutiliser `index + 1` — comme le faisait le web — écrasait les lignes d'un
 * autre document (la 2e vente écrasait les lignes de la 1re). Un id local est
 * donc NÉGATIF (jamais produit par une séquence) et déterministe (parent +
 * position) : les envois successifs mettent à jour la même ligne au lieu d'en
 * créer des doublons, y compris après un rechargement de la page.
 */
export function localChildId(parentId, index) {
  return -(Number(parentId) * 1000 + (Number(index) || 0) + 1);
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
  // Référence des lignes enfants réellement présentes côté distant.
  rememberRemoteChildIds(
    table,
    children.map((child) => ({ id: child.id, parentId: child[foreignKey] }))
  );
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
  const knownChildren = remoteChildIds.get(collection.items?.table) || new Map();
  if (known) {
    const stale = Array.from(known).filter((id) => !keptIds.has(id));
    // Les lignes enfants sont supprimées d'abord : la clé étrangère est en
    // NO ACTION (sale_items.sale_id -> sales.id), donc supprimer un document
    // sans ses lignes échouerait.
    if (collection.items && stale.length) {
      const orphans = [];
      knownChildren.forEach((parentId, childId) => {
        if (stale.includes(parentId)) orphans.push(childId);
      });
      for (const part of chunked(orphans)) {
        await run(
          supabase.from(collection.items.table).delete().in('id', part)
        );
      }
    }
    for (const part of chunked(stale)) {
      await run(supabase.from(collection.table).delete().in('id', part));
    }
  }

  // 3) Lignes enfants : remplacement complet par parent modifié
  //
  // ATTENTION (clé primaire globale) : les tables `sale_items` /
  // `proforma_invoice_items` partagent UNE SEULE séquence d'identifiants. Un id
  // de ligne égal à sa position dans le document (comportement précédent)
  // réécrivait donc les lignes d'un autre document — la 2e vente écrasait les
  // lignes de la 1re. Les lignes créées dans le navigateur reçoivent désormais
  // un id local négatif déterministe (voir `localChildId`), mémorisé dans la
  // ligne : les envois suivants restent idempotents et aucune ligne distante
  // n'est écrasée.
  if (collection.items) {
    const { key, table, foreignKey } = collection.items;
    const childRows = [];
    const expectedChildIds = new Set();
    const parentIds = new Set();

    list.forEach((row) => {
      if (row.id == null) return;
      parentIds.add(row.id);
      (row[key] || []).forEach((child, index) => {
        const clean = toSqlRow({ rename: {} }, child);
        clean[foreignKey] = row.id;
        // La ligne existe-t-elle deja cote distant, ET appartient-elle bien a ce
        // document ? Un id local peut coincider avec celui d'une ligne d'un
        // AUTRE document (les ids sont globaux) : la conserver deplacerait et
        // ecraserait cette ligne.
        const remoteParent = clean.id != null && clean.id >= 0
          ? knownChildren.get(clean.id)
          : undefined;
        const isRemoteChild = remoteParent != null && Number(remoteParent) === Number(row.id);
        if (!isRemoteChild) {
          clean.id = localChildId(row.id, index);
          // Mémorisé localement : le prochain envoi mettra à jour cette ligne
          // au lieu d'en insérer une autre.
          if (child && typeof child === 'object') child.id = clean.id;
        }
        expectedChildIds.add(clean.id);
        childRows.push(clean);
      });
    });

    // Lignes saisies dans le navigateur puis retirées : elles n'existent que
    // côté web (id négatif) et ne sont plus attendues -> on les supprime.
    const removedLocalLines = [];
    knownChildren.forEach((parentId, childId) => {
      if (childId < 0 && parentIds.has(parentId) && !expectedChildIds.has(childId)) {
        removedLocalLines.push(childId);
      }
    });
    for (const part of chunked(removedLocalLines)) {
      await run(supabase.from(table).delete().in('id', part));
    }

    if (childRows.length) {
      for (const part of chunked(childRows)) {
        await run(supabase.from(table).upsert(part, { onConflict: 'id' }));
      }
      // Les lignes viennent d'être écrites : elles sont désormais connues
      // (nécessaire pour supprimer une ligne ajoutée puis retirée avant toute
      // nouvelle hydratation).
      childRows.forEach((row) => knownChildren.set(row.id, row[foreignKey]));
      remoteChildIds.set(table, knownChildren);
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
  const errors = [];
  for (const collection of targets) {
    const rows = dbData[collection.name];
    if (!Array.isArray(rows)) continue;
    try {
      report[collection.name] = await pushCollection(collection, rows);
    } catch (e) {
      // Une collection en échec (colonne absente, contrainte, RLS...) ne doit
      // pas empêcher la synchronisation des collections suivantes : elles
      // resteraient muettes sans aucun message. L'erreur est agrégée et
      // remontée à la fin pour que le bandeau de synchronisation l'affiche.
      report[collection.name] = 0;
      errors.push(`${collection.table} : ${e.message}`);
    }
  }
  if (errors.length) throw new Error(errors.join(' | '));
  return report;
}
// ============================================================================
// Korgo Pro Web — Couche d'accès aux données
//
// DEUX MODES, choisis automatiquement au démarrage :
//
//   1. MODE SUPABASE (recommandé) — si `web/.env` contient
//      VITE_SUPABASE_URL + VITE_SUPABASE_ANON_KEY :
//        - `hydrate()` télécharge toutes les tables dans `db.data` ;
//        - les composants lisent `db.data` de façon synchrone (inchangés) ;
//        - `db.persist()` réécrit dans Supabase les SEULES collections
//          réellement modifiées (comparaison avec le dernier état envoyé).
//
//   2. MODE LOCAL (repli) — sans configuration, ou si Supabase est
//      injoignable : les données vivent dans le localStorage du navigateur
//      (mode démo autonome, identique au comportement historique).
//
// Le localStorage sert aussi de cache hors-ligne : la dernière copie connue
// de la base y est conservée pour un affichage immédiat avant hydratation.
// ============================================================================
import {
  COLLECTIONS,
  PUSH_DEBOUNCE_MS,
  forgetRemoteIds,
  hydrateAll,
  pushAll,
} from './remote';
import { isSupabaseConfigured } from './supabase';

const DB_KEY = 'korgo_pro_db_v1';

// Valeurs par défaut : aucun utilisateur réel n'est requis, plusieurs comptes
// de démonstration existent avec des rôles différents.
const DEFAULT_DB = {
  users: [
    {
      id: 1,
      username: 'admin',
      password: 'admin',
      email: 'admin@korgo-pro.com',
      role: 'ADMIN',
      active: true,
      must_change_password: false,
      last_login: null,
    },
    {
      id: 2,
      username: 'gestionnaire',
      password: 'gestionnaire',
      email: 'gestion@korgo-pro.com',
      role: 'GESTIONNAIRE',
      active: true,
      must_change_password: false,
      last_login: null,
    },
    {
      id: 3,
      username: 'caissier',
      password: 'caissier',
      email: 'caisse@korgo-pro.com',
      role: 'CAISSIER',
      active: true,
      must_change_password: false,
      last_login: null,
    },
  ],
  customers: [],
  products: [],
  suppliers: [],
  stores: [],
  sales: [],
  proformas: [],
  treasuryAccounts: [],
  treasuryMovements: [],
  monthlyClosures: [],
  expenses: [],
  settings: {
    company_name: 'Korgo Pro',
    address: 'Cotonou, Bénin',
    phone: '+229 00 00 00 00',
    email: 'contact@korgo-pro.com',
    currency: 'FCFA',
    tax_rate: 20.0,
    invoice_prefix: 'FAC',
    proforma_prefix: 'PRO',
    invoice_footer: 'Merci de votre confiance.',
    payment_terms: '30',
    date_format: 'dd/MM/yyyy',
  },
};

/**
 * Magasin par défaut, avec la même règle que le desktop
 * (`core.store_manager.default_store`) : celui marqué `is_default`, sinon le
 * plus ancien (plus petit id).
 *
 * L'ORDRE EST IMPORTANT : les données historiques sans magasin (store_id NULL)
 * sont rattachées au magasin PAR DÉFAUT. Le desktop applique exactement la même
 * règle (`store_scope` inclut `store_id IS NULL` pour le magasin par défaut) :
 * les deux applications doivent désigner le même magasin, sinon le web
 * n'affiche pas les produits que le desktop montre.
 */
export function defaultStore(stores) {
  const list = Array.isArray(stores) ? stores : [];
  const flagged = list.find((s) => s.is_default === true);
  if (flagged) return flagged;
  return list.reduce((best, s) => (best === null || s.id < best.id ? s : best), null);
}

/**
 * Migration multi-magasins : garantit qu'il existe au moins un magasin.
 * Les données existantes sans magasin sont rattachées au magasin par défaut.
 *
 * Le magasin de secours (id 1) n'est utilisé QUE lorsque la base ne contient
 * aucun magasin (mode local, ou avant hydratation Supabase). Dès que les
 * magasins réels sont chargés, ils remplacent cette liste : l'interface ne doit
 * jamais continuer à afficher ce magasin de secours, sinon elle désigne un
 * magasin qui ne filtre aucun produit (cf. StoreContext, qui relit la liste à
 * chaque changement d'état de synchronisation).
 */
export function ensureStores(db) {
  if (!Array.isArray(db.stores) || !db.stores.length) {
    db.stores = [
      {
        id: 1,
        code: 'MAG-0001',
        name: 'Magasin principal',
        address: '',
        phone: '',
        active: true,
        created_at: new Date().toISOString(),
      },
    ];
  }
  if (!Array.isArray(db.stores) || !db.stores.some((s) => s.active !== false)) {
    db.stores[0].active = true;
  }
  // Rattache les entités orphelines au magasin par défaut.
  //
  // ATTENTION : n'ajouter ici que les collections dont la table possède
  // réellement une colonne `store_id`. `proforma_invoices` n'en a PAS : y
  // injecter un store_id fait échouer l'écriture PostgREST (42703 « column
  // proforma_invoices.store_id does not exist ») et bloque toute la
  // synchronisation du lot de collections concerné.
  const defaultStoreId = defaultStore(db.stores)?.id ?? null;
  ['products', 'sales', 'inventoryMovements'].forEach((key) => {
    if (Array.isArray(db[key])) {
      db[key].forEach((it) => {
        if (!it.store_id) it.store_id = defaultStoreId;
      });
    }
  });
  // Nettoyage des caches écrits par une version antérieure : les proformas y
  // portaient un `store_id` inexistant en base. On retire cette propriété
  // résiduelle, sinon l'écriture PostgREST de la collection échouerait (42703).
  if (Array.isArray(db.proformas)) {
    db.proformas.forEach((p) => {
      if (p && 'store_id' in p) delete p.store_id;
    });
  }
  return db;
}

/** Charge la base depuis localStorage (ou initialise avec les valeurs de démo). */
export function loadDB() {
  try {
    const raw = localStorage.getItem(DB_KEY);
    if (raw) {
      return ensureStores(JSON.parse(raw));
    }
  } catch (e) {
    console.error('Impossible de lire la base locale, reinitialisation.', e);
  }
  const db = mergeDefaults(DEFAULT_DB, {});
  ensureStores(db);
  saveDB(db);
  return db;
}

/** Persiste la base dans localStorage. */
export function saveDB(db) {
  try {
    localStorage.setItem(DB_KEY, JSON.stringify(db));
  } catch (e) {
    console.error('Impossible de sauvegarder la base locale.', e);
  }
}

/** Fusionne les valeurs par défaut avec une base existante (montée de version). */
function mergeDefaults(defaults, db) {
  const merged = { ...db };
  Object.keys(defaults).forEach((key) => {
    if (!Array.isArray(merged[key]) && !(key in merged)) {
      merged[key] = defaults[key];
    }
  });
  return merged;
}

/** Supprime toute la base locale (utilisé lors de la réinitialisation). */
export function resetDB() {
  localStorage.removeItem(DB_KEY);
  return loadDB();
}

/** Génère un identifiant numérique unique. */
export function nextId(items) {
  return items.reduce((max, it) => Math.max(max, it.id || 0), 0) + 1;
}

/** Formatte un montant selon la devise configurée. */
export function formatMoney(amount, currency = 'FCFA') {
  const value = Number(amount) || 0;
  return `${value.toLocaleString('fr-FR', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })} ${currency}`;
}

/** Formate une date ISO en format local. */
export function formatDate(iso, fmt = 'dd/MM/yyyy') {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const year = d.getFullYear();
  if (fmt === 'yyyy-MM-dd') return `${year}-${month}-${day}`;
  return `${day}/${month}/${year}`;
}

/** Génère un nouveau numéro de document (vente ou proforma). */
export function nextDocumentNumber(prefix, items) {
  const maxNum = items.reduce((max, it) => {
    const m = String(it.number || '').match(/(\d+)$/);
    return m ? Math.max(max, parseInt(m[1], 10)) : max;
  }, 0);
  return `${prefix}-${String(maxNum + 1).padStart(4, '0')}`;
}

/** Crée un export JSON sauvegardé (téléchargement) de la base locale. */
export function exportDatabase() {
  const payload = {
    app: 'korgo-pro-web',
    version: '0.1.0',
    exported_at: new Date().toISOString(),
    data: db.data,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: 'application/json',
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `korgo-pro-backup-${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  return payload;
}

/**
 * Importe une sauvegarde JSON de la base locale.
 * Accepte soit l'enveloppe { app, data } soit directement un objet de base.
 * Retourne true si l'import a réussi.
 */
export function importDatabase(jsonText) {
  let parsed;
  try {
    parsed = JSON.parse(jsonText);
  } catch (e) {
    throw new Error('Fichier JSON invalide.');
  }
  const base = parsed && parsed.data ? parsed.data : parsed;
  if (!base || typeof base !== 'object' || !Array.isArray(base.users)) {
    throw new Error("Structure non reconnue : l'objet doit contenir au moins users.");
  }
  db.data = ensureStores(mergeDefaults(DEFAULT_DB, base));
  saveDB(db.data);
  return true;
}

/** Statistiques d'occupation du localStorage par clé. */
export function storageStats() {
  const stats = [];
  let total = 0;
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      const size = new Blob([localStorage.getItem(key) || '']).size;
      if (key && key.startsWith('korgo_')) {
        stats.push({ key, size });
        total += size;
      }
    }
  } catch (e) {
    /* ignore */
  }
  return { keys: stats.sort((a, b) => b.size - a.size), total };
}

/** Convertit des octets en taille lisible. */
export function formatBytes(bytes) {
  if (!bytes) return '0 o';
  const units = ['o', 'Ko', 'Mo', 'Go'];
  let i = 0;
  let v = bytes;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(i === 0 ? 0 : 2)} ${units[i]}`;
}

// ---------------------------------------------------------------------------
// Synchronisation Supabase (cache mémoire -> base distante)
// ---------------------------------------------------------------------------

/** Dernier état envoyé à Supabase, par collection (sérialisé). */
const snapshots = {};

/** Nombre d'allers-retours réseau et état de la dernière synchronisation. */
export const syncState = {
  mode: isSupabaseConfigured() ? 'supabase' : 'local',
  hydrated: false,
  pending: 0,
  lastSyncAt: null,
  lastError: null,
};

/** Sérialise une collection pour détecter les modifications réelles. */
function snapshotOf(name, data) {
  try {
    return JSON.stringify(data[name] || []);
  } catch (e) {
    return null;
  }
}

/** Enregistre l'état courant comme référence (après hydratation ou envoi). */
export function takeSnapshots(data, names = null) {
  const targets = names || COLLECTIONS.map((c) => c.name);
  targets.forEach((name) => {
    snapshots[name] = snapshotOf(name, data);
  });
}

/** Retourne la liste des collections modifiées depuis le dernier envoi. */
export function changedCollections(data) {
  return COLLECTIONS.map((c) => c.name).filter(
    (name) => snapshotOf(name, data) !== snapshots[name]
  );
}

let pushTimer = null;
let pendingNames = new Set();
let pushChain = Promise.resolve();

/** Abonnés aux changements d'état de synchronisation (page Administration). */
const listeners = new Set();

/** S'abonne aux événements de synchronisation. Retourne un désabonnement. */
export function onSyncStatus(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function emitStatus() {
  const info = { ...syncState };
  listeners.forEach((fn) => {
    try {
      fn(info);
    } catch (e) {
      /* ignore */
    }
  });
}

/** Exécute les écritures en attente (séquentiellement, sans chevauchement). */
export function flush() {
  if (pushTimer) {
    clearTimeout(pushTimer);
    pushTimer = null;
  }
  const names = Array.from(pendingNames);
  pendingNames = new Set();
  if (!names.length || syncState.mode !== 'supabase') {
    return Promise.resolve({});
  }

  pushChain = pushChain
    .catch(() => {})
    .then(async () => {
      syncState.pending = names.length;
      emitStatus();
      const report = await pushAll(db.data, names);
      takeSnapshots(db.data, names);
      syncState.lastSyncAt = new Date().toISOString();
      syncState.lastError = null;
      syncState.pending = 0;
      emitStatus();
      return report;
    })
    .catch((e) => {
      syncState.lastError = e.message;
      // Les collections en échec restent en attente : le bandeau de
      // synchronisation les affiche et son bouton « Synchroniser » peut
      // relancer l'écriture.
      names.forEach((n) => pendingNames.add(n));
      syncState.pending = 0;
      emitStatus();
      console.error('Synchronisation Supabase impossible :', e.message);
      return {};
    });

  return pushChain;
}

/** Programme l'envoi des collections modifiées (regroupé). */
function schedulePush(names) {
  if (syncState.mode !== 'supabase') return;
  names.forEach((n) => pendingNames.add(n));
  emitStatus();
  if (pushTimer) clearTimeout(pushTimer);
  pushTimer = setTimeout(() => {
    pushTimer = null;
    flush();
  }, PUSH_DEBOUNCE_MS);
}

/**
 * Télécharge la base depuis Supabase et remplace `db.data`.
 * En cas d'échec, conserve les données locales (mode dégradé hors-ligne).
 * Retourne { ok, message, counts }.
 */
export async function hydrate() {
  if (syncState.mode !== 'supabase') {
    syncState.hydrated = true;
    emitStatus();
    return { ok: false, message: 'Mode local (Supabase non configuré)', counts: {} };
  }
  try {
    const remote = await hydrateAll();
    const merged = mergeDefaults(DEFAULT_DB, remote);
    db.data = ensureStores(merged);
    saveDB(db.data);
    takeSnapshots(db.data);
    syncState.hydrated = true;
    syncState.lastError = null;
    syncState.lastSyncAt = new Date().toISOString();
    emitStatus();
    const counts = {};
    Object.keys(remote).forEach((k) => {
      counts[k] = Array.isArray(remote[k]) ? remote[k].length : 0;
    });
    return { ok: true, message: 'Données chargées depuis Supabase', counts };
  } catch (e) {
    syncState.hydrated = true;
    syncState.lastError = e.message;
    emitStatus();
    return { ok: false, message: e.message, counts: {} };
  }
}

/** Force l'envoi immédiat de toutes les collections. */
export async function pushEverything() {
  takeSnapshots(db.data, []);
  const names = COLLECTIONS.map((c) => c.name);
  names.forEach((n) => pendingNames.add(n));
  return flush();
}

/**
 * Purge le cache local (mémoire + localStorage) — appelé à la déconnexion.
 *
 * Objectif : ne pas laisser dans le navigateur les données issues de la base
 * distante, et annuler les écritures en attente plutôt que de les envoyer.
 * Aucune requête d'écriture n'est émise vers Supabase.
 */
export function clearRemote() {
  if (pushTimer) {
    clearTimeout(pushTimer);
    pushTimer = null;
  }
  pendingNames = new Set();
  // Les identifiants distants connus ne doivent pas survivre à la session :
  // sinon une écriture ultérieure (nouvel utilisateur) pourrait supprimer des
  // lignes qu'il n'a jamais vues.
  forgetRemoteIds();
  db.data = ensureStores(mergeDefaults(DEFAULT_DB, {}));
  saveDB(db.data);
  // Référence = état courant, pour qu'aucune collection ne soit considérée
  // comme « modifiée » (donc envoyée) après la déconnexion.
  takeSnapshots(db.data);
  syncState.hydrated = false;
  syncState.pending = 0;
  syncState.lastError = null;
  syncState.lastSyncAt = null;
  emitStatus();
  return db.data;
}

// ---------------------------------------------------------------------------
// Objet global de la base, accessible de manière synchrone par les services.
// ---------------------------------------------------------------------------
export const db = {
  data: loadDB(),
  /** 'supabase' ou 'local'. */
  get mode() {
    return syncState.mode;
  },
  /**
   * Enregistre localement (cache hors-ligne) puis programme l'écriture
   * Supabase des collections réellement modifiées.
   */
  persist() {
    saveDB(this.data);
    schedulePush(changedCollections(this.data));
  },
  hydrate,
  flush,
  pushEverything,
  clearRemote,
};
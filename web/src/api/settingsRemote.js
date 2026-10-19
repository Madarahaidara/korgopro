// ============================================================================
// Korgo Pro Web — Passerelle Supabase pour les paramètres entreprise.
//
// Les paramètres ne vivent pas dans une collection « tableau » (contrairement
// aux produits, ventes… synchronisés par remote.js) : c'est un dictionnaire
// unique. Ils ont donc leur propre passerelle, alignée sur la table singleton
// `app_settings` (ligne id=1, colonne JSONB `data`) partagée avec le desktop
// (voir core/models/app_setting.py et supabase_app_settings.sql).
//
// STRATÉGIE : même principe que le reste du web — cache mémoire synchrone
// (`db.data.settings`) + source de vérité distante :
//   * `hydrateSettings()` (au login) fusionne la ligne distante dans le cache ;
//   * `saveSettings()` met à jour le cache puis pousse vers Supabase.
//
// REPLI : sans configuration Supabase (mode démo localStorage) ou si la table
// est absente, toute opération distante est ignorée et le localStorage du
// navigateur fait office de persistance, comme avant.
// ============================================================================
import { supabase, run, isSupabaseConfigured } from './supabase';

// ----------------------------------------------------------------------------
// SÉPARATION DES CLÉS : desktop et web n'utilisent pas toujours les mêmes
// noms. Pour une vraie source de vérité partagée, la couche ci-dessous
// normalise vers les clés CANONIQUES (celles du desktop, stockées dans le
// JSONB) : le web écrit/relit donc exactement ce que le desktop écrit/relit.
//   web address/phone/email/ifu/rccm/bp
//     <-> canonical company_address/company_phone/company_email/
//        company_ifu/company_rccm/company_po_box
// Les autres clés sont communes aux deux plateformes.
// ----------------------------------------------------------------------------

/** Clés de paramètres reconnues/écrites par le web. */
export const WEB_SETTINGS_KEYS = [
  'company_name',
  'address',
  'phone',
  'email',
  'currency',
  'tax_rate',
  'invoice_prefix',
  'proforma_prefix',
  'invoice_footer',
  'payment_terms',
  'date_format',
  'ifu',
  'rccm',
  'bp',
];

/** Clés identiques des deux côtés (pas de traduction nécessaire). */
const SHARED_KEYS = new Set([
  'company_name', 'currency', 'tax_rate', 'invoice_prefix',
  'invoice_footer', 'payment_terms', 'date_format',
]);

/** web (local) -> canonical (Supabase). Les clés partagées s'appliquent telles quelles. */
const KEY_TO_CANONICAL = {
  address: 'company_address',
  phone: 'company_phone',
  email: 'company_email',
  ifu: 'company_ifu',
  rccm: 'company_rccm',
  bp: 'company_po_box',
};
/** canonical (Supabase) -> web (local), inverse exact de KEY_TO_CANONICAL. */
const CANONICAL_TO_KEY = {
  company_address: 'address',
  company_phone: 'phone',
  company_email: 'email',
  company_ifu: 'ifu',
  company_rccm: 'rccm',
  company_po_box: 'bp',
};

/** Convertit un patch web en clés canoniques (pour l'écriture serveur). */
function webToCanonical(patch) {
  const out = {};
  Object.entries(patch || {}).forEach(([k, v]) => {
    const canon = KEY_TO_CANONICAL[k] || k;
    out[canon] = v;
  });
  return out;
}

/**
 * Convertit le dictionnaire canonique distant en objet façonné pour le cache
 * web : clés partagées en clair, champs renommés sous leur alias web, et les
 * clés propres au desktop (logo, magasin actif, thème…) écartées pour ne pas
 * polluer le cache localStorage du navigateur.
 */
export function canonicalToWeb(canonical) {
  const out = {};
  Object.entries(canonical || {}).forEach(([canon, v]) => {
    if (SHARED_KEYS.has(canon)) {
      out[canon] = v;
    } else if (CANONICAL_TO_KEY[canon]) {
      out[CANONICAL_TO_KEY[canon]] = v;
    }
    // sinon : clé desktop-only -> ignorée côté web
  });
  return out;
}

/** Ne conserve que les clés propres au web (ignore celles venues du desktop). */
function webOwnedPatch(patch) {
  const out = {};
  WEB_SETTINGS_KEYS.forEach((k) => {
    if (patch && Object.prototype.hasOwnProperty.call(patch, k)) {
      out[k] = patch[k];
    }
  });
  return out;
}

/**
 * Lit la ligne de paramètres distante.
 * Retourne le dictionnaire FAÇONNÉ POUR LE WEB (alias appliqués) ou `null` si
 * Supabase n'est pas configuré, la table absente, ou le réseau injoignable.
 */
export async function fetchRemoteSettings() {
  if (!isSupabaseConfigured() || !supabase) return null;
  try {
    const row = await run(
      supabase.from('app_settings').select('data').eq('id', 1).maybeSingle()
    );
    if (!row || !row.data || typeof row.data !== 'object') return null;
    return canonicalToWeb(row.data);
  } catch (e) {
    // Table pas encore créée (migration non jouée) ou RLS : on reste en local.
    console.warn('[settings] lecture Supabase impossible :', e.message);
    return null;
  }
}

/**
 * Fusionne les clés fournies dans la ligne distante (merge superficiel via la
 * RPC `app_merge_settings`, atomique côté serveur). Ne pousse que les clés
 * propres au web, traduites en clés canoniques. Retourne le dictionnaire
 * distant résultant, ou `null` en cas d'échec (le cache local a malgré tout
 * été mis à jour par l'appelant).
 */
export async function pushRemoteSettings(patch) {
  if (!isSupabaseConfigured() || !supabase) return null;
  const owned = webOwnedPatch(patch);
  if (!Object.keys(owned).length) return null;
  const canonical = webToCanonical(owned);
  try {
    return await run(
      supabase.rpc('app_merge_settings', { p_patch: canonical })
    );
  } catch (e) {
    console.warn('[settings] écriture Supabase impossible :', e.message);
    return null;
  }
}

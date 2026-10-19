// ============================================================================
// Korgo Pro Mobile — Passerelle Supabase pour les paramètres entreprise.
//
// Miroir MOBILE de web/src/api/settingsRemote.js, en LECTURE SEULE : le
// mobile affiche les paramètres partagés (nom, devise, TVA, mentions de
// facture…) mais ne les modifie jamais (réglage réservé au desktop/web,
// cf. saveSettings dans settingsApi.js).
//
// Source de vérité : table singleton `app_settings` (ligne id=1, colonne
// JSONB `data`) — même table que desktop (core/models/app_setting.py) et
// web (web/src/api/settingsRemote.js). Les clés stockées sont CANONIQUES
// (vocabulaire desktop) ; le mobile applique les mêmes alias que le web.
//
// REPLI : sans mobile/.env (Supabase non configuré) ou si la table est
// absente / RLS / réseau, `fetchRemoteSettings()` retourne null et les
// valeurs par défaut + env servent, comme avant.
// ============================================================================
import { supabase, run } from './supabase';
import { isConfigured } from '../config';

/**
 * Clés canoniques reprises telles quelles (même nom de part et d'autre).
 * `proforma_prefix` est partagé en lecture (affiché par la page Réglages).
 */
const SHARED_KEYS = new Set([
  'company_name', 'currency', 'tax_rate', 'invoice_prefix',
  'proforma_prefix', 'invoice_footer', 'payment_terms', 'date_format',
]);

/** canonical (Supabase) -> façade mobile, miroir exact du web. */
const CANONICAL_TO_KEY = {
  company_address: 'address',
  company_phone: 'phone',
  company_email: 'email',
  company_ifu: 'ifu',
  company_rccm: 'rccm',
  company_po_box: 'bp',
};

const KEY_TO_CANONICAL = Object.fromEntries(
  Object.entries(CANONICAL_TO_KEY).map(([canonical, key]) => [key, canonical])
);

/**
 * Convertit le dictionnaire canonique (JSONB `data`) en objet façonné pour
 * le mobile : clés partagées en clair + champs renommés sous leur alias ;
 * les clés propres au desktop (logo, magasin actif, thème…) sont écartées.
 */
export function canonicalToMobile(canonical) {
  const out = {};
  Object.entries(canonical || {}).forEach(([canon, v]) => {
    if (SHARED_KEYS.has(canon)) {
      out[canon] = v;
    } else if (CANONICAL_TO_KEY[canon]) {
      out[CANONICAL_TO_KEY[canon]] = v;
    }
  });
  return out;
}

/**
 * Lit la ligne de paramètres distante (PostgREST, session authentifiée).
 * Retourne la façade mobile ou `null` (non configuré, table absente, RLS,
 * réseau) — l'appelant garde alors les valeurs par défaut/env.
 */
export async function fetchRemoteSettings() {
  if (!isConfigured() || !supabase) return null;
  try {
    const row = await run(
      supabase.from('app_settings').select('data').eq('id', 1).maybeSingle()
    );
    if (!row || !row.data || typeof row.data !== 'object') return null;
    return canonicalToMobile(row.data);
  } catch (e) {
    // Table pas encore créée (migration non jouée) ou RLS : on reste en local.
    console.warn('[settings] lecture Supabase impossible :', e.message);
    return null;
  }
}

export async function pushRemoteSettings(patch) {
  if (!isConfigured() || !supabase) return null;
  const canonical = {};
  Object.entries(patch || {}).forEach(([key, value]) => {
    const target = SHARED_KEYS.has(key) ? key : KEY_TO_CANONICAL[key];
    if (target) canonical[target] = value;
  });
  if (!Object.keys(canonical).length) return null;
  return run(supabase.rpc('app_merge_settings', { p_patch: canonical }));
}

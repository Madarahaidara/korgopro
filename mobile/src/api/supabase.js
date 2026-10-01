// ============================================================================
// Client Supabase du mobile (PostgREST + Auth).
//
// La version mobile lit la MÊME base que le desktop et le web :
//   * DESKTOP : SQLAlchemy / psycopg2 (port 5432, réseau local ou Supabase) ;
//   * WEB     : navigateur -> PostgREST (clé publique) ;
//   * MOBILE  : application -> PostgREST (clé publique), session persistée
//               dans AsyncStorage.
//
// Conséquence importante : le rôle `authenticated` et les politiques RLS
// s'appliquent. Les écritures opérationnelles passent par les RPC `app_*`
// (voir supabase_mobile_rpc.sql) car RLS les réserve aux administrateurs.
// ============================================================================
import 'react-native-url-polyfill/auto';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { createClient } from '@supabase/supabase-js';
import { config, isConfigured } from '../config';

/** Client Supabase, ou null si `.env` n'est pas renseigné. */
export const supabase = isConfigured()
  ? createClient(config.supabaseUrl, config.supabaseAnonKey, {
      db: { schema: config.supabaseSchema },
      auth: {
        storage: AsyncStorage,
        storageKey: 'korgo_pro_mobile_auth',
        persistSession: true,
        autoRefreshToken: true,
        // Une app native ne reçoit pas de session dans l'URL (contrairement
        // au navigateur) : on désactive explicitement l'analyse d'URL.
        detectSessionInUrl: false,
      },
      global: { headers: { 'x-application-name': 'korgo-pro-mobile' } },
    })
  : null;

/**
 * Traduit une erreur Supabase/PostgREST en message affichable en français.
 * Les refus de droits (42501) sont fréquents et doivent être compréhensibles.
 */
export function friendlyError(error) {
  const raw = error?.message || String(error || 'Erreur inconnue');
  const code = error?.code || '';

  if (code === '42501' || /row-level security|permission denied|non autorise/i.test(raw)) {
    return `Action refusée par le serveur (droits insuffisants).\n${raw}`;
  }
  // PostgREST : RPC inconnue de son cache de schéma (code PGRST202). Sans
  // traduction, le message brut (« Could not find the function
  // public.app_create_sale(...) in the schema cache ») n'indique pas quoi faire.
  if (code === 'PGRST202' || /Could not find the function/i.test(raw)) {
    return "API d'écriture mobile absente du serveur (fonction app_* non "
      + 'installée).\nPrévenez l\'administrateur : le script '
      + 'supabase_mobile_rpc.sql doit être appliqué à la base '
      + '(python _apply_mobile_rpc.py), puis le cache PostgREST rechargé.';
  }
  // PGRST203 : plusieurs surcharges peuvent correspondre (paramètres par
  // défaut) — la fonction existe mais le serveur ne sait pas laquelle appeler.
  if (code === 'PGRST203') {
    return 'Fonction serveur ambiguë (plusieurs surcharges).\nPrévenez '
      + 'l\'administrateur : supabase_mobile_rpc.sql doit être réappliqué.';
  }
  if (/JWT|jwt|token is expired|invalid claim/i.test(raw)) {
    return 'Session expirée. Reconnectez-vous.';
  }
  if (/Network request failed|Failed to fetch|fetch failed|ENOTFOUND|timeout|timed out/i.test(raw)) {
    return "Réseau indisponible. Vérifiez la connexion puis réessayez : rien n'a été enregistré.";
  }
  return raw;
}

/** Exécute une requête PostgREST en normalisant l'erreur. */
export async function run(query) {
  const { data, error } = await query;
  if (error) {
    const err = new Error(friendlyError(error));
    err.code = error.code;
    err.details = error.details;
    err.hint = error.hint;
    err.cause = error;
    throw err;
  }
  return data;
}

/** Erreur de session/permission explicite, levée par `requireClient()`. */
export class NotConfiguredError extends Error {}

/** Retourne le client ou lève une erreur lisible si `.env` est absent. */
export function requireClient() {
  if (!supabase) {
    throw new NotConfiguredError(
      'Supabase non configuré : renseignez mobile/.env (voir mobile/.env.example).'
    );
  }
  return supabase;
}

/** Nombre d'allers-retours réseau effectués (miroir web getRequestCount). */
let requestCount = 0;
export function getRequestCount() {
  return requestCount;
}

/** Incrémente le compteur (appelé par les façades api/*). */
export function countRequest() {
  requestCount += 1;
  return requestCount;
}

/** Référence du projet (sous-domaine de l'URL) — miroir web. */
export function supabaseProjectRef() {
  const m = String(config.supabaseUrl || '').match(/^https?:\/\/([^.]+)\./);
  return m ? m[1] : '';
}

/**
 * Test de connectivité : renvoie la latence (miroir web ping()).
 * Lecture d'une table légère pour valider clé + RLS.
 */
export async function ping() {
  if (!supabase) {
    return { ok: false, latency: 0, message: 'Supabase non configuré' };
  }
  const start = Date.now();
  try {
    requestCount += 1;
    await run(supabase.from('stores').select('id').limit(1));
    return { ok: true, latency: Date.now() - start, message: 'Connexion Supabase opérationnelle' };
  } catch (e) {
    return { ok: false, latency: Date.now() - start, message: e.message };
  }
}

// ============================================================================
// Korgo Pro Web — Client Supabase (PostgREST + Auth)
//
// La version web lit/écrit la MÊME base PostgreSQL/Supabase que l'app desktop.
// Contrairement au desktop (SQLAlchemy, port 5432), le navigateur passe par
// l'API REST PostgREST de Supabase : il faut donc une URL de projet et une clé
// publique (publishable / anon).
//
// Configuration : créez `web/.env` à partir de `web/.env.example` :
//
//   VITE_SUPABASE_URL=https://<REF>.supabase.co
//   VITE_SUPABASE_ANON_KEY=<clé publique>
//   VITE_SUPABASE_SCHEMA=public
//
// Sans configuration, l'application retombe automatiquement sur le mode
// localStorage (mode démo autonome) — aucune erreur bloquante.
// ============================================================================
import { createClient } from '@supabase/supabase-js';

const URL = (import.meta.env.VITE_SUPABASE_URL || '').trim();
// Supabase a renommé « anon key » en « publishable key » : on accepte les deux.
const KEY = (
  import.meta.env.VITE_SUPABASE_ANON_KEY ||
  import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY ||
  ''
).trim();
const SCHEMA = (import.meta.env.VITE_SUPABASE_SCHEMA || 'public').trim();

/** Vrai si l'URL et la clé Supabase sont renseignées dans `web/.env`. */
export function isSupabaseConfigured() {
  return /^https?:\/\/.+/.test(URL) && KEY.length > 20;
}

/** Origine du projet Supabase (utile pour les messages d'erreur). */
export function supabaseProjectUrl() {
  return URL;
}

/** Référence du projet (sous-domaine de l'URL). */
export function supabaseProjectRef() {
  const m = URL.match(/^https?:\/\/([^.]+)\./);
  return m ? m[1] : '';
}

export const supabase = isSupabaseConfigured()
  ? createClient(URL, KEY, {
      db: { schema: SCHEMA },
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        storageKey: 'korgo_pro_supabase_auth',
      },
      global: {
        headers: { 'x-application-name': 'korgo-pro-web' },
      },
    })
  : null;

/** Nombre d'allers-retours réseau effectués (diagnostic page Administration). */
let requestCount = 0;
export function getRequestCount() {
  return requestCount;
}

/**
 * Exécute une requête PostgREST en comptant les appels et en normalisant
 * les erreurs (Supabase renvoie un objet { message, details, hint, code }).
 */
export async function run(query) {
  requestCount += 1;
  const { data, error } = await query;
  if (error) {
    const err = new Error(error.message || 'Erreur Supabase');
    err.code = error.code;
    err.details = error.details;
    err.hint = error.hint;
    throw err;
  }
  return data;
}

/** Test de connectivité : renvoie la latence et la version PostgreSQL. */
export async function ping() {
  if (!supabase) {
    return { ok: false, latency: 0, message: 'Supabase non configuré' };
  }
  const start = performance.now();
  try {
    // Lecture d'une table légère pour valider la clé et les policies RLS.
    await run(supabase.from('stores').select('id').limit(1));
    return {
      ok: true,
      latency: Math.round(performance.now() - start),
      message: 'Connexion Supabase opérationnelle',
    };
  } catch (e) {
    return {
      ok: false,
      latency: Math.round(performance.now() - start),
      message: e.message,
    };
  }
}
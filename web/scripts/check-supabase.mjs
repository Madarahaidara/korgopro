import { createClient } from '@supabase/supabase-js';
import { loadEnv } from 'vite';

// Diagnostic en lecture seule : aucune insertion, modification ou suppression.
const env = loadEnv('development', process.cwd(), 'VITE_');
const url = (env.VITE_SUPABASE_URL || '').trim();
const key = (env.VITE_SUPABASE_ANON_KEY || env.VITE_SUPABASE_PUBLISHABLE_KEY || '').trim();
const schema = (env.VITE_SUPABASE_SCHEMA || 'public').trim();

function reportError(step, error) {
  console.error(`${step}: ECHEC`, {
    status: error?.status ?? null,
    code: error?.code ?? null,
    message: error?.message || String(error),
  });
}

async function main() {
  if (!url || !key) {
    throw new Error('VITE_SUPABASE_URL et une cle publique Supabase sont requis.');
  }
  console.log('Configuration:', {
    urlPresente: Boolean(url),
    clePresente: Boolean(key),
    cleDeRemplacement: /A_REMPLACER|<.*>/i.test(key),
    schema,
  });

  const client = createClient(url, key, {
    db: { schema },
    auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
    global: {
      fetch: (input, init = {}) => fetch(input, { ...init, signal: AbortSignal.timeout(15000) }),
    },
  });

  // getSession() seul ne valide pas la cle : sans stockage il retourne null.
  const response = await fetch(`${url.replace(/\/$/, '')}/auth/v1/settings`, {
    headers: { apikey: key },
    signal: AbortSignal.timeout(15000),
  });
  console.log('Supabase Auth /settings: HTTP', response.status);
  if (!response.ok) process.exitCode = 1;

  const { data, error } = await client.from('stores').select('id').limit(1);
  if (error) {
    if (error.code === '42501') {
      // Comportement ATTENDU : le rôle `anon` (sans session) n'a aucun droit sur
      // les tables (cf. supabase_rls_policies.sql). L'app web ne lit les données
      // qu'APRÈS le signInWithPassword, avec le rôle `authenticated`.
      console.log('Lecture stores: refus attendu en rôle anon (42501).');
      console.log('  -> normal : la connexion web se fait après authentification.');
      console.log('  -> pour tester un compte réel, se connecter dans l\'application.');
    } else {
      reportError('Lecture stores', error);
      process.exitCode = 1;
    }
  } else {
    console.log('Lecture stores: OK', { lignesVisibles: data.length });
    console.log('Une liste vide ne prouve pas un acces authentifie (RLS).');
  }
}

main().catch((error) => {
  reportError('Diagnostic', error);
  process.exitCode = 1;
});

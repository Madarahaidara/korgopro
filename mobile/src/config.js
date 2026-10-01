// ============================================================================
// Configuration de l'application mobile.
//
// Toutes les valeurs viennent du fichier `mobile/.env` (préfixe EXPO_PUBLIC_
// obligatoire pour être embarquées dans le bundle). Voir `.env.example`.
//
// Aucune valeur secrète ici : seule la clé publique Supabase est utilisée, et
// ce sont les politiques RLS + les RPC `app_*` qui décident des droits.
// ============================================================================

function readEnv(value, fallback = '') {
  const raw = typeof value === 'string' ? value.trim() : '';
  return raw || fallback;
}

export const config = {
  supabaseUrl: readEnv(process.env.EXPO_PUBLIC_SUPABASE_URL),
  supabaseAnonKey: readEnv(
    process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ||
      process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY
  ),
  supabaseSchema: readEnv(process.env.EXPO_PUBLIC_SUPABASE_SCHEMA, 'public'),
  currency: readEnv(process.env.EXPO_PUBLIC_CURRENCY, 'FCFA'),
  taxRate: Number(readEnv(process.env.EXPO_PUBLIC_TAX_RATE, '0')) || 0,
};

/** Vrai si `.env` contient une URL et une clé publique exploitables. */
export function isConfigured() {
  return /^https?:\/\/.+/.test(config.supabaseUrl) && config.supabaseAnonKey.length > 20;
}

/** Message d'aide affiché quand `.env` n'est pas renseigné. */
export const MISSING_ENV_MESSAGE =
  "Supabase n'est pas configuré.\n\n" +
  'Créez mobile/.env à partir de mobile/.env.example puis renseignez :\n' +
  '  EXPO_PUBLIC_SUPABASE_URL\n' +
  '  EXPO_PUBLIC_SUPABASE_ANON_KEY';

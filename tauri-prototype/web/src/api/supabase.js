import { createClient } from '@supabase/supabase-js';

const url = (import.meta.env.VITE_SUPABASE_URL || '').trim();
const key = (
  import.meta.env.VITE_SUPABASE_ANON_KEY ||
  import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY ||
  ''
).trim();
const schema = (import.meta.env.VITE_SUPABASE_SCHEMA || 'public').trim();

export const isSupabaseConfigured =
  /^https?:\/\/.+/.test(url) && key.length > 20;

export const supabase = isSupabaseConfigured
  ? createClient(url, key, {
      db: { schema },
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        storageKey: 'korgo_pro_tauri_auth',
      },
      global: {
        headers: { 'x-application-name': 'korgo-pro-tauri' },
      },
    })
  : null;

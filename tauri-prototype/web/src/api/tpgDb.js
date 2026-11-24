// === Client Tauri pour le prototype React + Tauri ===
//
// Remplace l'appel direct à Supabase JS par des appels au backend Rust
// (Tauri). Le bridge est disponible via `window.__TAURI_INTERNALS__` quand
// l'application est lancée avec `tauri dev` / `tauri build`.
//
// Si le bridge n'est pas présent (mode Vite / navigateur), on utilise le
// mode "frontend local" (données fictives) pour que l'interface reste
// navigable pendant le développement.

const tauri = () => {
  if (typeof window === 'undefined') return null;
  return window.__TAURI_INTERNALS__;
};

async function invoke(cmd, args = {}) {
  const t = tauri();
  if (!t) {
    throw new Error('Tauri bridge non disponible (mode Vite).');
  }
  return t.invoke(cmd, args);
}

// ── db (tables / requêtes / insertions) ──────────────────────────────

export async function listTables() {
  return invoke('db_list_tables');
}

export async function queryTable(table, whereFilter = {}) {
  return invoke('db_query', { table, where: whereFilter });
}

export async function insertIntoTable(table, data) {
  return invoke('db_insert', { table, data });
}

// ── auth (login / is_admin) ──────────────────────────────────────────

export async function login(email, password) {
  return invoke('auth_login', { email, password });
}

export async function isAdmin(email) {
  return invoke('auth_is_admin', { email });
}

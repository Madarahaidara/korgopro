// ============================================================================
// Service d'authentification et de gestion des comptes (web).
//
// ARCHITECTURE : Supabase Auth est la SOURCE DE VERITE UNIQUE.
//   - la CONNEXION passe par Supabase Auth (remoteAuth.js, signInWithPassword) ;
//   - la CREATION / MODIFICATION / DESACTIVATION d'un compte passe par les RPC
//     PostgreSQL `admin_*` (SECURITY DEFINER, reservees aux administrateurs) ;
//   - public.users n'est qu'un PROFIL alimente par le trigger
//     `on_auth_user_changed` : le navigateur ne l'ecrit jamais directement.
//
// Pourquoi des RPC et non l'API Admin Supabase Auth ? L'API Admin exige la
// cle `service_role`, qui ne doit JAMAIS etre exposee dans un navigateur.
// Les RPC conservent la creation cote Supabase sans exposer de secret.
//
// Sans Supabase configure, l'application reste en mode demo (localStorage).
// ============================================================================
import { db, hydrate } from './db';
import { supabase } from './supabase';
import { authenticateRemote } from './remoteAuth';

/** Erreur metier : message directement affichable a l'utilisateur. */
export class UserAdminError extends Error {}

/** Email normalise (identifiant de connexion Supabase Auth). */
function normalizeEmail(email) {
  return String(email || '').trim().toLowerCase();
}

/** Exécute une RPC `admin_*` et lève une erreur si elle refuse l'opération. */
async function callAdminRpc(fn, params) {
  if (!supabase) {
    throw new UserAdminError('Supabase non configuré.');
  }
  const { data, error } = await supabase.rpc(fn, params);
  if (error) {
    // PostgREST remonte l'erreur brute (ex. « Reserve aux administrateurs »).
    throw new UserAdminError(error.message || 'Opération refusée par Supabase.');
  }
  if (data && typeof data === 'object' && data.ok === false) {
    throw new UserAdminError(data.message || 'Opération refusée par Supabase.');
  }
  return data;
}

/**
 * Authentifie un utilisateur.
 *
 * En mode Supabase, `username` accepte un email OU un nom d'utilisateur : le
 * nom est d'abord resolu en email via le profil public.users.
 */
export async function login(username, password) {
  if (db.mode === 'supabase') {
    const ident = String(username || '').trim();
    let email = ident;

    // Supabase Auth s'authentifie par email : on resout le nom d'utilisateur.
    if (!ident.includes('@')) {
      const profile = await supabase
        .from('users')
        .select('email')
        .ilike('username', ident)
        .maybeSingle();
      if (profile.error || !profile.data?.email) {
        throw new UserAdminError(
          "Nom d'utilisateur inconnu. Utilisez votre email ou verifiez votre nom d'utilisateur."
        );
      }
      email = profile.data.email;
    }
    return authenticateRemote(supabase, email, password);
  }

  const user = db.data.users.find(
    (u) =>
      u.username.toLowerCase() === String(username).toLowerCase() &&
      u.password === password
  );
  if (!user || !user.active) {
    return null;
  }
  user.last_login = new Date().toISOString();
  db.persist();
  return toSafeUser(user);
}
/** Retourne un utilisateur sans le mot de passe, par son identifiant. */
export function getUserById(id) {
  const user = db.data.users.find((u) => u.id === Number(id));
  return user ? toSafeUser(user) : null;
}

/**
 * Retire tout secret avant de sortir du service.
 *
 * `password` porte le hash bcrypt hydrate depuis password_hash : il ne doit
 * jamais atteindre l'interface.
 */
export function toSafeUser(user) {
  // eslint-disable-next-line no-unused-vars
  const { password, password_hash, ...safe } = user;
  return safe;
}

/** Vérifie qu'un mot de passe correspond à l'utilisateur (actions sensibles). */
export async function verifyPassword(username, password) {
  if (db.mode === 'supabase') {
    try {
      await login(username, password);
      return true;
    } catch (e) {
      return false;
    }
  }
  const user = db.data.users.find((u) => u.username === username);
  return !!user && user.password === password;
}

/** Liste tous les utilisateurs (vue admin), sans aucun secret. */
export function listUsers() {
  return db.data.users.map(toSafeUser);
}

/** Recharge les profils depuis Supabase (les RPC modifient le profil). */
async function refreshFromSupabase() {
  const result = await hydrate();
  if (!result.ok) {
    throw new UserAdminError(result.message || 'Rafraîchissement impossible.');
  }
}

/**
 * Crée ou met à jour un utilisateur.
 *
 * En mode Supabase, l'écriture se fait dans auth.users via les RPC admin : le
 * mot de passe et l'email sont gérés par Supabase Auth, et le profil
 * public.users suit automatiquement (trigger PostgreSQL).
 */
export async function saveUser(user) {
  if (db.mode !== 'supabase') {
    return saveUserLocal(user);
  }

  const email = normalizeEmail(user.email);
  if (!email) {
    throw new UserAdminError(
      "L'email est obligatoire : Supabase Auth l'utilise comme identifiant de connexion."
    );
  }

  if (user.id) {
    // Le formulaire a pu changer l'email : on localise la ligne par son email
    // ACTUEL (encore en base) pour retrouver le compte Supabase Auth.
    const current = db.data.users.find((u) => u.id === Number(user.id));
    const currentEmail = normalizeEmail(current?.email);
    if (!currentEmail) {
      throw new UserAdminError('Utilisateur introuvable dans Supabase.');
    }

    await callAdminRpc('admin_update_user_profile', {
      p_email: currentEmail,
      p_username: user.username || null,
      p_role: user.role || null,
      p_active: null,
      p_new_email: email !== currentEmail ? email : null,
    });

    if (user.password) {
      await callAdminRpc('admin_set_user_password', {
        p_email: email,
        p_password: user.password,
        p_must_change_password: false,
      });
    }

    await refreshFromSupabase();
    return { ...user, id: Number(user.id), email };
  }

  if (!user.password) {
    throw new UserAdminError('Mot de passe requis pour un nouvel utilisateur.');
  }

  const created = await callAdminRpc('admin_create_user', {
    p_email: email,
    p_password: user.password,
    p_username: user.username || null,
    p_role: user.role || 'CAISSIER',
    p_active: user.active !== false,
    p_must_change_password: true,
  });

  await refreshFromSupabase();
  return { ...user, id: created?.user_id ?? null, email };
}

/** Active / désactive un utilisateur (bannissement Supabase Auth). */
export async function toggleUserActive(id) {
  if (db.mode !== 'supabase') {
    const local = db.data.users.find((u) => u.id === Number(id));
    if (local) {
      local.active = !local.active;
      db.persist();
    }
    return local ? toSafeUser(local) : null;
  }

  const user = db.data.users.find((u) => u.id === Number(id));
  if (!user) {
    throw new UserAdminError('Utilisateur introuvable dans Supabase.');
  }

  await callAdminRpc('admin_set_user_active', {
    p_email: normalizeEmail(user.email),
    p_active: !user.active,
  });

  await refreshFromSupabase();
  return toSafeUser({ ...user, active: !user.active });
}
// ---------------------------------------------------------------------------
// Mode démo (localStorage) — conservé pour le développement sans Supabase.
// ---------------------------------------------------------------------------
function saveUserLocal(user) {
  const users = db.data.users;
  if (user.id) {
    const idx = users.findIndex((u) => u.id === Number(user.id));
    if (idx >= 0) users[idx] = { ...users[idx], ...user };
  } else {
    const id = Math.max(0, ...users.map((u) => u.id)) + 1;
    users.push({
      id,
      username: user.username,
      password: user.password || 'changeme',
      email: user.email || '',
      role: user.role || 'CAISSIER',
      active: user.active !== false,
      must_change_password: false,
      last_login: null,
      created_at: new Date().toISOString(),
    });
  }
  db.persist();
  return user.id
    ? user
    : { ...user, id: Math.max(0, ...users.map((u) => u.id)) };
}

/** Réinitialise la sécurité : recrée la base de démonstration. */
export function resetSecurity() {
  // eslint-disable-next-line no-restricted-globals
  localStorage.removeItem('korgo_pro_db_v1');
  // Le prochain loadDB du module recréera la base.
  // eslint-disable-next-line no-restricted-globals
  location.reload();
}
// ============================================================================
// Authentification et profil utilisateur (mobile).
//
// ARCHITECTURE (identique au web — web/src/api/remoteAuth.js) :
//   * Supabase Auth est la SOURCE DE VÉRITÉ : signInWithPassword sur l'email ;
//   * le nom d'utilisateur est résolu en email via public.users (ilike) ;
//   * le profil applicatif (role, active) est lu dans public.users : c'est lui
//     qui porte le rôle utilisé par la matrice de permissions ;
//   * la CREATION de comptes reste réservée à l'admin (RPC admin_*, web ou
//     desktop) : le mobile ne gère aucun mot de passe.
//   * SESSION UNIQUE : après l'authentification, la session est enregistrée
//     dans `public.user_sessions` (voir supabase_single_session.sql). Si un autre
//     appareil est déjà connecté, la connexion est refusée ; `force: true`
//     ferme l'autre session et reprend la main ici.
// ============================================================================
import { requireClient, supabase, friendlyError } from './supabase';
import { registerSession, endSession } from './sessionApi';

/** Colonnes du profil (jamais de mot de passe : la table n'en expose pas). */
export const PROFILE_COLUMNS =
  'id,username,email,role,active,must_change_password,last_login';

/** Élève une erreur lisible (401 Supabase -> message métier). */
function authError(message) {
  const err = new Error(message);
  err.isAuth = true;
  return err;
}

/**
 * Connecte un utilisateur.
 * `identifiant` accepte un email OU un nom d'utilisateur.
 * `options.force` : ferme la session d'un autre appareil et prend la place
 * (session unique — voir supabase_single_session.sql).
 */
export async function login(identifiant, password, options = {}) {
  const client = requireClient();
  const ident = String(identifiant || '').trim();
  if (!ident || !password) {
    throw authError('Renseignez votre identifiant et votre mot de passe.');
  }

  let email = ident;
  if (!ident.includes('@')) {
    // Supabase Auth s'authentifie par email : on résout le nom d'utilisateur.
    const { data, error } = await client
      .from('users')
      .select('email')
      .ilike('username', ident)
      .maybeSingle();
    if (error || !data?.email) {
      throw authError(
        "Nom d'utilisateur inconnu. Utilisez votre email ou vérifiez votre nom d'utilisateur."
      );
    }
    email = data.email;
  }

  const { data: session, error: signInError } = await client.auth.signInWithPassword({
    email,
    password,
  });
  if (signInError) {
    throw authError('Connexion refusée. Vérifiez votre email et votre mot de passe.');
  }
  if (!session?.user?.email) {
    throw authError('Session Supabase invalide.');
  }

  try {
    // Session unique : ouvre (ou refuse) la session applicative. Levee
    // `SessionConflictError` si un autre appareil est deja connecte — le
    // `catch` ferme alors la session Supabase pour ne rien laisser ouvert.
    await registerSession({ force: !!options.force });
    return await fetchProfile(session.user.email);
  } catch (error) {
    // Un profil inactif/supprimé ne doit pas laisser une session ouverte.
    await client.auth.signOut({ scope: 'local' }).catch(() => {});
    throw error;
  }
}

async function fetchProfile(email) {
  const client = requireClient();
  const { data, error } = await client
    .from('users')
    .select(PROFILE_COLUMNS)
    .eq('email', email)
    .eq('active', true)
    .maybeSingle();

  if (error || !data) {
    throw authError(
      "Profil actif inaccessible. Vérifiez votre compte auprès de l'administrateur."
    );
  }
  return data;
}

/**
 * Restaure la session enregistrée dans AsyncStorage.
 * Retourne le profil, ou null si aucune session valide (ou profil inactif).
 */
export async function restoreSession() {
  if (!supabase) return null;
  try {
    const { data } = await supabase.auth.getSession();
    const email = data?.session?.user?.email;
    if (!email) return null;
    // Session unique : la session restauree a-t-elle encore le droit d'ouvrir
    // l'application ? (l'utilisateur a pu se connecter ailleurs entre-temps.)
    try {
      await registerSession();
    } catch (conflict) {
      if (conflict?.code === 'SESSION_ACTIVE') {
        await supabase.auth.signOut({ scope: 'local' }).catch(() => {});
        return null;
      }
      throw conflict;
    }
    return await fetchProfile(email);
  } catch (error) {
    await supabase.auth.signOut({ scope: 'local' }).catch(() => {});
    return null;
  }
}

/** Déconnexion : libère le verrou puis ferme la session locale. */
export async function logout() {
  if (!supabase) return;
  // D'abord le verrou applicatif : un autre poste peut se connecter aussitôt.
  await endSession().catch(() => {});
  const { error } = await supabase.auth.signOut({ scope: 'local' });
  if (error) throw new Error(friendlyError(error));
}

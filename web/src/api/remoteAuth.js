// Supabase Auth est la seule autorité d'authentification en mode distant.
//
// APRES l'authentification, la session applicative est ouverte dans la table
// `public.user_sessions` (verrou « une seule session par compte ») : si un
// autre appareil est déjà connecté, la connexion est refusée et la session
// Supabase locale est fermée (`force: true` permet de reprendre la main).
import { registerSession } from './sessionApi';

export const PROFILE_COLUMNS = 'id,username,email,role,active,must_change_password,last_login';

export async function authenticateRemote(client, email, password, options = {}) {
  const { data, error } = await client.auth.signInWithPassword({ email, password });
  if (error) throw new Error('Connexion Supabase refusée. Vérifiez votre email et votre mot de passe.');
  try {
    if (!data?.user?.email) throw new Error('Session Supabase invalide.');
    const profile = await client.from('users').select(PROFILE_COLUMNS)
      .eq('email', data.user.email).eq('active', true).maybeSingle();
    if (profile.error || !profile.data) {
      throw new Error('Profil actif inaccessible. Vérifiez le lien email et les politiques RLS avec votre administrateur.');
    }
    // Verrou multi-appareils (lève SessionConflictError si un autre appareil
    // est déjà connecté : le `catch` ci-dessous ferme alors la session).
    await registerSession({ force: !!options.force });
    return profile.data;
  } catch (error) {
    await client.auth.signOut({ scope: 'local' });
    throw error;
  }
}

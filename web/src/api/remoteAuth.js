// Supabase Auth est la seule autorité d'authentification en mode distant.
export const PROFILE_COLUMNS = 'id,username,email,role,active,must_change_password,last_login';

export async function authenticateRemote(client, email, password) {
  const { data, error } = await client.auth.signInWithPassword({ email, password });
  if (error) throw new Error('Connexion Supabase refusée. Vérifiez votre email et votre mot de passe.');
  try {
    if (!data?.user?.email) throw new Error('Session Supabase invalide.');
    const profile = await client.from('users').select(PROFILE_COLUMNS)
      .eq('email', data.user.email).eq('active', true).maybeSingle();
    if (profile.error || !profile.data) {
      throw new Error('Profil actif inaccessible. Vérifiez le lien email et les politiques RLS avec votre administrateur.');
    }
    return profile.data;
  } catch (error) {
    await client.auth.signOut({ scope: 'local' });
    throw error;
  }
}

-- ============================================================================
-- supabase_web_link_patch.sql
--
-- Corrige la liaison de l'app web (PostgREST) avec Supabase.
--
-- CONTEXTE : l'app web s'authentifie via Supabase Auth puis lit/écrit la base
-- par l'API REST (rôle `authenticated`). Trois verrous l'en empêchaient :
--   1. le schéma app_security était révoqué pour `authenticated`, donc toutes
--      les policies RLS appelant app_security.is_admin() échouaient avec
--      « permission denied for schema app_security » : aucune lecture des
--      tables réservées aux admins, AUCUNE écriture possible ;
--   2. aucune policy ne permettait à un utilisateur de lire SA propre ligne
--      public.users (nécessaire à web/src/api/remoteAuth.js) : la connexion
--      échouait pour tous les comptes non-admin ;
--   3. les emails de auth.users ne correspondaient à aucun public.users.email,
--      donc aucun profil n'était trouvable (connexion impossible).
--
-- Idempotent. À exécuter dans Dashboard Supabase -> SQL Editor, ou via :
--   python _apply_web_link_patch.py
--
-- NOTE : ce correctif est aussi intégré à supabase_rls_policies.sql afin
-- qu'une ré-exécution de ce dernier ne l'annule pas.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1) Rendre is_admin() évaluable par les policies RLS
--    (le schéma reste non exposé à PostgREST : pas d'appel via /rest/v1/rpc)
-- ----------------------------------------------------------------------------
GRANT USAGE ON SCHEMA app_security TO authenticated;

-- ----------------------------------------------------------------------------
-- 2) Email de l'utilisateur connecté
--    Fonction SECURITY DEFINER obligatoire : `authenticated` n'a PAS le droit
--    de lire auth.users directement, ce qui interdit une policy du type
--    USING (email = (SELECT email FROM auth.users WHERE id = auth.uid())).
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION app_security.current_email()
RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
  SELECT email FROM auth.users WHERE id = auth.uid()
$$;

REVOKE ALL ON FUNCTION app_security.current_email() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_security.current_email() TO authenticated;

-- ----------------------------------------------------------------------------
-- 3) Table `users` : UNE SEULE policy SELECT permissive (pour ne pas déclencher
--    le lint Supabase 'multiple_permissive_policies')
--      - un administrateur voit tous les utilisateurs (is_admin()) ;
--      - tout autre utilisateur ne voit que sa propre ligne (current_email()),
--        ce qui permet à remoteAuth.js de charger son profil -> login possible.
--    L'ancienne policy admin_full_users (FOR ALL) est remplacée par des
--    policies par action, comme le reste du schéma.
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS self_read_users ON public.users;
DROP POLICY IF EXISTS admin_full_users ON public.users;
DROP POLICY IF EXISTS admin_select_users ON public.users;
DROP POLICY IF EXISTS admin_insert_users ON public.users;
DROP POLICY IF EXISTS admin_update_users ON public.users;
DROP POLICY IF EXISTS admin_delete_users ON public.users;

CREATE POLICY admin_select_users ON public.users
  FOR SELECT TO authenticated
  USING (app_security.is_admin() OR email = app_security.current_email());

CREATE POLICY admin_insert_users ON public.users
  FOR INSERT TO authenticated
  WITH CHECK (app_security.is_admin());

CREATE POLICY admin_update_users ON public.users
  FOR UPDATE TO authenticated
  USING (app_security.is_admin())
  WITH CHECK (app_security.is_admin());

CREATE POLICY admin_delete_users ON public.users
  FOR DELETE TO authenticated
  USING (app_security.is_admin());

-- ----------------------------------------------------------------------------
-- 4) Lier les comptes Supabase Auth aux utilisateurs applicatifs
--    >>> ADAPTER les emails si nécessaire <<<
--    (voir la table de vérification en fin de script)
-- ----------------------------------------------------------------------------
UPDATE public.users SET email = 'haidaracompaore224@gmail.com' WHERE id = 1;
UPDATE public.users SET email = 'checomtech@gmail.com'          WHERE id = 2;

-- ----------------------------------------------------------------------------
-- 5) Vérification : chaque public.users doit trouver son auth.users
-- ----------------------------------------------------------------------------
SELECT u.id, u.username, u.email, u.role, u.active, a.id AS auth_id
FROM public.users u
LEFT JOIN auth.users a ON a.email = u.email
ORDER BY u.id;

-- ============================================================================
-- supabase_rls_policies.sql
--
-- Activer la Row Level Security (RLS) sur toutes les tables de Korgo Pro
-- et définir des policies adaptées aux deux profils applicatifs :
--
--   - "admin"  : accès complet (lecture + écriture) sur toutes les tables
--   - "user"   : utilisateur métier (caissier/vendeur) â€” accès en lecture
--                et écriture aux données opérationnelles, mais PAS aux
--                données sensibles (utilisateurs, logs, trésorerie, dépenses)
--
-- Identification : les users applicatifs sont authentifiés via Supabase Auth
-- (auth.uid()). Le rôle est stocké dans public.users.role ('ADMIN' ou autre).
-- L'utilisateur anon (clé publique, sans session) n'a accès à AUCUNE table.
--
-- Ã€ exécuter dans : Dashboard Supabase -> SQL Editor (ou psql). Idempotent.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 0) Helper : l'utilisateur courant (auth.uid()) est-il administrateur ?
--    (mappage auth.users.id <-> public.users via l'email)
--
--    La fonction vit dans le schéma "app_security", NON exposé par l'API
--    Supabase (PostgREST) : elle ne peut donc plus être appelée via
--    /rest/v1/rpc (corrige le linter authenticated_security_definer_function_executable).
-- ----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS app_security;




CREATE OR REPLACE FUNCTION app_security.is_admin()
RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.users u
    WHERE u.email = (SELECT email FROM auth.users WHERE id = auth.uid())
      AND UPPER(u.role) = 'ADMIN'
      AND u.active
  );
$$;

-- Restriction d'exécution : anon et public n'ont pas le droit d'appel.
-- (la fonction n'étant pas dans un schéma exposé, authenticated ne peut
-- de toute façon pas l'appeler via RPC ; le GRANT ci-dessous n'est là que
-- pour la propreté des privilèges)
REVOKE ALL ON SCHEMA app_security FROM PUBLIC;
REVOKE ALL ON SCHEMA app_security FROM anon;
-- ATTENTION : `authenticated` DOIT garder USAGE, sinon TOUTES les policies
-- ci-dessous échouent avec « permission denied for schema app_security »
-- (ni lecture, ni écriture pour l'app web qui passe par PostgREST).
-- Le schéma n'étant pas exposé à l'API, la fonction reste inatteignable
-- via /rest/v1/rpc : le risque est nul.
GRANT USAGE ON SCHEMA app_security TO authenticated;
GRANT USAGE ON SCHEMA app_security TO postgres;


-- ----------------------------------------------------------------------------
-- 0 bis) Helper : email de l'utilisateur connecté
--
--    Nécessaire au login de l'app web : remoteAuth.js recherche le profil
--    public.users dont l'email correspond à celui du compte Supabase Auth.
--    `authenticated` n'a PAS le droit de lire auth.users directement, d'où
--    cette fonction SECURITY DEFINER.
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
-- 1) Activer RLS sur toutes les tables + verrouiller l'accès public (anon)
-- ----------------------------------------------------------------------------
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'users','customers','activity_logs','sale_logs',
    'sales','sale_items','payments','sale_returns','sale_return_items',
    'proforma_invoices','proforma_invoice_items',
    'products','suppliers','inventory_movements','expense_categories',
    'expenses','purchase_orders','purchase_order_items','stock_alerts',
    'treasury_accounts','treasury_movements','cash_register_sessions','stores'
  ]
  LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format('REVOKE ALL ON public.%I FROM anon', t);
  END LOOP;
END $$;

-- ----------------------------------------------------------------------------
-- 2) Tables 100 % réservées aux ADMIN
--    users (hachages de mots de passe), activity_logs (audit), sale_logs,
--    expenses, expense_categories (données financières sensibles)
-- ----------------------------------------------------------------------------
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'users','activity_logs','sale_logs',
    'expenses','expense_categories'
  ]
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS admin_full_%1$s ON public.%1$I', t);
    EXECUTE format(
      'CREATE POLICY admin_full_%1$s ON public.%1$I
       FOR ALL TO authenticated
       USING (app_security.is_admin())
       WITH CHECK (app_security.is_admin())', t);
  END LOOP;
END $$;

-- ----------------------------------------------------------------------------
-- 3) Tables métier : lecture pour tout utilisateur authentifié
-- ----------------------------------------------------------------------------
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'customers','sales','sale_items','payments','sale_returns',
    'sale_return_items','proforma_invoices','proforma_invoice_items',
    'products','suppliers','inventory_movements','stores',
    'purchase_orders','purchase_order_items','stock_alerts',
    'treasury_accounts','treasury_movements','cash_register_sessions'
  ]
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS user_read_%1$s ON public.%1$I', t);
    EXECUTE format(
      'CREATE POLICY user_read_%1$s ON public.%1$I
       FOR SELECT TO authenticated
       USING (true)', t);
  END LOOP;
END $$;


-- ----------------------------------------------------------------------------
-- 4) Ã‰criture : RÃ‰SERVÃ‰E AUX ADMINS sur toutes les tables opérationnelles
--    (les utilisateurs standards sont en lecture seule ; supprime les
--    policies permissives USING(true)/WITH CHECK(true))
-- ----------------------------------------------------------------------------
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'sales','sale_items','payments','sale_returns','sale_return_items',
    'proforma_invoices','proforma_invoice_items',
    'inventory_movements','stock_alerts'
  ]
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS user_write_%1$s ON public.%1$I', t);
    EXECUTE format('DROP POLICY IF EXISTS admin_full_%1$s ON public.%1$I', t);
    -- Policies par action (et non FOR ALL) pour éviter le lint Supabase
    -- 'multiple_permissive_policies' : la lecture est déjà couverte par
    -- user_read_%1$s (FOR SELECT), un FOR ALL ajouterait un second policy
    -- permissif sur SELECT.
    EXECUTE format(
      'CREATE POLICY admin_insert_%1$s ON public.%1$I
       FOR INSERT TO authenticated
       WITH CHECK (app_security.is_admin())', t);
    EXECUTE format(
      'CREATE POLICY admin_update_%1$s ON public.%1$I
       FOR UPDATE TO authenticated
       USING (app_security.is_admin())
       WITH CHECK (app_security.is_admin())', t);
    EXECUTE format(
      'CREATE POLICY admin_delete_%1$s ON public.%1$I
       FOR DELETE TO authenticated
       USING (app_security.is_admin())', t);
  END LOOP;
END $$;


-- ----------------------------------------------------------------------------
-- 5) Ã‰criture admin uniquement : référentiels (clients, fournisseurs,
--    produits, achats) et trésorerie
-- ----------------------------------------------------------------------------
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'customers','suppliers','products','stores',
    'purchase_orders','purchase_order_items',
    'treasury_accounts','treasury_movements','cash_register_sessions'
  ]
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS admin_write_%1$s ON public.%1$I', t);
    -- Policies par action (et non FOR ALL) pour éviter le lint Supabase
    -- 'multiple_permissive_policies' : la lecture est déjà couverte par
    -- user_read_%1$s (FOR SELECT).
    EXECUTE format(
      'CREATE POLICY admin_insert_%1$s ON public.%1$I
       FOR INSERT TO authenticated
       WITH CHECK (app_security.is_admin())', t);
    EXECUTE format(
      'CREATE POLICY admin_update_%1$s ON public.%1$I
       FOR UPDATE TO authenticated
       USING (app_security.is_admin())
       WITH CHECK (app_security.is_admin())', t);
    EXECUTE format(
      'CREATE POLICY admin_delete_%1$s ON public.%1$I
       FOR DELETE TO authenticated
       USING (app_security.is_admin())', t);
  END LOOP;
END $$;

-- ----------------------------------------------------------------------------
-- 6) Vérification : état RLS + nombre de policies par table
-- ----------------------------------------------------------------------------
SELECT c.relname AS table,
       c.relrowsecurity AS rls_enabled,
       c.relforcerowsecurity AS rls_forced,
       (SELECT count(*) FROM pg_policies p
         WHERE p.schemaname = 'public' AND p.tablename = c.relname) AS policies
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r'
ORDER BY c.relname;



-- ----------------------------------------------------------------------------
-- 7) Nettoyage : supprimer l'ancienne version de is_admin dans le schéma
--    public (exposé à l'API) une fois les policies recréées.
-- ----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS public.is_admin();

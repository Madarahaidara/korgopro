-- supabase_org_functions.sql
-- Fonctions de securite multi-entreprises (schema app_security).
-- A deployer via le tableau de bord Supabase (SQL Editor).
-- Ne contient aucun secret.
CREATE SCHEMA IF NOT EXISTS app_security;

CREATE OR REPLACE FUNCTION app_security.current_organization_ids()
RETURNS uuid[] LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS
$$SELECT COALESCE(array_agg(organization_id), '{}')
FROM public.organization_members
WHERE user_id = auth.uid() AND active = TRUE$$;

CREATE OR REPLACE FUNCTION app_security.is_member_of(p_org uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public AS
$$SELECT EXISTS (SELECT 1 FROM public.organization_members
WHERE user_id = auth.uid() AND organization_id = p_org AND active = TRUE)$$;

CREATE OR REPLACE FUNCTION app_security.current_member_role(p_org uuid)
RETURNS text LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public AS
$$SELECT role FROM public.organization_members
WHERE user_id = auth.uid() AND organization_id = p_org AND active = TRUE
LIMIT 1$$;

CREATE OR REPLACE FUNCTION app_security.is_admin_in_org(p_org uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public AS
$$SELECT EXISTS (SELECT 1 FROM public.organization_members
WHERE user_id = auth.uid() AND organization_id = p_org
AND role = 'ADMIN' AND active = TRUE)$$;

REVOKE ALL ON SCHEMA app_security FROM anon, authenticated;
GRANT USAGE ON SCHEMA app_security TO authenticated;

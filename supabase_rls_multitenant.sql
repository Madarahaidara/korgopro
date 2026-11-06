-- supabase_rls_multitenant.sql : isolation stricte par organization_id.
-- A deployer APRES supabase_org_functions.sql, via SQL Editor Supabase.
-- Prerequis : colonnes organization_id (migration 0004) et backfill (0005).
DO $m$
DECLARE
  t text;
BEGIN
FOREACH t IN ARRAY ARRAY['customers','suppliers','products','stores',
'sales','sale_items','payments','sale_returns','sale_return_items',
'proforma_invoices','proforma_invoice_items','inventory_movements',
'stock_alerts','purchase_orders','purchase_order_items',
'treasury_accounts','treasury_movements','cash_register_sessions',
'monthly_closures','activity_logs','sale_logs','app_settings'] LOOP
EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
EXECUTE format('DROP POLICY IF EXISTS org_read_%I ON public.%I', t, t);
EXECUTE format('DROP POLICY IF EXISTS org_write_%I ON public.%I', t, t);
EXECUTE format('DROP POLICY IF EXISTS org_admin_%I ON public.%I', t, t);
EXECUTE format('CREATE POLICY org_read_%I ON public.%I FOR SELECT TO'
' authenticated USING (organization_id = ANY'
' (app_security.current_organization_ids()))', t, t);
EXECUTE format('CREATE POLICY org_write_%I ON public.%I FOR INSERT TO'
' authenticated WITH CHECK (app_security.is_member_of(organization_id))',
t, t);
EXECUTE format('CREATE POLICY org_admin_%I ON public.%I FOR UPDATE TO'
' authenticated USING (organization_id = ANY'
' (app_security.current_organization_ids())) WITH CHECK'
' (app_security.is_member_of(organization_id))', t, t);
END LOOP; END $m$;

-- PostgreSQL ORs permissive policies. These restrictive gates make the tenant
-- boundary hold even if older permissive policies are still installed.
DO $m$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['customers','suppliers','products','stores','sales',
    'sale_items','payments','sale_returns','sale_return_items','proforma_invoices',
    'proforma_invoice_items','inventory_movements','stock_alerts','purchase_orders',
    'purchase_order_items','treasury_accounts','treasury_movements','cash_register_sessions',
    'monthly_closures','activity_logs','sale_logs','app_settings'] LOOP
    EXECUTE format('DROP POLICY IF EXISTS org_tenant_gate ON public.%I', t);
    EXECUTE format('CREATE POLICY org_tenant_gate ON public.%I AS RESTRICTIVE FOR ALL TO authenticated USING (app_security.is_member_of(organization_id)) WITH CHECK (app_security.is_member_of(organization_id))', t);
  END LOOP;
  FOREACH t IN ARRAY ARRAY['customers','suppliers','products','stores','sales',
    'sale_items','payments','sale_returns','sale_return_items','proforma_invoices',
    'proforma_invoice_items','inventory_movements','stock_alerts','purchase_orders',
    'purchase_order_items','treasury_accounts','treasury_movements','cash_register_sessions',
    'monthly_closures','activity_logs','sale_logs','app_settings'] LOOP
    EXECUTE format('DROP POLICY IF EXISTS org_delete_admin_gate ON public.%I', t);
    EXECUTE format('CREATE POLICY org_delete_admin_gate ON public.%I AS RESTRICTIVE FOR DELETE TO authenticated USING (app_security.is_admin_in_org(organization_id))', t);
  END LOOP;
END $m$;
-- Suppression reservee aux ADMIN de l'entreprise.
-- A trigger below prevents a member from transferring a row between two
-- organizations they both belong to. Only an admin of both organizations
-- may change organization_id.
CREATE OR REPLACE FUNCTION app_security.guard_organization_id_change()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS
$$BEGIN
  IF NEW.organization_id IS DISTINCT FROM OLD.organization_id
     AND (NOT app_security.is_admin_in_org(OLD.organization_id)
          OR NOT app_security.is_admin_in_org(NEW.organization_id)) THEN
    RAISE EXCEPTION 'changing organization_id requires admin access to both organizations'
      USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END$$;

DO $m$
DECLARE
  t text;
BEGIN
FOREACH t IN ARRAY ARRAY['customers','suppliers','products','stores',
'sales','sale_returns','proforma_invoices','purchase_orders',
'treasury_accounts','treasury_movements','cash_register_sessions',
'monthly_closures'] LOOP
EXECUTE format('DROP POLICY IF EXISTS org_delete_%I ON public.%I', t, t);
EXECUTE format('CREATE POLICY org_delete_%I ON public.%I FOR DELETE TO'
' authenticated USING'
' (app_security.is_admin_in_org(organization_id))', t, t);
END LOOP; END $m$;

-- Memberships and organizations are security-critical. Membership creation
-- is reserved for trusted signup RPCs or an admin of the target organization.
ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS org_read_organizations ON public.organizations;
DROP POLICY IF EXISTS org_admin_organizations ON public.organizations;
DROP POLICY IF EXISTS org_create_organizations ON public.organizations;
DROP POLICY IF EXISTS org_delete_organizations ON public.organizations;
CREATE POLICY org_read_organizations ON public.organizations FOR SELECT TO authenticated
  USING (id = ANY(app_security.current_organization_ids()));
CREATE POLICY org_admin_organizations ON public.organizations FOR UPDATE TO authenticated
  USING (app_security.is_admin_in_org(id)) WITH CHECK (app_security.is_admin_in_org(id));
CREATE POLICY org_create_organizations ON public.organizations FOR INSERT TO authenticated
  WITH CHECK (false);
CREATE POLICY org_delete_organizations ON public.organizations FOR DELETE TO authenticated
  USING (app_security.is_admin_in_org(id));
DROP POLICY IF EXISTS org_organization_gate ON public.organizations;
CREATE POLICY org_organization_gate ON public.organizations AS RESTRICTIVE FOR ALL TO authenticated
  USING (app_security.is_member_of(id)) WITH CHECK (app_security.is_member_of(id));
DROP POLICY IF EXISTS org_organization_delete_gate ON public.organizations;
CREATE POLICY org_organization_delete_gate ON public.organizations AS RESTRICTIVE FOR DELETE TO authenticated
  USING (app_security.is_admin_in_org(id));

ALTER TABLE public.organization_members ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS org_read_memberships ON public.organization_members;
DROP POLICY IF EXISTS org_admin_memberships ON public.organization_members;
DROP POLICY IF EXISTS org_create_memberships ON public.organization_members;
DROP POLICY IF EXISTS org_delete_memberships ON public.organization_members;
CREATE POLICY org_read_memberships ON public.organization_members FOR SELECT TO authenticated
  USING (organization_id = ANY(app_security.current_organization_ids()));
CREATE POLICY org_admin_memberships ON public.organization_members FOR UPDATE TO authenticated
  USING (app_security.is_admin_in_org(organization_id))
  WITH CHECK (app_security.is_admin_in_org(organization_id));
CREATE POLICY org_create_memberships ON public.organization_members FOR INSERT TO authenticated
  WITH CHECK (app_security.is_admin_in_org(organization_id));
CREATE POLICY org_delete_memberships ON public.organization_members FOR DELETE TO authenticated
  USING (app_security.is_admin_in_org(organization_id));
DROP POLICY IF EXISTS org_membership_gate ON public.organization_members;
CREATE POLICY org_membership_gate ON public.organization_members AS RESTRICTIVE FOR ALL TO authenticated
  USING (app_security.is_member_of(organization_id))
  WITH CHECK (app_security.is_admin_in_org(organization_id));

DO $m$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['customers','suppliers','products','stores','sales',
    'sale_items','payments','sale_returns','sale_return_items','proforma_invoices',
    'proforma_invoice_items','inventory_movements','stock_alerts','purchase_orders',
    'purchase_order_items','treasury_accounts','treasury_movements','cash_register_sessions',
    'monthly_closures','activity_logs','sale_logs','app_settings'] LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS guard_organization_id_change ON public.%I', t);
    EXECUTE format('CREATE TRIGGER guard_organization_id_change BEFORE UPDATE OF organization_id ON public.%I FOR EACH ROW EXECUTE FUNCTION app_security.guard_organization_id_change()', t);
  END LOOP;
END $m$;

-- alembic_version : RLS active, aucun acces direct via les API (migrations
-- executees par le role proprietaire, qui contourne le RLS).
ALTER TABLE public.alembic_version ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.alembic_version FROM anon, authenticated;
DROP POLICY IF EXISTS none_shall_pass ON public.alembic_version;
CREATE POLICY none_shall_pass ON public.alembic_version
  FOR ALL TO public USING (false) WITH CHECK (false);


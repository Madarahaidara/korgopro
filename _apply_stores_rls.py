"""Active la RLS sur la table `stores` (référentiel magasins) en suivant
les conventions de supabase_rls_policies.sql :
  - RLS activée + forcée, anon révoqué ;
  - lecture pour `authenticated` ;
  - écriture réservée aux admins via app_security.is_admin().
Idempotent. Ne touche à aucune autre table.
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except Exception:
    pass

from sqlalchemy import create_engine, text

url = os.environ.get("DATABASE_URL", "")
if not url or url.startswith("sqlite"):
    print("[ERREUR] DATABASE_URL doit pointer vers PostgreSQL/Supabase.")
    sys.exit(1)
if url.startswith("postgresql:"):
    url = "postgresql+psycopg2://" + url.split("://", 1)[1]

IS_ADMIN_SQL = """
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
"""

STMTS = [
    """CREATE SCHEMA IF NOT EXISTS app_security""",
    """GRANT USAGE ON SCHEMA app_security TO postgres""",
    """ALTER TABLE public.stores ENABLE ROW LEVEL SECURITY""",
    """ALTER TABLE public.stores FORCE ROW LEVEL SECURITY""",
    """REVOKE ALL ON public.stores FROM anon""",
    """DROP POLICY IF EXISTS user_read_stores ON public.stores""",
    """CREATE POLICY user_read_stores ON public.stores
       FOR SELECT TO authenticated
       USING (true)""",
    """DROP POLICY IF EXISTS admin_write_stores ON public.stores""",
    """CREATE POLICY admin_write_stores ON public.stores
       FOR ALL TO authenticated
       USING (app_security.is_admin())
       WITH CHECK (app_security.is_admin())""",
]

engine = create_engine(url, connect_args={"sslmode": "require"})

with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
    who = conn.execute(text("SELECT current_user")).scalar()
    print(f"[OK] Connecté en tant que : {who}")

    # app_security.is_admin() : nécessaire pour la policy admin_write_stores
    has_is_admin = conn.execute(text(
        "SELECT count(*) FROM pg_proc p JOIN pg_namespace n "
        "ON n.oid = p.pronamespace WHERE p.proname='is_admin' "
        "AND n.nspname='app_security'")).scalar()
    if not has_is_admin:
        print("[i] app_security.is_admin() absente -> création")
        cur = conn.connection.driver_connection.cursor()
        cur.execute(IS_ADMIN_SQL)
    else:
        print("[OK] app_security.is_admin() présente")

    for stmt in STMTS:
        first = " ".join(stmt.split())[:70]
        try:
            cur = conn.connection.driver_connection.cursor()
            cur.execute(stmt)
        except Exception as exc:
            print(f"  [ERREUR] {first!r} -> {str(exc).splitlines()[0]}")
            sys.exit(1)
    print(f"[OK] {len(STMTS)} instructions exécutées")

    print("--- Vérification ---")
    rls = conn.execute(text(
        "SELECT relrowsecurity, relforcerowsecurity FROM pg_class c "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND c.relname='stores'")).one()
    print(f"stores: RLS={rls[0]}  FORCE={rls[1]}")
    for r in conn.execute(text(
            "SELECT policyname, cmd, roles FROM pg_policies "
            "WHERE schemaname='public' AND tablename='stores' ORDER BY policyname")):
        print(f"  policy: {r[0]} ({r[1]}, {r[2]})")

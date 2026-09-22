"""Vérifie l'état des policies RLS, droits is_admin() et dépendances."""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(".env")
url = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+psycopg2://")
engine = create_engine(url, connect_args={"sslmode": "require"})

with engine.connect() as c:
    print("--- Fonctions is_admin restantes ---")
    for r in c.execute(text(
            "SELECT n.nspname, p.oid::regprocedure FROM pg_proc p "
            "JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE p.proname='is_admin'")):
        print("  ", r)

    print("--- Dépendants de public.is_admin (deptype 'n') ---")
    rows = c.execute(text(
        "SELECT DISTINCT pol.polname, cls.relname "
        "FROM pg_depend d "
        "JOIN pg_proc f ON f.oid=d.objid "
        "JOIN pg_class cls ON cls.oid=d.refobjid "
        "JOIN pg_policy pol ON pol.oid=d.objid "
        "WHERE f.proname='is_admin' AND f.pronamespace='public'::regnamespace")).fetchall()
    for r in rows:
        print("  ", r)
    if not rows:
        print("   (aucune)")

    print("--- Policies utilisant is_admin (cible app_security attendue) ---")
    for r in c.execute(text(
            "SELECT tablename, policyname, qual FROM pg_policies "
            "WHERE schemaname='public' AND qual LIKE '%is_admin%'")):
        print("  ", r)

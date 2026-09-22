"""Diagnostic LECTURE SEULE : droits du role connecte + app_security."""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from sqlalchemy import create_engine, text

url = os.environ.get("DATABASE_URL", "")
if url.startswith("postgresql:"):
    url = "postgresql+psycopg2://" + url.split("://", 1)[1]

ROLES = text("""
    select rolname, rolsuper, rolbypassrls
      from pg_roles
     where rolname in ('postgres', 'authenticated', 'anon', 'service_role')
     order by rolname
""")

MINE = text("select current_user, session_user")

FUNCSEC = text("""
    select n.nspname || '.' || p.proname as fqn,
           pg_get_userbyid(p.proowner) as owner,
           p.prosecdef as security_definer
      from pg_proc p join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'app_security' order by 1
""")

try:
    engine = create_engine(url)
    with engine.connect() as conn:
        print("== Roles ==")
        for r in conn.execute(ROLES):
            print(f"  {r.rolname:<16} super={r.rolsuper} bypassrls={r.rolbypassrls}")

        print()
        print("== Session ==")
        for r in conn.execute(MINE):
            print(f"  current_user={r[0]}  session_user={r[1]}")

        print()
        print("== Fonctions app_security ==")
        for r in conn.execute(FUNCSEC):
            print(f"  {r.fqn:<32} owner={r.owner:<14} security_definer={r.security_definer}")
except Exception as exc:
    print("ERREUR:", type(exc).__name__, str(exc)[:400])
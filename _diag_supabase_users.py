"""Diagnostic LECTURE SEULE : etat de auth.users / public.users sur la base active.

Aucune ecriture, aucune modification de schema.
Usage : python _diag_supabase_users.py
"""
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

COLS = text(
    "select column_name, is_nullable, data_type from information_schema.columns "
    "where table_schema = :s and table_name = 'users' order by ordinal_position"
)
TRIGGERS = text(
    "select t.tgname from pg_trigger t "
    "join pg_class c on c.oid = t.tgrelid "
    "join pg_namespace n on n.oid = c.relnamespace "
    "where n.nspname = :s and c.relname = 'users' and not t.tgisinternal"
)
FUNCS = text(
    "select n.nspname || '.' || p.proname from pg_proc p "
    "join pg_namespace n on n.oid = p.pronamespace "
    "where n.nspname in ('public', 'app_security') order by 1"
)

try:
    engine = create_engine(url)
    with engine.connect() as conn:
        print("== Connexion ==")
        print("backend :", engine.url.get_backend_name())
        print("hote    :", engine.url.host, engine.url.port, "/", engine.url.database)

        print()
        print("== Colonnes auth.users ==")
        for name, nullable, dtype in conn.execute(COLS, {"s": "auth"}):
            print(f"  {name:<28} {dtype:<26} nullable={nullable}")

        print()
        print("== Colonnes public.users ==")
        for name, nullable, dtype in conn.execute(COLS, {"s": "public"}):
            print(f"  {name:<28} {dtype:<26} nullable={nullable}")

        print()
        print("== Triggers sur auth.users ==")
        rows = list(conn.execute(TRIGGERS, {"s": "auth"}))
        print("  ", [r[0] for r in rows] or "aucun")

        print()
        print("== Triggers sur public.users ==")
        rows = list(conn.execute(TRIGGERS, {"s": "public"}))
        print("  ", [r[0] for r in rows] or "aucun")

        print()
        print("== Compteurs ==")
        for tbl in ("auth.users", "auth.identities", "public.users"):
            try:
                n = conn.execute(text(f"select count(*) from {tbl}")).scalar()
                print(f"  {tbl:<20} {n}")
            except Exception as exc:  # table absente ou non lisible
                print(f"  {tbl:<20} ERREUR {str(exc)[:80]}")

        print()
        print("== Fonctions public / app_security ==")
        for (fqn,) in conn.execute(FUNCS):
            print("  ", fqn)
except Exception as exc:
    print("ERREUR:", type(exc).__name__, str(exc)[:400])
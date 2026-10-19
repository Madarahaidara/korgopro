"""Applique supabase_app_settings.sql (paramètres entreprise centralisés).

Installe :
  * la table singleton `public.app_settings` (ligne id=1, colonne JSONB `data`) ;
  * les policies RLS (lecture `authenticated`, écriture admin) ;
  * la RPC `app_merge_settings(p_patch jsonb)` (fusion superficielle atomique).

Idempotent, peut être rejoué sans risque.

Usage :
    python _apply_app_settings.py
Puis, pour retrouver les politiques RLS déjà présentes sur la base :
    python sync_rls_to_supabase.py
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from _apply_mobile_rpc import split_sql

SQL_FILE = Path(__file__).with_name("supabase_app_settings.sql")


def main():
    load_dotenv(".env")
    url = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+psycopg2://")
    engine = create_engine(url, connect_args={"sslmode": "require"})
    script = SQL_FILE.read_text(encoding="utf-8")

    with engine.begin() as c:
        for statement in split_sql(script):
            if all(line.strip().startswith("--") or not line.strip()
                   for line in statement.splitlines()):
                continue  # bloc de commentaires seul
            label = " ".join(statement.split())[:70]
            result = c.execute(text(statement))
            if result.returns_rows:
                print(f"OK (lecture) : {label}")
                for row in result.fetchall():
                    print("   ", row)
            else:
                print(f"OK : {label} ... ({result.rowcount} ligne(s) touchée(s))")

        # Vérification : table + policies + RPC
        exists = c.execute(text(
            "select 1 from information_schema.tables "
            "where table_schema='public' and table_name='app_settings'")).scalar()
        pol = [r[0] for r in c.execute(text(
            "select policyname from pg_policies "
            "where schemaname='public' and tablename='app_settings'"))]
        rpc = c.execute(text(
            "select 1 from pg_proc p join pg_namespace n on n.oid=p.pronamespace "
            "where n.nspname='public' and p.proname='app_merge_settings'")).scalar()
        print("\nTABLE_EXISTS =", bool(exists))
        print("POLICIES =", pol)
        print("RPC app_merge_settings =", bool(rpc))
    print("\nParamètres centralisés installés.")


if __name__ == "__main__":
    main()

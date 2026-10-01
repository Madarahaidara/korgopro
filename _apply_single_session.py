"""Applique supabase_single_session.sql (verrou « un appareil par utilisateur »).

Installe :
  * `public.user_sessions` + index unique partiel (UNE session ouverte / compte) ;
  * les helpers `app_security.*` (battement de coeur, expiration, messages) ;
  * les RPC clients `app_register_session`, `app_session_heartbeat`,
    `app_session_status`, `app_end_session` ;
  * les RPC administrateur `admin_list_sessions`, `admin_revoke_sessions` ;
  * les RPC du logiciel de bureau `app_desktop_session_*` (reservees au role
    technique de l'application, inaccessibles a `authenticated`).

Le script est idempotent et termine par une requete de verification.

Usage : python _apply_single_session.py
Puis, pour la garde d'ecriture mobile : python _apply_mobile_rpc.py
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from _apply_mobile_rpc import split_sql

SQL_FILE = Path(__file__).with_name("supabase_single_session.sql")


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
    print("\nVerrou multi-appareils installe.")


if __name__ == "__main__":
    main()

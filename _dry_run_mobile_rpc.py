"""Validation à blanc de supabase_mobile_rpc.sql (transaction ANNULÉE).

Exécute le script puis ROLLBACK : la base n'est PAS modifiée. Cela sert à
vérifier que les fonctions PL/pgSQL compilent et que les tables/colonnes
référencées existent réellement.

Usage : python _dry_run_mobile_rpc.py
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from _apply_mobile_rpc import split_sql

SQL_FILE = Path(__file__).with_name("supabase_mobile_rpc.sql")


def main():
    load_dotenv(".env")
    url = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+psycopg2://")
    engine = create_engine(url, connect_args={"sslmode": "require"})
    statements = split_sql(SQL_FILE.read_text(encoding="utf-8"))

    conn = engine.connect()
    ok = 0
    try:
        for statement in statements:
            if all(line.strip().startswith("--") or not line.strip()
                   for line in statement.splitlines()):
                continue
            label = " ".join(statement.split())[:70]
            result = conn.execute(text(statement))
            ok += 1
            if result.returns_rows:
                print(f"OK (lecture) : {label}")
                for row in result.fetchall():
                    print("   ", row)
            else:
                print(f"OK           : {label}")
    except Exception as exc:                    # noqa: BLE001 (diagnostic)
        conn.rollback()
        print(f"\nECHEC à l'instruction {ok + 1}: {exc}")
        return 1

    # --- Auto-test de la garde de droits -----------------------------------
    print()
    problems = 0
    try:
        role = conn.execute(text("SELECT app_security.current_role()")).scalar()
        can_sell = conn.execute(
            text("SELECT app_security.can('create_sales')")).scalar()
        print(f"current_role() (connexion non authentifiée) : {role!r}")
        print(f"can('create_sales')                         : {can_sell}")
        if role is not None or can_sell is not False:
            problems += 1
            print("  ATTENDU : NULL / False pour une connexion sans JWT Supabase.")

        ctx = conn.execute(text("SELECT public.app_mobile_context()")).scalar()
        print(f"app_mobile_context()                        : {ctx}")
        if ctx != {"ok": False, "role": None, "user_id": None, "username": None,
                   "permissions": [], "server_time": None} and not (
            isinstance(ctx, dict) and ctx.get("ok") is False and not ctx.get("permissions")):
            problems += 1
            print("  ATTENDU : ok=false et permissions vides.")

        try:
            conn.execute(text(
                "SELECT public.app_create_sale("
                "'[{\"product_id\": 1, \"quantity\": 1}]'::jsonb)"))
            problems += 1
            print("[GARDE KO] app_create_sale a accepté un appel non authentifié !")
        except Exception as exc:                # noqa: BLE001 (attendu)
            message = str(exc).splitlines()[0]
            if "non autorise" in message or "42501" in str(exc):
                print(f"[GARDE OK] app_create_sale refusé : {message}")
            else:
                problems += 1
                print(f"[GARDE KO] refus inattendu : {message}")
    finally:
        conn.rollback()                          # rien n'est conservé
        conn.close()

    print(f"\n{ok} instruction(s) validée(s), transaction ANNULÉE (aucune écriture).")
    print("Auto-test :", "OK" if problems == 0 else f"{problems} problème(s)")
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Diagnostic LECTURE SEULE de la liaison web (PostgREST) <-> Supabase.

Vérifie, côté base PostgreSQL :
  1. les privilèges REST des rôles `anon` et `authenticated` ;
  2. la fonction app_security.is_admin() ;
  3. le lien auth.users <-> public.users (email) utilisé par la connexion web ;
  4. le comportement réel d'un utilisateur Supabase Auth connecté (SET ROLE).

Aucune écriture n'est conservée : toutes les transactions de test sont annulées.

Usage : python _diag_web_supabase.py
"""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

TABLES = ["stores", "products", "customers", "suppliers", "sales", "sale_items",
          "proforma_invoices", "proforma_invoice_items", "inventory_movements",
          "treasury_accounts", "treasury_movements", "expenses", "activity_logs",
          "users"]

load_dotenv(".env")
url = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+psycopg2://")
engine = create_engine(url, connect_args={"sslmode": "require"})


def main():
    with engine.connect() as c:
        print("=== 1. Privilèges REST (anon / authenticated) + RLS ===")
        print(f"{'table':<26}{'anon':<7}{'authenticated':<15}{'RLS':<7}{'FORCE':<7}policies")
        for t in TABLES:
            r = c.execute(text("""
                SELECT c.relrowsecurity, c.relforcerowsecurity,
                       has_table_privilege('anon', c.oid, 'SELECT'),
                       has_table_privilege('authenticated', c.oid, 'SELECT'),
                       (SELECT count(*) FROM pg_policies p
                         WHERE p.schemaname='public' AND p.tablename=c.relname)
                FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' AND c.relname=:t"""), {"t": t}).fetchone()
            if not r:
                print(f"{t:<26}TABLE ABSENTE")
                continue
            print(f"{t:<26}{str(r[2]):<7}{str(r[3]):<15}{str(r[0]):<7}{str(r[1]):<7}{r[4]}")

        print("\n=== 2. Fonction app_security.is_admin() ===")
        print("  ", c.execute(text("""
            SELECT n.nspname, p.proname FROM pg_proc p
            JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE p.proname='is_admin'""")).fetchall())

        print("\n=== 3. Lien auth.users <-> public.users (email) ===")
        print(c.execute(text("""
            SELECT a.email AS auth_email, u.id, u.username, u.email AS users_email, u.role
            FROM auth.users a LEFT JOIN public.users u ON u.email = a.email
            ORDER BY a.created_at""")).fetchall())

        print("\n=== 4. Comportement d'un utilisateur Auth connecté (annulé) ===")
        for uid, email in c.execute(text(
                "SELECT id, email FROM auth.users ORDER BY created_at")).fetchall():
            print(f"\n  -- {email} --")
            conn = engine.connect()
            conn.execute(text("SET LOCAL role authenticated"))
            conn.execute(text("SELECT set_config('request.jwt.claims', :j, true)"),
                         {"j": '{"sub":"%s","email":"%s"}' % (uid, email)})

            def q(sql, params=None):
                sp = conn.begin_nested()
                try:
                    res = conn.execute(text(sql), params or {})
                    out = res.fetchall() if res.returns_rows else f"OK ({res.rowcount} ligne(s))"
                    sp.rollback()
                    return out
                except Exception as exc:  # noqa: BLE001
                    sp.rollback()
                    return "ERREUR: " + str(exc).splitlines()[0][:100]

            print("     is_admin()                 ->", q("SELECT app_security.is_admin()"))
            for t in ["users", "stores", "products", "sales", "customers",
                      "expenses", "activity_logs", "treasury_accounts"]:
                print(f"     SELECT {t:<20} -> {q(f'SELECT count(*) FROM public.{t}')}")
            print("     profil par email           ->",
                  q("SELECT id, username, role FROM public.users WHERE email = :e", {"e": email}))
            print("     INSERT stores              ->", q(
                "INSERT INTO public.stores (code,name,active) VALUES ('DIAG','diag',true)"))
            conn.rollback()
            conn.close()


if __name__ == "__main__":
    main()

"""Diagnostic (LECTURE SEULE) : la version INSTALLEE de `app_create_sale`
gere-t-elle reellement la vente a credit (payment_method = CRÉDIT) ?

Compare le corps de la fonction en base avec `supabase_mobile_rpc.sql` et
recherche les branches metier du credit.

Usage : python _diag_credit_rpc.py
"""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

MARKERS = [
    "'CREDIT'",
    "CRÉDIT",
    "v_method IN",
    "customers",
    "balance",
    "payments",
]


def main() -> int:
    load_dotenv(".env")
    engine = create_engine(
        os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+psycopg2://"),
        connect_args={"sslmode": "require"},
    )
    with engine.connect() as c:
        body = c.execute(text(
            "SELECT pg_get_functiondef(p.oid) FROM pg_proc p "
            "JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = 'public' AND p.proname = 'app_create_sale' "
            "LIMIT 1"
        )).scalar()

    print(f"longueur du corps installe : {len(body or '')} caracteres\n")
    for marker in MARKERS:
        n = (body or "").count(marker)
        print(f"{'OK  ' if n else 'ABSENT'} {marker!r} : {n} occurrence(s)")

    print("\n--- lignes contenant CREDIT / balance / customers ---")
    for i, line in enumerate((body or "").splitlines(), 1):
        if any(m in line for m in ("CREDIT", "CRÉDIT", "balance", "customers", "payments")):
            print(f"{i:4} {line.strip()}")

    # Les ventes a credit deja presentes en base (toutes plateformes).
    with engine.connect() as c:
        rows = c.execute(text(
            "SELECT payment_method, payment_status, count(*), "
            "       round(sum(total_amount - amount_paid)::numeric, 2) AS du "
            "FROM public.sales GROUP BY 1, 2 ORDER BY 1, 2"
        )).fetchall()
    print("\n--- ventes en base par (payment_method, payment_status) ---")
    for r in rows:
        print(f"   {str(r[0]):14} {str(r[1]):9} n={r[2]:4} reste_du={r[3]}")

    with engine.connect() as c:
        nb = c.execute(text(
            "SELECT count(*) FROM public.customers WHERE active"
        )).scalar()
        cols = c.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='customers' "
            "ORDER BY ordinal_position"
        )).scalars().all()
    print(f"\nclients actifs en base : {nb}")
    print(f"colonnes de `customers`: {', '.join(cols)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

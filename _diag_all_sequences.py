"""Diagnostic (LECTURE SEULE) : dessequences des colonnes `id` en base.

Symptomes connus provoques par une sequence en retard sur max(id) :
  * « duplicate key value violates unique constraint "treasury_movements_pkey" »
    a l'encaissement (`app_register_payment`) et a toute vente avec acompte ;
  * « duplicate key ... payments_pkey / sale_items_pkey / sale_logs_pkey » ;
  * ventes a credit et reglements donc « impossibles » depuis mobile et web.

Usage : python _diag_all_sequences.py
"""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

TABLES = [
    "sales", "sale_items", "payments", "sale_logs", "treasury_movements",
    "treasury_accounts", "inventory_movements", "customers", "products",
    "proforma_invoices", "proforma_invoice_items", "activity_logs", "stores",
]

QUERY = text("""
    SELECT t.relname,
           pg_get_serial_sequence('public.' || t.relname, 'id') AS seq,
           (SELECT max(x.id) FROM public.{{table}} x)            AS max_id
    FROM pg_class t
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'public' AND t.relkind = 'r' AND t.relname = :table
""")


def main() -> int:
    load_dotenv(".env")
    engine = create_engine(
        os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+psycopg2://"),
        connect_args={"sslmode": "require"},
    )
    problems = 0
    with engine.connect() as c:
        print(f"{'table':24} {'sequence':40} {'last_value':>10} {'max(id)':>9}  etat")
        for table in TABLES:
            seq = c.execute(text(
                "SELECT pg_get_serial_sequence('public.' || :t, 'id')"
            ), {"t": table}).scalar()
            if not seq:
                print(f"{table:24} {'(pas de sequence)':40}")
                continue
            max_id = c.execute(text(
                f'SELECT COALESCE(max(id), 0) FROM public."{table}"'
            )).scalar()
            last = c.execute(text(f"SELECT last_value, is_called FROM {seq}")).all()
            last_value, is_called = int(last[0][0]), bool(last[0][1])
            # nextval() = last_value + 1 quand is_called, sinon last_value.
            nxt = last_value + 1 if is_called else last_value
            state = "OK" if nxt > int(max_id or 0) else "DECALAGE : INSERT echouera"
            if nxt <= int(max_id or 0):
                problems += 1
            print(f"{table:24} {seq:40} {last_value:>10} {max_id:>9}  {state}")

    print("\nVerdict :",
          f"{problems} table(s) dont la sequence est en retard sur max(id)"
          if problems else "toutes les sequences sont en avance")
    if problems:
        print("Reparation : python fix_sequences.py  (ou _fix_sequences.py)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

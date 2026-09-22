"""Diagnostic LECTURE SEULE : etat reel des sequences PostgreSQL."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

from sqlalchemy import create_engine, text

url = os.environ["DATABASE_URL"]
if url.startswith("postgresql:"):
    url = "postgresql+psycopg2://" + url.split("://", 1)[1]

TABLES = ["users", "products", "customers", "sales", "activity_logs",
          "stores", "treasury_accounts"]

engine = create_engine(url)
with engine.connect() as conn:
    print(f"{'table':<22}{'seq':<26}{'last_value':>11}{'is_called':>11}{'max(id)':>9}")
    for tb in TABLES:
        try:
            seq = conn.execute(text("select pg_get_serial_sequence(:t, 'id')"),
                               {"t": tb}).scalar()
            if not seq:
                print(f"{tb:<22}{'pas de sequence':<26}")
                continue
            last, called = conn.execute(
                text(f"select last_value, is_called from {seq}")).one()
            mx = conn.execute(text(f"select coalesce(max(id), 0) from {tb}")).scalar()
            flag = "  <-- DESALIGNEE" if (not called) or last < mx else ""
            print(f"{tb:<22}{seq:<26}{last:>11}{str(called):>11}{mx:>9}{flag}")
        except Exception as exc:
            print(f"{tb:<22}ERREUR {str(exc)[:60]}")
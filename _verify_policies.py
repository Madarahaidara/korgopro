"""Vérifie les policies de cash_register_sessions (une seule par rôle/action)."""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(".env")
url = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+psycopg2://")
engine = create_engine(url, connect_args={"sslmode": "require"})

with engine.connect() as c:
    rows = c.execute(text(
        "SELECT cmd, count(*), string_agg(policyname, ', ') "
        "FROM pg_policies WHERE schemaname='public' "
        "AND tablename='cash_register_sessions' "
        "GROUP BY cmd ORDER BY cmd"))
    for cmd, n, names in rows:
        print(f"{cmd:8s} policies={n}  ->  {names}")

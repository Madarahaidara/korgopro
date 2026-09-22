"""Liste les index jamais utilisés depuis la dernière réinitialisation des
statistiques (linter Supabase 'unused_index'). Lecture seule."""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except Exception:
    pass

from sqlalchemy import create_engine, text

url = os.environ.get("DATABASE_URL", "")
if url.startswith("postgresql:"):
    url = "postgresql+psycopg2://" + url.split("://", 1)[1]

engine = create_engine(url, connect_args={"sslmode": "require"})

QUERY = text("""
SELECT s.schemaname, s.relname AS table_name, s.indexrelname AS index_name,
       s.idx_scan, s.idx_tup_read, s.idx_tup_fetch,
       pg_size_pretty(pg_relation_size(s.indexrelid)) AS size
FROM pg_stat_user_indexes s
WHERE s.idx_scan = 0
  AND s.schemaname = 'public'
ORDER BY pg_relation_size(s.indexrelid) DESC
""")

RESET = text("SELECT stats_reset FROM pg_stat_database "
             "WHERE datname = current_database()")

with engine.connect() as conn:
    try:
        reset = conn.execute(RESET).scalar()
        print(f"Statistiques réinitialisées : {reset}")
    except Exception:
        pass
    rows = conn.execute(QUERY).fetchall()
    print(f"{len(rows)} index jamais utilisés :")
    for schema, table, index, scans, rd, fetch, size in rows:
        print(f"  {index:55s} {table:28s} taille={size:>10s}")

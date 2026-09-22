"""Crée les index manquants sur les colonnes de clés étrangères
(linter Supabase 'unindexed_foreign_keys'), en CONCURRENTLY (autocommit).
Idempotent : les FK déjà couvertes par un index sont ignorées.
"""
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

# FK dont les colonnes de tête ne correspondent à aucun index existant.
QUERY = text("""
WITH fk AS (
  SELECT conrelid::regclass AS table_name,
         c.conkey AS attnums,
         (SELECT array_agg(a.attname ORDER BY x.ord)
            FROM unnest(c.conkey) WITH ORDINALITY x(attnum, ord)
            JOIN pg_attribute a
              ON a.attrelid = c.conrelid AND a.attnum = x.attnum) AS columns
  FROM pg_constraint c
  WHERE c.contype = 'f'
    AND c.connamespace = 'public'::regnamespace
)
SELECT f.table_name::text, f.columns
FROM fk f
WHERE NOT EXISTS (
  SELECT 1 FROM pg_index i
  WHERE i.indrelid = (f.table_name)::oid
    AND (i.indkey::int2[])[0:array_length(f.attnums,1)-1]
        @> f.attnums
)
ORDER BY 1
""")

with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
    rows = conn.execute(QUERY).fetchall()
    if not rows:
        print("Aucune FK sans index couvrant. Rien à faire.")
        sys.exit(0)
    print(f"{len(rows)} index à créer :")
    cur = conn.connection.driver_connection.cursor()
    for table, cols in rows:
        table = str(table)
        col = str(cols[0])
        idx = f"ix_{table}_{col}"
        stmt = (f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{idx}" '
                f'ON public."{table}" ("{col}")')
        try:
            cur.execute(stmt)
            print(f"  [OK] {idx}")
        except Exception as exc:
            print(f"  [ERREUR] {idx} -> {str(exc).splitlines()[0]}")


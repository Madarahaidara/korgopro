"""Applique supabase_monthly_closures.sql sur la base (idempotent)."""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
engine = create_engine(os.environ['DATABASE_URL'])
sql = open('supabase_monthly_closures.sql', encoding='utf-8').read()

with engine.begin() as conn:
    for chunk in sql.split(';'):
        # retirer les lignes de commentaire de tête
        body = '\n'.join(l for l in chunk.splitlines() if not l.strip().startswith('--'))
        if body.strip():
            conn.execute(text(body))

    # Vérification
    exists = conn.execute(text(
        "select 1 from information_schema.tables "
        "where table_schema='public' and table_name='monthly_closures'")).scalar()
    cols = [r[0] for r in conn.execute(text(
        "select column_name from information_schema.columns "
        "where table_schema='public' and table_name='monthly_closures' order by ordinal_position"))]
    pol = [r[0] for r in conn.execute(text(
        "select policyname from pg_policies where schemaname='public' and tablename='monthly_closures'"))]
    print('TABLE_EXISTS =', bool(exists))
    print('COLUMNS =', cols)
    print('POLICIES =', pol)

"""Verifie les colonnes NULL dans les tables de logs."""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from dotenv import load_dotenv; load_dotenv()
import os
from sqlalchemy import create_engine, text as t
e = create_engine(os.environ['DATABASE_URL'])
c = e.connect()
print('activity_logs :', c.execute(t("""
    select count(*) filter (where username is null) as username_null,
           count(*) filter (where action is null) as action_null,
           count(*) filter (where created_at is null) as created_null
    from activity_logs""")).fetchone()._mapping)
print('sale_logs     :', c.execute(t("""
    select count(*) filter (where sale_number is null) as sale_null,
           count(*) filter (where username is null) as username_null,
           count(*) filter (where user_role is null) as role_null,
           count(*) filter (where action is null) as action_null,
           count(*) filter (where total_amount is null) as amount_null,
           count(*) filter (where created_at is null) as created_null
    from sale_logs""")).fetchone()._mapping)

"""Colonnes nullables concernees par les items Qt."""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from dotenv import load_dotenv; load_dotenv()
import os
from sqlalchemy import create_engine, text as t
e = create_engine(os.environ['DATABASE_URL'])
q = """
select table_name, column_name, is_nullable
from information_schema.columns
where table_schema='public' and (
  (table_name='products' and column_name in ('name','category'))
  or (table_name='suppliers' and column_name='name')
  or (table_name='sales' and column_name in ('sale_number','sale_status'))
  or (table_name='stock_movements' and column_name='movement_type')
  or (table_name='expenses' and column_name in ('description','category_id'))
  or (table_name='proforma_invoices' and column_name in ('proforma_number','status'))
  or (table_name='users' and column_name='username')
  or (table_name='treasury_accounts' and column_name in ('name','account_type'))
  or (table_name='treasury_movements' and column_name='movement_type')
  or (table_name='activity_logs' and column_name in ('username','action'))
  or (table_name='sale_logs' and column_name in ('sale_number','username','user_role','action'))
) and is_nullable='YES'
order by table_name, column_name
"""
for r in e.connect().execute(t(q)):
    print(f'{r.table_name}.{r.column_name}  NULLABLE')

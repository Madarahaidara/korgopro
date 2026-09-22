"""Vérifie et resynchronise les séquences PostgreSQL désalignées."""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from dotenv import load_dotenv; load_dotenv()
import os
from sqlalchemy import create_engine, text as t
e = create_engine(os.environ['DATABASE_URL'])
TABLES = ['sales', 'sale_items', 'payments', 'products', 'customers', 'stores',
          'users', 'treasury_accounts', 'treasury_movements', 'cash_register_sessions',
          'monthly_closures', 'expenses', 'activity_logs', 'proforma_invoices',
          'proforma_invoice_items', 'suppliers', 'sale_logs']
with e.begin() as conn:
    for tb in TABLES:
        try:
            mx = conn.execute(t(f'select coalesce(max(id),0) from {tb}')).scalar()
            seq = conn.execute(t(
                "select pg_get_serial_sequence(:tb, 'id')"), {'tb': tb}).scalar()
            if not seq:
                print(f'{tb:28s} pas de séquence (id non serial)')
                continue
            last = conn.execute(t(f'select last_value from {seq}')).scalar()
            if last < mx:
                conn.execute(t(
                    'select setval(:s, :v, true)'), {'s': seq, 'v': mx})
                print(f'{tb:28s} CORRIGE seq {last} -> {mx}')
            else:
                print(f'{tb:28s} ok (seq={last}, max={mx})')
        except Exception as ex:
            print(f'{tb:28s} ERREUR {str(ex)[:80]}')


"""Test d'integration : vente POS -> mouvement de tresorerie -> annulation."""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from sqlalchemy import create_engine, text as sqltext  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
import os  # noqa: E402
from core.database import SessionLocal  # noqa: E402
from ui.views.sale_services import SaleService, default_cash_account  # noqa: E402
from core.models.stock_models import Product  # noqa: E402
from datetime import datetime  # noqa: E402

load_dotenv()
engine = create_engine(os.environ['DATABASE_URL'])
db = SessionLocal()
fails = []


def check(name, ok, detail=''):
    print(('OK   ' if ok else 'ECHEC') + f'  {name}' + (f'  -- {detail}' if detail else ''))
    if not ok:
        fails.append(name)


# Nettoyage préalable (résidus d'un run crashé)
db.execute(sqltext("delete from products where code='_TESTSKU'"))
db.commit()

u = db.execute(sqltext('select id from users where active=true order by id limit 1')).scalar()
account = default_cash_account(db)
check('compte de caisse par defaut present', account is not None,
      f'{account.name if account else "AUCUN"}')
before = float(account.current_balance)

prod = Product(code='_TESTSKU', name='_TEST_PROD', category='_TEST',
               quantity=100, min_stock=5,
               purchase_price=400, sale_price=1000, active=True)
db.add(prod)
db.commit()

svc = SaleService(db)
ok, sale, msg = svc.create_sale({
    'sale_number': 'S_TEST_' + datetime.now().strftime('%H%M%S'),
    'cashier_id': u,
    'subtotal': 2000, 'discount_amount': 0, 'tax_amount': 0,
    'total_amount': 2000, 'amount_paid': 2500, 'change_amount': 500,
    'payment_method': 'ESPECES', 'payment_status': 'PAID',
    'items': [{'product_id': prod.id, 'quantity': 2, 'unit_price': 1000,
               'discount_percent': 0, 'discount_amount': 0, 'line_total': 2000,
               'product_name': '_TEST_PROD'}],
}, user_info={'id': u, 'username': 'test', 'role': 'ADMIN'})
check('create_sale', ok and sale is not None, msg)
db.refresh(account)
after_sale = float(account.current_balance)
check('mouvement IN poste (+2000)', abs(after_sale - (before + 2000)) < 0.01,
      f'{before} -> {after_sale}')
mv = db.execute(sqltext(
    "select count(*), coalesce(sum(amount),0) from treasury_movements "
    "where reference_type='SALE' and reference_id=:i and movement_type='IN'"),
    {'i': sale.id}).fetchone()
check('mouvement SALE reference en base', mv[0] == 1 and abs(float(mv[1]) - 2000) < 0.01,
      f'{mv[0]} mv, total {mv[1]}')

okc, msgc = svc.cancel_sale(sale.id, 'test auto', {'id': u, 'username': 'test', 'role': 'ADMIN'})
check('cancel_sale', okc, msgc)
db.refresh(account)
after_cancel = float(account.current_balance)
check('reversement OUT (-2000) -> solde initial', abs(after_cancel - before) < 0.01,
      f'{after_sale} -> {after_cancel}')

# Nettoyage
with engine.begin() as conn:
    n1 = conn.execute(sqltext(
        "delete from treasury_movements where reference_id=:i "
        "and reference_type in ('SALE','SALE_CANCEL')"), {'i': sale.id}).rowcount
    conn.execute(sqltext('delete from payments where sale_id=:i'), {'i': sale.id})
    conn.execute(sqltext('delete from sale_items where sale_id=:i'), {'i': sale.id})
    conn.execute(sqltext("delete from sale_logs where sale_id=:i"), {'i': sale.id})
    conn.execute(sqltext('delete from sales where id=:i'), {'i': sale.id})
    conn.execute(sqltext("delete from products where code='_TESTSKU'"))
print(f'NETTOYAGE: {n1} mouvements, vente+payment+items+produit supprimes')
db.close()
print()
print('RESULTAT:', 'TOUS OK' if not fails else f'{len(fails)} ECHEC(S): {fails}')

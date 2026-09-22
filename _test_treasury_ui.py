"""Test UI offscreen : les combobox de comptes doivent être remplies."""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from dotenv import load_dotenv; load_dotenv()
from PySide6.QtWidgets import QApplication
from ui.views.treasury_view import TreasuryView

app = QApplication([])
view = TreasuryView(user=None)
fails = []


def check(name, ok, detail=''):
    print(('OK   ' if ok else 'ECHEC') + f'  {name}' + (f'  -- {detail}' if detail else ''))
    if not ok:
        fails.append(name)


check('mv_account rempli', view.mv_account.count() > 0,
      f'{view.mv_account.count()} items: {view.mv_account.currentText()}')
check('session_account rempli', view.session_account.count() > 0,
      f'{view.session_account.count()} items')
check('currentData = id du compte', view.mv_account.currentData() is not None,
      f'data={view.mv_account.currentData()}')
# la creation d'un compte doit rafraichir les combos
res = view.manager.create_account(name='_TEST_UI_ACC', account_type='BANK',
                                  initial_balance=10)
check('create_account via manager', res.get('success'))
view._load_accounts()
check('nouveau compte visible dans mv_account',
      view.mv_account.findData(res['account'].id) >= 0)
# nettoyage
view.manager.delete_account(res['account'].id)
from sqlalchemy import create_engine, text as t
e = create_engine(os.environ['DATABASE_URL'])
with e.begin() as c:
    c.execute(t("delete from treasury_accounts where name='_TEST_UI_ACC'"))

# _add_movement avec un utilisateur DICT (cas reel : main_window passe un dict)
import ui.views.treasury_view as tv
captured = {}


def fake_add(*args, **kwargs):
    captured['user_id'] = kwargs.get('user_id')
    captured['account_id'] = kwargs.get('account_id')
    return {"success": True}


view.manager.add_movement = fake_add
tv.QMessageBox.information = staticmethod(lambda *a, **k: None)
tv.QMessageBox.warning = staticmethod(lambda *a, **k: None)
tv.QMessageBox.critical = staticmethod(lambda *a, **k: None)
view.user = {"id": 2, "username": "admin", "role": "ADMIN"}
view.mv_amount.setValue(50)
view._add_movement()
check('_add_movement avec user dict -> user_id=2', captured.get('user_id') == 2,
      f'captured={captured}')
check('account_id pris de la combobox', captured.get('account_id') is not None,
      f'account_id={captured.get("account_id")}')
view.user = type('U', (), {'id': 3})()
view._add_movement()
check('_add_movement avec objet user -> user_id=3', captured.get('user_id') == 3,
      f'user_id={captured.get("user_id")}')
print()
print('RESULTAT:', 'TOUS OK' if not fails else f'{len(fails)} ECHEC(S): {fails}')


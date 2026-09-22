"""Tests du module trésorerie desktop (base réelle, nettoyage inclus)."""
import io
import sys
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from sqlalchemy import create_engine, text as sqltext  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
import os  # noqa: E402
from core.database import SessionLocal  # noqa: E402
from core.treasury_manager import TreasuryManager  # noqa: E402

load_dotenv()
engine = create_engine(os.environ['DATABASE_URL'])
db = SessionLocal()
mgr = TreasuryManager(session=db)
fails = []


def check(name, ok, detail=''):
    print(('OK   ' if ok else 'ECHEC') + f'  {name}' + (f'  -- {detail}' if detail else ''))
    if not ok:
        fails.append(name)


# ---------------------------------------------------------------- A. Cohérence soldes <-> mouvements
rows = db.execute(sqltext("""
    select a.id, a.name, a.initial_balance, a.current_balance,
           coalesce(sum(case when m.movement_type='IN' then m.amount else 0 end), 0) as tin,
           coalesce(sum(case when m.movement_type='OUT' then m.amount else 0 end), 0) as tout
    from treasury_accounts a left join treasury_movements m on m.account_id = a.id
    where a.is_active = true
    group by a.id, a.name, initial_balance, current_balance
""")).fetchall()
for r in rows:
    expected = float(r.initial_balance or 0) + float(r.tin) - float(r.tout)
    drift = expected - float(r.current_balance or 0)
    check(f'A. solde coherent: {r.name}', abs(drift) < 0.01,
          f'stored={r.current_balance}, recalculé={expected}, écart={drift:.2f}')

# ---------------------------------------------------------------- B. Total trésorerie
tot = mgr.get_total_balance()
dbtot = db.execute(sqltext(
    'select coalesce(sum(current_balance),0) from treasury_accounts where is_active=true')).scalar()
check('B. get_total_balance', tot.get('success') and abs(float(tot.get('total', 0)) - float(dbtot)) < 0.01,
      f'{tot.get("total")} vs {dbtot}')

# ---------------------------------------------------------------- C. Résumé mensuel vs SQL direct
now = datetime.now()
summary = mgr.compute_month_summary(now.year, now.month)
sql_sum = db.execute(sqltext("""
    select count(*), coalesce(sum(total_amount),0),
           coalesce(sum(greatest(amount_paid - change_amount, 0)),0)
    from sales
    where sale_date >= date_trunc('month', now()) and sale_date < date_trunc('month', now()) + interval '1 month'
      and sale_status <> 'CANCELLED' and (type_document is null or type_document <> 'AVOIR')
""")).fetchone()
check('C. compute_month_summary: ventes', summary.get('sales_count') == sql_sum[0],
      f"manager={summary.get('sales_count')} vs SQL={sql_sum[0]}")
check('C. compute_month_summary: total', abs(float(summary.get('total_sales', 0)) - float(sql_sum[1])) < 0.01)
check('C. compute_month_summary: encaissé', abs(float(summary.get('total_collected', 0)) - float(sql_sum[2])) < 0.01,
      f"manager={summary.get('total_collected')} vs SQL={sql_sum[2]}")

# ---------------------------------------------------------------- E. Orphelins
orph = db.execute(sqltext(
    'select count(*) from treasury_movements m left join treasury_accounts a '
    'on a.id=m.account_id where a.id is null')).scalar()
check('E. mouvements orphelins', orph == 0, f'{orph}')

# ---------------------------------------------------------------- F. Écritures sur comptes de TEST (puis nettoyage SQL)
acc1 = mgr.create_account(name='_TEST_A', account_type='CASH', initial_balance=1000)
acc2 = mgr.create_account(name='_TEST_B', account_type='BANK', initial_balance=500)
check('F. create_account x2', acc1.get('success') and acc2.get('success'))
id1, id2 = acc1['account'].id, acc2['account'].id

r = mgr.add_movement(id1, 'IN', 250, description='test entree')
check('F. add_movement IN +250 -> 1250', r.get('success') and
      abs(float(mgr.get_account(id1)['account'].current_balance) - 1250) < 0.01)
r = mgr.add_movement(id1, 'OUT', -50)
check('F. add_movement OUT montant negatif refuse', not r.get('success'))
r = mgr.add_movement(id1, 'OUT', 300, description='test sortie')
check('F. add_movement OUT -300 -> 950', r.get('success') and
      abs(float(mgr.get_account(id1)['account'].current_balance) - 950) < 0.01)
r = mgr.transfer(id1, id2, 200)
check('F. transfer 200 -> A=750 / B=700', r.get('success') and
      abs(float(mgr.get_account(id1)['account'].current_balance) - 750) < 0.01 and
      abs(float(mgr.get_account(id2)['account'].current_balance) - 700) < 0.01)
r = mgr.transfer(id1, id2, -10)
check('F. transfer negatif refuse', not r.get('success'))

# session de caisse sur _TEST_A
u = db.execute(sqltext('select id from users where active=true order by id limit 1')).scalar()
op = mgr.open_cash_session(id1, u, opening_amount=750)
check('F. open_cash_session', op.get('success'))
sid = op['session'].id
mgr.add_movement(id1, 'IN', 100, description='test session')
cl = mgr.close_cash_session(sid, closing_amount=850)
check('F. close_cash_session: expected=750+100=850, diff=0', cl.get('success') and
      abs(float(cl['session'].expected_amount) - 850) < 0.01 and
      abs(float(cl['session'].difference or 0)) < 0.01,
      f"expected={cl['session'].expected_amount} diff={cl['session'].difference}")
r = mgr.close_cash_session(sid, 999)
check('F. re-fermeture refusee', not r.get('success'))

op2 = mgr.open_cash_session(id2, u)
sid2 = op2['session'].id
op3 = mgr.open_cash_session(id2, u)
check('F. double session ouverte refusee', not op3.get('success'), op3.get('error', ''))

# ---------------------------------------------------------------- G. close_month réel + nettoyage manuel
c = mgr.close_month(now.year, now.month, user_id=u, notes='test auto')
check('G. close_month commit', c.get('success') and c['closure'].status == 'CLOSED',
      f"{c['closure'].period if c.get('closure') else c.get('error')}")
r = mgr.close_month(now.year, now.month)
check('G. re-cloture refusee', not r.get('success'))
closures = mgr.get_closures()
check('G. get_closures contient la periode', closures.get('success') and
      any(x.period == f'{now.year:04d}-{now.month:02d}' for x in closures['closures']))

# ---------------------------------------------------------------- Nettoyage
with engine.begin() as conn:
    n1 = conn.execute(sqltext(
        "delete from treasury_movements where account_id in (select id from treasury_accounts "
        "where name in ('_TEST_A', '_TEST_B'))")).rowcount
    n2 = conn.execute(sqltext(
        "delete from cash_register_sessions where account_id in (select id from treasury_accounts "
        "where name in ('_TEST_A', '_TEST_B'))")).rowcount
    n3 = conn.execute(sqltext(
        "delete from treasury_accounts where name in ('_TEST_A', '_TEST_B')")).rowcount
    n4 = conn.execute(sqltext(
        "delete from monthly_closures where notes = 'test auto'")).rowcount
print(f'NETTOYAGE: {n1} mouvements, {n2} sessions, {n3} comptes, {n4} clotures supprimes')
db.close()

print()
print('RESULTAT:', 'TOUS OK' if not fails else f'{len(fails)} ECHEC(S): {fails}')


"""Tests multi-entreprises : modeles + migrations 0004-0006 (SQLite tmp)."""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker


def _fresh_base():
    from core.database import Base
    import core.models.organization  # noqa: F401
    import core.models.store  # noqa: F401
    import core.models.customer  # noqa: F401
    import core.models.stock_models  # noqa: F401
    import core.models.sale_models  # noqa: F401
    import core.models.treasury_models  # noqa: F401
    import core.models.activity_log  # noqa: F401
    import core.models.sale_log  # noqa: F401
    import core.models.app_setting  # noqa: F401
    return Base


def test_org_tables_and_columns_present():
    Base = _fresh_base()
    eng = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=eng)
    insp = inspect(eng)
    names = set(insp.get_table_names())
    assert 'organizations' in names
    assert 'organization_members' in names
    for t in ('customers', 'products', 'sales', 'stores'):
        cols = {c['name'] for c in insp.get_columns(t)}
        assert 'organization_id' in cols, t


def test_unique_per_org_allows_same_code():
    Base = _fresh_base()
    eng = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=eng)
    S = sessionmaker(bind=eng)
    from core.models.organization import Organization
    from core.models.store import Store
    s = S()
    o1 = Organization(name='A', code='A-001')
    o2 = Organization(name='B', code='B-001')
    s.add_all([o1, o2])
    s.commit()
    s.add_all([
        Store(code='MAG-0001', name='M1', organization_id=o1.id),
        Store(code='MAG-0001', name='M1b', organization_id=o2.id),
    ])
    s.commit()
    n = s.execute(text('SELECT COUNT(*) FROM stores')).scalar()
    assert n == 2
    s.close()


def test_sale_creation_propagates_store_organization_to_related_rows():
    Base = _fresh_base()
    eng = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=eng)
    S = sessionmaker(bind=eng)
    from core.models.organization import Organization
    from core.models.store import Store
    from core.models.stock_models import Product
    from core.models.user import User
    from core.models.sale_models import SaleItem, Payment
    from core.models.sale_log import SaleLog
    from core.models.treasury_models import TreasuryAccount, TreasuryMovement
    from ui.views.sale_services import SaleService

    with S() as session:
        org = Organization(name='Entreprise vente', code='ORG-SALE-TEST')
        session.add(org)
        session.flush()
        store = Store(code='STORE-SALE-TEST', name='Magasin test',
                      organization_id=org.id)
        user = User(username='sale-test', email='sale-test@example.invalid',
                    active=True)
        account = TreasuryAccount(name='Caisse test', account_type='CASH',
                                  organization_id=org.id)
        session.add_all([store, user, account])
        session.flush()
        product = Product(code='PROD-SALE-TEST', name='Produit test',
                          category='Test', quantity=5, purchase_price=2,
                          sale_price=4, store_id=store.id,
                          organization_id=org.id)
        session.add(product)
        session.flush()

        ok, sale, message = SaleService(session).create_sale({
            'sale_number': 'SALE-ORG-TEST-001',
            'cashier_id': user.id,
            'store_id': store.id,
            'items': [{'product_id': product.id, 'quantity': 1,
                       'unit_price': 4, 'line_total': 4}],
            'subtotal': 4,
            'discount_amount': 0,
            'tax_amount': 0,
            'total_amount': 4,
            'amount_paid': 4,
            'change_amount': 0,
            'payment_method': 'CASH',
            'payment_status': 'PAID',
        }, user_info={'id': user.id, 'username': user.username,
                      'role': 'CAISSIER'})

        assert ok, message
        assert sale.organization_id == org.id
        assert session.query(SaleItem).one().organization_id == org.id
        assert session.query(Payment).one().organization_id == org.id
        assert session.query(TreasuryMovement).one().organization_id == org.id
        assert session.query(SaleLog).one().organization_id == org.id
    eng.dispose()


def test_alembic_chain_revisions_linked():
    """La chaine 0001 -> 0006 est continue (sans executer de migration)."""
    import re
    from pathlib import Path
    versions = Path('alembic/versions')
    rev_to_down = {}
    for path in versions.glob('*.py'):
        text = path.read_text(encoding='utf-8')
        m_rev = re.search(r"^revision:\s*str\s*=\s*['\"]([^'\"]+)['\"]",
                          text, re.MULTILINE)
        m_down = re.search(r"^down_revision[^=]*=\s*['\"]([^'\"]+)['\"]",
                            text, re.MULTILINE)
        if m_rev:
            rev_to_down[m_rev.group(1)] = (
                m_down.group(1) if m_down else None)
    assert rev_to_down.get('0004_multi_entreprise') == '0003_app_settings'
    assert (rev_to_down.get('0005_backfill_organization')
            == '0004_multi_entreprise')
    assert (rev_to_down.get('0006_organization_id_required')
            == '0005_backfill_organization')


def test_alembic_upgrade_head_backfills_and_requires_organization(tmp_path, monkeypatch):
    """Applique la chaine reelle sur une base SQLite temporaire."""
    from alembic import command
    from alembic.config import Config
    from pathlib import Path

    db_path = tmp_path / 'multitenant.sqlite'
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{db_path.as_posix()}')
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / 'alembic.ini'))

    command.upgrade(config, 'head')

    eng = create_engine(f'sqlite:///{db_path.as_posix()}')
    try:
        insp = inspect(eng)
        with eng.connect() as conn:
            assert conn.execute(text(
                'SELECT version_num FROM alembic_version')).scalar() == (
                    '0006_organization_id_required')
            assert conn.execute(text(
                'SELECT COUNT(*) FROM organizations')).scalar() == 1
            org_id = conn.execute(text(
                'SELECT organization_id FROM app_settings WHERE id = 1'
            )).scalar()
            assert org_id is not None
        for table in ('customers', 'sales', 'products', 'stores',
                      'activity_logs', 'sale_logs'):
            column = next(c for c in insp.get_columns(table)
                          if c['name'] == 'organization_id')
            assert column['nullable'] is False, table
    finally:
        eng.dispose()



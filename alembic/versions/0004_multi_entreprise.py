"""multi-entreprise : organizations + organization_id (nullable).

Revision ID: 0004_multi_entreprise
Revises: 0003_app_settings
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = '0004_multi_entreprise'
down_revision: Union[str, Sequence[str], None] = '0003_app_settings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES_WITH_ORG = (
    'customers', 'suppliers', 'products', 'stores', 'sales',
    'sale_items', 'payments', 'sale_returns', 'sale_return_items',
    'proforma_invoices', 'proforma_invoice_items',
    'inventory_movements', 'stock_alerts', 'purchase_orders',
    'purchase_order_items', 'treasury_accounts', 'treasury_movements',
    'cash_register_sessions', 'monthly_closures', 'activity_logs',
    'sale_logs', 'app_settings',
)

# Index composites PAR ENTREPRISE : deux entreprises peuvent reutiliser le
# meme code / numero. (table, nom_index, colonnes, unique).
ORG_UNIQUE_INDEXES = (
    ('customers', 'ix_customers_org_code', ['organization_id', 'code'], True),
    ('customers', 'ix_customers_org_email', ['organization_id', 'email'], True),
    ('suppliers', 'ix_suppliers_org_code', ['organization_id', 'code'], True),
    ('products', 'ix_products_org_code', ['organization_id', 'code'], True),
    ('products', 'ix_products_org_barcode', ['organization_id', 'barcode'], True),
    ('stores', 'ix_stores_org_code', ['organization_id', 'code'], True),
    ('sales', 'ix_sales_org_sale_number', ['organization_id', 'sale_number'], True),
    ('sale_returns', 'ix_sale_returns_org_return_number',
     ['organization_id', 'return_number'], True),
    ('proforma_invoices', 'ix_proforma_invoices_org_proforma_number',
     ['organization_id', 'proforma_number'], True),
    ('purchase_orders', 'ix_purchase_orders_org_order_number',
     ['organization_id', 'order_number'], True),
    ('monthly_closures', 'ix_monthly_closures_org_period',
     ['organization_id', 'period'], True),
    ('organization_members', 'ix_organization_members_user_id', ['user_id'], False),
    ('organization_members', 'ix_organization_members_organization_id',
     ['organization_id'], False),
)

# Anciennes unicites GLOBALES a retirer sur PostgreSQL (elles interdiraient
# deux entreprises partagent un meme code). Ordres IF EXISTS : ne levent
# jamais d'erreur (un echec en transaction PostgreSQL annulerait toute la
# migration, d'ou l'absence de try/except ici).
LEGACY_PG_DROPS = (
    "ALTER TABLE products DROP CONSTRAINT IF EXISTS products_barcode_key",
    "ALTER TABLE purchase_orders DROP CONSTRAINT IF EXISTS"
    " purchase_orders_order_number_key",
    "ALTER TABLE monthly_closures DROP CONSTRAINT IF EXISTS"
    " monthly_closures_period_key",
    "ALTER TABLE customers DROP CONSTRAINT IF EXISTS customers_email_key",
    "DROP INDEX IF EXISTS ix_products_code",
    "DROP INDEX IF EXISTS ix_products_barcode",
    "DROP INDEX IF EXISTS ix_customers_code",
    "DROP INDEX IF EXISTS ix_customers_email",
    "DROP INDEX IF EXISTS ix_stores_code",
    "DROP INDEX IF EXISTS ix_sales_sale_number",
    "DROP INDEX IF EXISTS ix_sale_returns_return_number",
    "DROP INDEX IF EXISTS ix_proforma_invoices_proforma_number",
    "DROP INDEX IF EXISTS ix_purchase_orders_order_number",
    "DROP INDEX IF EXISTS ix_monthly_closures_period",
    "DROP INDEX IF EXISTS ix_suppliers_code",
)

# Index simples NON UNIQUES attendus par les modeles (recrees apres le DROP
# des anciennes unicites globales ci-dessus). (table, nom, colonnes).
SIMPLE_INDEXES = (
    ('products', 'ix_products_code', ['code']),
    ('products', 'ix_products_barcode', ['barcode']),
    ('customers', 'ix_customers_code', ['code']),
    ('customers', 'ix_customers_email', ['email']),
    ('stores', 'ix_stores_code', ['code']),
    ('sales', 'ix_sales_sale_number', ['sale_number']),
    ('sale_returns', 'ix_sale_returns_return_number', ['return_number']),
    ('proforma_invoices', 'ix_proforma_invoices_proforma_number',
     ['proforma_number']),
    ('purchase_orders', 'ix_purchase_orders_order_number', ['order_number']),
    ('monthly_closures', 'ix_monthly_closures_period', ['period']),
    ('suppliers', 'ix_suppliers_code', ['code']),
)


def _cols(bind, table):
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return None
    return {c['name'] for c in insp.get_columns(table)}


def _index_names(bind, table):
    return {i['name'] for i in sa.inspect(bind).get_indexes(table)}


def _pg_constraint_exists(bind, name):
    return bind.execute(
        sa.text("SELECT 1 FROM pg_constraint WHERE conname = :n"),
        {"n": name},
    ).fetchone() is not None


def _pg_add_auth_fks(bind):
    """Rattache organization_members a Supabase Auth (PostgreSQL uniquement).

    Le schema `auth` n'existe ni sous SQLite (dev/tests) ni dans le metadata
    ORM : ces FK sont donc posees ici en SQL brut, avec garde d'existence
    (sans try/except : un echec annulerait la transaction PostgreSQL).
    """
    for name, ddl in (
        ('fk_organization_members_user_id',
         'ALTER TABLE organization_members ADD CONSTRAINT'
         ' fk_organization_members_user_id FOREIGN KEY (user_id)'
         ' REFERENCES auth.users (id) ON DELETE CASCADE'),
        ('fk_organization_members_invited_by',
         'ALTER TABLE organization_members ADD CONSTRAINT'
         ' fk_organization_members_invited_by FOREIGN KEY (invited_by)'
         ' REFERENCES auth.users (id) ON DELETE SET NULL'),
    ):
        if not _pg_constraint_exists(bind, name):
            bind.execute(sa.text(ddl))


def _add_org_fk(bind, table):
    """FK table.organization_id -> organizations.id (idempotente)."""
    name = f'fk_{table}_organization_id'
    if bind.dialect.name == 'postgresql':
        if _pg_constraint_exists(bind, name):
            return
    try:
        with op.batch_alter_table(table) as b:
            b.create_foreign_key(
                name, 'organizations',
                ['organization_id'], ['id'], ondelete='SET NULL')
    except Exception:
        if bind.dialect.name == 'postgresql':
            raise


def _create_org_unique_indexes(bind):
    """Cree les index composites par entreprise manquants (idempotent)."""
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    for table, name, columns, unique in ORG_UNIQUE_INDEXES:
        if table not in tables:
            continue
        cols = {c['name'] for c in insp.get_columns(table)}
        if not all(c in cols for c in columns):
            continue
        if name in _index_names(bind, table):
            continue
        try:
            op.create_index(name, table, columns, unique=unique)
        except Exception:
            if bind.dialect.name == 'postgresql':
                raise


def _pg_drop_legacy_uniques(bind):
    """Retire les unicites globales (PostgreSQL) et recree du simple."""
    for stmt in LEGACY_PG_DROPS:
        bind.execute(sa.text(stmt))
    tables = set(sa.inspect(bind).get_table_names())
    for table, name, columns in SIMPLE_INDEXES:
        if table not in tables or name in _index_names(bind, table):
            continue
        bind.execute(sa.text(
            f'CREATE INDEX "{name}" ON "{table}" ("{columns[0]}")'))


def _pg_add_app_settings_unique(bind):
    if not _pg_constraint_exists(bind, 'uq_app_settings_organization'):
        bind.execute(sa.text(
            "ALTER TABLE app_settings ADD CONSTRAINT"
            " uq_app_settings_organization UNIQUE (organization_id)"))


def upgrade() -> None:
    from core.database import Base
    import core.models.organization  # noqa: F401
    import core.models.customer  # noqa: F401
    import core.models.store  # noqa: F401
    import core.models.stock_models  # noqa: F401
    import core.models.sale_models  # noqa: F401
    import core.models.treasury_models  # noqa: F401
    import core.models.activity_log  # noqa: F401
    import core.models.sale_log  # noqa: F401
    import core.models.app_setting  # noqa: F401
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, tables=[
        Base.metadata.tables['organizations'],
        Base.metadata.tables['organization_members'],
    ])
    dialect = bind.dialect.name
    if dialect == 'postgresql':
        _pg_add_auth_fks(bind)
    for table in TABLES_WITH_ORG:
        cols = _cols(bind, table)
        if cols is None:
            continue
        if 'organization_id' not in cols:
            with op.batch_alter_table(table) as b:
                b.add_column(sa.Column('organization_id', sa.Uuid(), nullable=True))
                b.create_index(f'ix_{table}_organization_id', ['organization_id'])
            _add_org_fk(bind, table)
    if dialect == 'postgresql':
        _pg_drop_legacy_uniques(bind)
    # Build composite uniques only after removing old global constraints.
    # They are initially permissive for NULL organization_id, then enforced
    # once 0005 assigns the legacy rows to their organization.
    _create_org_unique_indexes(bind)
    if dialect == 'postgresql':
        _pg_add_app_settings_unique(bind)
    try:
        Base.metadata.create_all(bind=bind)
    except Exception:
        pass


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        # Ordres IF EXISTS : aucun ne leve, la transaction reste saine.
        for _t, name, _c, _u in ORG_UNIQUE_INDEXES:
            bind.execute(sa.text(f'DROP INDEX IF EXISTS "{name}"'))
        for _t, name, _c in SIMPLE_INDEXES:
            bind.execute(sa.text(f'DROP INDEX IF EXISTS "{name}"'))
        bind.execute(sa.text(
            "ALTER TABLE app_settings DROP CONSTRAINT IF EXISTS"
            " uq_app_settings_organization"))
        for table in TABLES_WITH_ORG:
            bind.execute(sa.text(
                f'ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS'
                f' "fk_{table}_organization_id"'))
        for table in TABLES_WITH_ORG:
            bind.execute(sa.text(
                f'ALTER TABLE "{table}" DROP COLUMN IF EXISTS'
                ' "organization_id"'))
        bind.execute(sa.text(
            "ALTER TABLE organization_members DROP CONSTRAINT IF EXISTS"
            " fk_organization_members_user_id"))
        bind.execute(sa.text(
            "ALTER TABLE organization_members DROP CONSTRAINT IF EXISTS"
            " fk_organization_members_invited_by"))
        bind.execute(sa.text("DROP TABLE IF EXISTS organization_members"))
        bind.execute(sa.text("DROP TABLE IF EXISTS organizations"))
        return
    for table in reversed(TABLES_WITH_ORG):
        if _cols(bind, table) is None:
            continue
        for action in ('fk', 'ix', 'col'):
            try:
                with op.batch_alter_table(table) as b:
                    if action == 'fk':
                        b.drop_constraint(
                            f'fk_{table}_organization_id',
                            type_='foreignkey')
                    elif action == 'ix':
                        b.drop_index(f'ix_{table}_organization_id')
                    else:
                        b.drop_column('organization_id')
            except Exception:
                pass
    for table, name, _c, _u in ORG_UNIQUE_INDEXES:
        try:
            op.drop_index(name, table_name=table)
        except Exception:
            pass
    for t in ('organization_members', 'organizations'):
        try:
            op.drop_table(t)
        except Exception:
            pass

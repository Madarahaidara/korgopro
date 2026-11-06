"""backfill organization : rattache l'existant, refuse si ambigu.

Revision ID: 0005_backfill_organization
Revises: 0004_multi_entreprise
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = '0005_backfill_organization'
down_revision: Union[str, Sequence[str], None] = '0004_multi_entreprise'
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

# A 0004 composite unique index permits duplicates while organization_id is
# NULL. Assigning every legacy row to one organization would make such
# duplicates collide, so detect them before changing any data.
LEGACY_UNIQUE_COLUMNS = (
    ('customers', 'code'), ('customers', 'email'),
    ('suppliers', 'code'), ('products', 'code'), ('products', 'barcode'),
    ('stores', 'code'), ('sales', 'sale_number'),
    ('sale_returns', 'return_number'),
    ('proforma_invoices', 'proforma_number'),
    ('purchase_orders', 'order_number'), ('monthly_closures', 'period'),
)


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    names = set(insp.get_table_names())
    if 'organizations' not in names:
        raise RuntimeError('0004 non appliquee : table organizations absente.')
    existing = bind.execute(sa.text(
        'SELECT id FROM organizations LIMIT 1')).fetchone()
    if existing is not None:
        # Rejouable : verifie qu'il ne reste aucun NULL puis sort.
        left = 0
        for table in TABLES_WITH_ORG:
            if table not in names:
                continue
            cols = {c['name'] for c in insp.get_columns(table)}
            if 'organization_id' not in cols:
                continue
            left += bind.execute(sa.text(
                f'SELECT COUNT(*) FROM "{table}"'
                ' WHERE organization_id IS NULL')).scalar() or 0
        if left:
            raise RuntimeError(
                f'{left} ligne(s) sans organization_id alors qu\'une '
                'organisation existe deja : rattachement manuel requis.')
        return
    # Table vide de production neuve : rien a rattacher.
    total = 0
    for table in TABLES_WITH_ORG:
        if table not in names:
            continue
        cols = {c['name'] for c in insp.get_columns(table)}
        if 'organization_id' not in cols:
            continue
        total += bind.execute(
            sa.text(f'SELECT COUNT(*) FROM "{table}"')).scalar() or 0
    if total == 0:
        return
    if 'app_settings' in names:
        settings_count = bind.execute(
            sa.text('SELECT COUNT(*) FROM app_settings')).scalar() or 0
        if settings_count > 1:
            raise RuntimeError(
                f'{settings_count} lignes app_settings : une seule ligne '
                'historique peut etre rattachee automatiquement.')
    for table, column in LEGACY_UNIQUE_COLUMNS:
        if table not in names:
            continue
        cols = {c['name'] for c in insp.get_columns(table)}
        if column not in cols:
            continue
        duplicate = bind.execute(sa.text(
            f'SELECT "{column}" FROM "{table}" '
            f'WHERE "{column}" IS NOT NULL GROUP BY "{column}" '
            'HAVING COUNT(*) > 1 LIMIT 1')).fetchone()
        if duplicate is not None:
            raise RuntimeError(
                f"Doublon historique dans {table}.{column} "
                f"({duplicate[0]!r}) : corriger avant le backfill 0005.")
    # L'id est genere en Python : aucun server_default sur Uuid, et le defaut
    # ORM (uuid4) ne s'applique pas au SQL brut. str(uuid) canonique
    # (avec tirets) : accepte par PostgreSQL (type uuid natif) comme par
    # SQLite (CHAR(32) flexible, stocke 36 car. sans erreur).
    import uuid as _uuid
    org_id = _uuid.uuid4()
    org_id_str = str(org_id)
    bind.execute(
        sa.text(
            "INSERT INTO organizations (id, name, code, country, currency,"
            " active, subscription_plan) VALUES"
            " (:id, 'Korgo Pro - Donnees existantes', 'KORGO-DEFAULT',"
            " 'BJ', 'FCFA', TRUE, 'free')"),
        {"id": org_id_str},
    )
    for table in TABLES_WITH_ORG:
        if table not in names:
            continue
        cols = {c['name'] for c in insp.get_columns(table)}
        if 'organization_id' not in cols:
            continue
        bind.execute(
            sa.text(f'UPDATE "{table}" SET organization_id = :oid'
                    ' WHERE organization_id IS NULL'),
            {'oid': org_id_str})
    for table in TABLES_WITH_ORG:
        if table not in names:
            continue
        cols = {c['name'] for c in insp.get_columns(table)}
        if 'organization_id' not in cols:
            continue
        left = bind.execute(sa.text(
            f'SELECT COUNT(*) FROM "{table}"'
            ' WHERE organization_id IS NULL')).scalar() or 0
        if left:
            raise RuntimeError(
                f"{left} ligne(s) de '{table}' sans organization_id : "
                'migration interrompue.')


def downgrade() -> None:
    pass  # Backfill non reversible : restaurer depuis sauvegarde.

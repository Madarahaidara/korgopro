"""organization_id NOT NULL apres backfill valide.

Revision ID: 0006_organization_id_required
Revises: 0005_backfill_organization
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = '0006_organization_id_required'
down_revision: Union[str, Sequence[str], None] = '0005_backfill_organization'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# app_settings garde NULL autorise : la ligne historique id=1 recoit son
# organization_id via le backfill mais le JSON reste partage en transition.
TABLES_NOT_NULL = (
    'customers', 'suppliers', 'products', 'stores', 'sales',
    'sale_items', 'payments', 'sale_returns', 'sale_return_items',
    'proforma_invoices', 'proforma_invoice_items',
    'inventory_movements', 'stock_alerts', 'purchase_orders',
    'purchase_order_items', 'treasury_accounts', 'treasury_movements',
    'cash_register_sessions', 'monthly_closures', 'activity_logs',
    'sale_logs',
)


def upgrade() -> None:
    bind = op.get_bind()
    names = set(sa.inspect(bind).get_table_names())
    for table in TABLES_NOT_NULL:
        if table not in names:
            continue
        left = bind.execute(sa.text(
            f'SELECT COUNT(*) FROM "{table}"'
            ' WHERE organization_id IS NULL')).scalar() or 0
        if left:
            raise RuntimeError(
                f"{left} ligne(s) de '{table}' sans organization_id : "
                'executer 0005 avant 0006.')
        with op.batch_alter_table(table) as b:
            b.alter_column('organization_id', existing_type=sa.Uuid(),
                             nullable=False)


def downgrade() -> None:
    bind = op.get_bind()
    names = set(sa.inspect(bind).get_table_names())
    for table in TABLES_NOT_NULL:
        if table not in names:
            continue
        with op.batch_alter_table(table) as b:
            b.alter_column('organization_id', existing_type=sa.Uuid(),
                             nullable=True)

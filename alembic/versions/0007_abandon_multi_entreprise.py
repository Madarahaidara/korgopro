"""Abandon du système multi-entreprise : organization_id redevient nullable.

Cette migration annule la contrainte NOT NULL imposée par la migration 0006
sur organization_id pour toutes les tables métier, notamment activity_logs.
"""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = '0007_abandon_multi_entreprise'
down_revision: Union[str, Sequence[str], None] = '0006_organization_id_required'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES_NULLABLE = (
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
    for table in TABLES_NULLABLE:
        if table not in names:
            continue
        with op.batch_alter_table(table) as b:
            b.alter_column('organization_id', existing_type=sa.Uuid(),
                             nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    names = set(sa.inspect(bind).get_table_names())
    for table in TABLES_NULLABLE:
        if table not in names:
            continue
        with op.batch_alter_table(table) as b:
            b.alter_column('organization_id', existing_type=sa.Uuid(),
                             nullable=False)
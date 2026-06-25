"""add proforma invoice tables

Revision ID: proforma_invoice_001
Revises: 92a3de20ce0e
Create Date: 2026-06-03 15:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'proforma_invoice_001'
down_revision = '92a3de20ce0e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create proforma_invoices table
    op.create_table(
        'proforma_invoices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('proforma_number', sa.String(50), nullable=False, unique=True),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_date', sa.DateTime(), nullable=True),
        sa.Column('valid_until', sa.DateTime(), nullable=True),
        sa.Column('subtotal', sa.Float(), nullable=False),
        sa.Column('discount_amount', sa.Float(), nullable=False),
        sa.Column('discount_percent', sa.Float(), nullable=False),
        sa.Column('tax_amount', sa.Float(), nullable=False),
        sa.Column('tax_percent', sa.Float(), nullable=False),
        sa.Column('total_amount', sa.Float(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('terms_and_conditions', sa.Text(), nullable=True),
        sa.Column('currency', sa.String(10), nullable=False),
        sa.Column('converted_to_sale_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['converted_to_sale_id'], ['sales.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('proforma_number')
    )
    op.create_index(op.f('ix_proforma_invoices_proforma_number'), 'proforma_invoices', ['proforma_number'], unique=True)
    
    # Create proforma_invoice_items table
    op.create_table(
        'proforma_invoice_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('proforma_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.String(255), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('unit_price', sa.Float(), nullable=False),
        sa.Column('discount_percent', sa.Float(), nullable=False),
        sa.Column('discount_amount', sa.Float(), nullable=False),
        sa.Column('line_total', sa.Float(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['proforma_id'], ['proforma_invoices.id']),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('proforma_invoice_items')
    op.drop_index(op.f('ix_proforma_invoices_proforma_number'), table_name='proforma_invoices')
    op.drop_table('proforma_invoices')

"""Add proforma and invoice fields

Revision ID: proforma_invoice_002
Revises: 92a3de20ce0e
Create Date: 2026-01-21

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'proforma_invoice_002'
down_revision = '92a3de20ce0e'
branch_labels = None
depends_on = None


def upgrade():
    # Create proforma_invoices table
    op.create_table(
        'proforma_invoices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('proforma_number', sa.String(50), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_date', sa.DateTime(), nullable=False),
        sa.Column('valid_until', sa.DateTime(), nullable=True),
        sa.Column('subtotal', sa.Float(), nullable=False),
        sa.Column('discount_amount', sa.Float(), nullable=True),
        sa.Column('discount_percent', sa.Float(), nullable=True),
        sa.Column('tax_amount', sa.Float(), nullable=True),
        sa.Column('tax_percent', sa.Float(), nullable=True),
        sa.Column('total_amount', sa.Float(), nullable=False),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('terms_and_conditions', sa.Text(), nullable=True),
        sa.Column('currency', sa.String(10), nullable=True),
        sa.Column('converted_to_sale_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['converted_to_sale_id'], ['sales.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_proforma_invoices_proforma_number'), 'proforma_invoices', ['proforma_number'], unique=True)
    op.create_index(op.f('ix_proforma_invoices_id'), 'proforma_invoices', ['id'], unique=False)

    # Create proforma_invoice_items table
    op.create_table(
        'proforma_invoice_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('proforma_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.String(255), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('unit_price', sa.Float(), nullable=False),
        sa.Column('discount_percent', sa.Float(), nullable=True),
        sa.Column('discount_amount', sa.Float(), nullable=True),
        sa.Column('line_total', sa.Float(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.ForeignKeyConstraint(['proforma_id'], ['proforma_invoices.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_proforma_invoice_items_id'), 'proforma_invoice_items', ['id'], unique=False)

    # Add new columns to sales table
    op.add_column('sales', sa.Column('type_document', sa.String(20), nullable=True, server_default='FACTURE'))
    op.add_column('sales', sa.Column('origine_proforma_id', sa.Integer(), nullable=True))
    op.add_column('sales', sa.Column('date_conversion', sa.DateTime(), nullable=True))
    op.add_column('sales', sa.Column('utilisateur_conversion', sa.Integer(), nullable=True))
    op.add_column('sales', sa.Column('statut', sa.String(20), nullable=True, server_default='BROUILLON'))
    op.add_column('sales', sa.Column('date_expiration', sa.DateTime(), nullable=True))
    op.add_column('sales', sa.Column('version', sa.Integer(), nullable=True, server_default='1'))

    # Create foreign keys for new columns
    op.create_foreign_key('fk_sales_origine_proforma', 'sales', 'proforma_invoices', ['origine_proforma_id'], ['id'])
    op.create_foreign_key('fk_sales_utilisateur_conversion', 'sales', 'users', ['utilisateur_conversion'], ['id'])


def downgrade():
    # Remove foreign keys
    op.drop_constraint('fk_sales_origine_proforma', 'sales', type_='foreignkey')
    op.drop_constraint('fk_sales_utilisateur_conversion', 'sales', type_='foreignkey')

    # Remove columns from sales table
    op.drop_column('sales', 'version')
    op.drop_column('sales', 'date_expiration')
    op.drop_column('sales', 'statut')
    op.drop_column('sales', 'utilisateur_conversion')
    op.drop_column('sales', 'date_conversion')
    op.drop_column('sales', 'origine_proforma_id')
    op.drop_column('sales', 'type_document')

    # Drop proforma_invoice_items table
    op.drop_index(op.f('ix_proforma_invoice_items_id'), table_name='proforma_invoice_items')
    op.drop_table('proforma_invoice_items')

    # Drop proforma_invoices table
    op.drop_index(op.f('ix_proforma_invoices_id'), table_name='proforma_invoices')
    op.drop_index(op.f('ix_proforma_invoices_proforma_number'), table_name='proforma_invoices')
    op.drop_table('proforma_invoices')
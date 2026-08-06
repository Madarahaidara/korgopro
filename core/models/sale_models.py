# core/models/sale_models.py (version mise à jour)
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base
from core.models.customer import Customer
from core.models.sale_log import SaleLog
from core.models.stock_models import Product

class Sale(Base):
    """Modèle pour les factures définitives"""
    __tablename__ = "sales"
    
    id = Column(Integer, primary_key=True, index=True)
    sale_number = Column(String(50), unique=True, index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=True)
    cashier_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    sale_date = Column(DateTime, default=func.now())
    subtotal = Column(Float, nullable=False, default=0)
    discount_amount = Column(Float, default=0)
    tax_amount = Column(Float, default=0)
    total_amount = Column(Float, nullable=False, default=0)
    amount_paid = Column(Float, default=0)
    change_amount = Column(Float, default=0)
    payment_method = Column(String(50), default="CASH")
    payment_status = Column(String(20), default="PENDING")
    sale_status = Column(String(20), default="COMPLETED")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    currency = Column(String(10), default="FCFA")
    
    # Nouveaux champs pour facture définitive
    type_document = Column(String(20), default="FACTURE")  # FACTURE, AVOIR
    origine_proforma_id = Column(Integer, ForeignKey('proforma_invoices.id'), nullable=True)
    date_conversion = Column(DateTime, nullable=True)
    utilisateur_conversion = Column(Integer, ForeignKey('users.id'), nullable=True)
    statut = Column(String(20), default="BROUILLON")  # BROUILLON, EMISE, PARTIELLEMENT_PAYEE, PAYEE, EN_RETARD, ANNULEE
    date_expiration = Column(DateTime, nullable=True)
    version = Column(Integer, default=1)
    
    # Relations
    customer = relationship("Customer", backref="sales")
    cashier = relationship("User", backref="ventes_caisse", foreign_keys=[cashier_id])
    items = relationship("SaleItem", backref="sale", cascade="all, delete-orphan")
    logs = relationship("core.models.sale_log.SaleLog", backref="sale", cascade="all, delete-orphan")
    # Lien vers la proforma source (relation unidirectionnelle)
    origine_proforma = relationship("ProformaInvoice", foreign_keys=[origine_proforma_id])
    utilisateur_conversion_rel = relationship("User", backref="ventes_converties", foreign_keys=[utilisateur_conversion])
    
    @property
    def profit(self):
        """Calcul du profit de la vente"""
        total_profit = 0
        for item in self.items:
            if item.product:
                profit_per_unit = item.product.sale_price - item.product.purchase_price
                total_profit += profit_per_unit * item.quantity
        return total_profit
    
    def __repr__(self):
        return f"<Sale {self.sale_number}>"


class SaleItem(Base):
    """Modèle pour les articles vendus"""
    __tablename__ = "sale_items"
    
    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey('sales.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    quantity = Column(Float, nullable=False, default=1)
    unit_price = Column(Float, nullable=False)
    discount_percent = Column(Float, default=0)
    discount_amount = Column(Float, default=0)
    line_total = Column(Float, nullable=False)
    notes = Column(Text, nullable=True)
    
    # Relations
    product = relationship("Product", backref="sale_items")
    
    @property
    def profit(self):
        """Profit sur cette ligne"""
        if self.product:
            profit_per_unit = self.product.sale_price - self.product.purchase_price
            return profit_per_unit * self.quantity
        return 0
    
    def __repr__(self):
        return f"<SaleItem {self.product_id} x {self.quantity}>"


class Payment(Base):
    """Modèle pour les paiements"""
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey('sales.id', ondelete='CASCADE'), nullable=False)
    amount = Column(Float, nullable=False)
    payment_method = Column(String(50), nullable=False)
    transaction_id = Column(String(100), nullable=True)
    reference = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    payment_date = Column(DateTime, default=func.now())
    collected_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Relations
    sale = relationship("Sale", backref="payments")
    collector = relationship("User", backref="collected_payments")
    
    def __repr__(self):
        return f"<Payment {self.amount} - {self.payment_method}>"


class SaleReturn(Base):
    """Modèle pour les retours de vente"""
    __tablename__ = "sale_returns"
    
    id = Column(Integer, primary_key=True, index=True)
    return_number = Column(String(50), unique=True, index=True, nullable=False)
    sale_id = Column(Integer, ForeignKey('sales.id'), nullable=False)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=True)
    return_date = Column(DateTime, default=func.now())
    total_amount = Column(Float, nullable=False, default=0)
    reason = Column(String(200), nullable=True)
    notes = Column(Text, nullable=True)
    processed_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    status = Column(String(20), default="PENDING")
    created_at = Column(DateTime, default=func.now())
    
    # Relations
    sale = relationship("Sale", backref="returns")
    customer = relationship("Customer", backref="returns")
    processor = relationship("User", backref="processed_returns")
    items = relationship("SaleReturnItem", backref="sale_return", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<SaleReturn {self.return_number}>"


class SaleReturnItem(Base):
    """Modèle pour les articles retournés"""
    __tablename__ = "sale_return_items"
    
    id = Column(Integer, primary_key=True, index=True)
    return_id = Column(Integer, ForeignKey('sale_returns.id'), nullable=False)
    sale_item_id = Column(Integer, ForeignKey('sale_items.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    quantity = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)
    refund_amount = Column(Float, nullable=False)
    reason = Column(String(200), nullable=True)
    notes = Column(Text, nullable=True)
    
    # Relations
    sale_item = relationship("SaleItem", backref="returns")
    product = relationship("Product", backref="return_items")
    
    def __repr__(self):
        return f"<SaleReturnItem {self.product_id} x {self.quantity}>"


class ProformaInvoice(Base):
    """Modèle pour les factures proforma (devis)"""
    __tablename__ = "proforma_invoices"
    
    id = Column(Integer, primary_key=True, index=True)
    proforma_number = Column(String(50), unique=True, index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=True)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_date = Column(DateTime, default=func.now())
    valid_until = Column(DateTime, nullable=True)
    subtotal = Column(Float, nullable=False, default=0)
    discount_amount = Column(Float, default=0)
    discount_percent = Column(Float, default=0)
    tax_amount = Column(Float, default=0)
    tax_percent = Column(Float, default=0)
    total_amount = Column(Float, nullable=False, default=0)
    status = Column(String(20), default="BROUILLON")  # BROUILLON, EN_ATTENTE, ENVOYEE, ACCEPTEE, REFUSEE, EXPIREE, CONVERTIE
    notes = Column(Text, nullable=True)
    terms_and_conditions = Column(Text, nullable=True)
    currency = Column(String(10), default="FCFA")
    converted_to_sale_id = Column(Integer, ForeignKey('sales.id'), nullable=True)
    
    # Relations
    customer = relationship("Customer", backref="proforma_invoices")
    creator = relationship("User", backref="created_proforma_invoices")
    items = relationship("ProformaInvoiceItem", backref="proforma_invoice", cascade="all, delete-orphan")
    # La vente issue de cette proforma (relation unidirectionnelle)
    vente_issue = relationship("Sale", foreign_keys=[converted_to_sale_id])


class ProformaInvoiceItem(Base):
    """Modèle pour les articles dans une facture proforma"""
    __tablename__ = "proforma_invoice_items"
    
    id = Column(Integer, primary_key=True, index=True)
    proforma_id = Column(Integer, ForeignKey('proforma_invoices.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=True)
    description = Column(String(255), nullable=False)
    quantity = Column(Float, nullable=False, default=1)
    unit_price = Column(Float, nullable=False)
    discount_percent = Column(Float, default=0)
    discount_amount = Column(Float, default=0)
    line_total = Column(Float, nullable=False)
    notes = Column(Text, nullable=True)
    
    # Relations
    product = relationship("Product", backref="proforma_items")
    
    def __repr__(self):
        return f"<ProformaInvoiceItem {self.description} x {self.quantity}>"



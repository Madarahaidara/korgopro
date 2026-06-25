from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base
from core.models.customer import Customer

class Product(Base):
    """Modèle pour les produits"""
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    category = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    quantity = Column(Integer, default=0)
    min_stock = Column(Integer, default=5)
    max_stock = Column(Integer, default=100)
    purchase_price = Column(Float, nullable=False)
    sale_price = Column(Float, nullable=False)
    supplier_id = Column(Integer, ForeignKey('suppliers.id'), nullable=True)
    location = Column(String(100), nullable=True)
    barcode = Column(String(50), nullable=True, unique=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relations
    supplier = relationship("Supplier", backref="products")
    
    @property
    def stock_value(self):
        """Valeur totale du stock"""
        return self.quantity * self.purchase_price
    
    @property
    def profit_margin(self):
        """Marge de profit en pourcentage"""
        if self.purchase_price > 0:
            return ((self.sale_price - self.purchase_price) / self.purchase_price) * 100
        return 0
    
    @property
    def profit_per_unit(self):
        """Profit par unité"""
        return self.sale_price - self.purchase_price
    
    @property
    def total_potential_profit(self):
        """Profit potentiel total"""
        return self.quantity * self.profit_per_unit
    
    @property
    def is_low_stock(self):
        """Vérifier si le stock est bas"""
        return self.quantity <= self.min_stock and self.active
    
    @property
    def is_out_of_stock(self):
        """Vérifier si le produit est en rupture"""
        return self.quantity <= 0 and self.active
    
    def __repr__(self):
        return f"<Product {self.code} - {self.name}>"

class Supplier(Base):
    """Modèle pour les fournisseurs"""
    __tablename__ = "suppliers"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True)
    name = Column(String(200), nullable=False)
    contact_person = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    website = Column(String(200), nullable=True)
    notes = Column(Text, nullable=True)
    payment_terms = Column(String(100), nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Supplier {self.code} - {self.name}>"

class InventoryMovement(Base):
    """Modèle pour les mouvements de stock"""
    __tablename__ = "inventory_movements"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    movement_type = Column(String(20), nullable=False)  # IN, OUT, ADJUST, LOSS, RETURN
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=True)
    total_value = Column(Float, nullable=True)
    reference = Column(String(100), nullable=True)  # Numéro de facture, commande, etc.
    reason = Column(String(200), nullable=True)  # Raison du mouvement
    notes = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    date = Column(DateTime, default=func.now())
    created_at = Column(DateTime, default=func.now())
    
    # Relations
    product = relationship("Product", backref="movements")
    user = relationship("User", backref="inventory_movements")
    
    def __repr__(self):
        return f"<Movement {self.movement_type} - {self.quantity} units>"

class ExpenseCategory(Base):
    """Modèle pour les catégories de dépenses"""
    __tablename__ = "expense_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    
    def __repr__(self):
        return f"<ExpenseCategory {self.name}>"

class Expense(Base):
    """Modèle pour les dépenses"""
    __tablename__ = "expenses"
    
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey('expense_categories.id'), nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=False)
    payment_method = Column(String(50), nullable=True)  # CASH, BANK, MOBILE_MONEY
    reference = Column(String(100), nullable=True)  # Numéro de facture, reçu
    supplier_id = Column(Integer, ForeignKey('suppliers.id'), nullable=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    date = Column(DateTime, default=func.now())
    created_at = Column(DateTime, default=func.now())
    
    # Relations
    category = relationship("ExpenseCategory", backref="expenses")
    supplier = relationship("Supplier", backref="expenses")
    user = relationship("User", backref="expenses")
    
    def __repr__(self):
        return f"<Expense {self.description} - {self.amount}>"

class PurchaseOrder(Base):
    """Modèle pour les commandes d'achat"""
    __tablename__ = "purchase_orders"
    
    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(50), unique=True, nullable=False)
    supplier_id = Column(Integer, ForeignKey('suppliers.id'), nullable=False)
    status = Column(String(20), default="PENDING")  # PENDING, ORDERED, RECEIVED, CANCELLED
    total_amount = Column(Float, default=0)
    notes = Column(Text, nullable=True)
    expected_delivery = Column(DateTime, nullable=True)
    received_date = Column(DateTime, nullable=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relations
    supplier = relationship("Supplier", backref="purchase_orders")
    user = relationship("User", backref="purchase_orders")
    items = relationship("PurchaseOrderItem", backref="order", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<PurchaseOrder {self.order_number}>"

class PurchaseOrderItem(Base):
    """Modèle pour les articles d'une commande d'achat"""
    __tablename__ = "purchase_order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey('purchase_orders.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    received_quantity = Column(Integer, default=0)
    notes = Column(Text, nullable=True)
    
    # Relations
    product = relationship("Product", backref="purchase_order_items")
    
    def __repr__(self):
        return f"<PurchaseOrderItem {self.product_id} - {self.quantity}>"

class StockAlert(Base):
    """Modèle pour les alertes de stock"""
    __tablename__ = "stock_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    alert_type = Column(String(20), nullable=False)  # LOW_STOCK, OUT_OF_STOCK, EXPIRING
    threshold = Column(Integer, nullable=True)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    
    # Relations
    product = relationship("Product", backref="alerts")
    
    def __repr__(self):
        return f"<StockAlert {self.alert_type} - Product ID: {self.product_id}>"
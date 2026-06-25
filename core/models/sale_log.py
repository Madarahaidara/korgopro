# core/models/sale_log.py
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from core.database import Base

class SaleLog(Base):
    """Modèle pour la journalisation des ventes"""
    __tablename__ = "sale_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey('sales.id'), nullable=True)
    sale_number = Column(String(50), nullable=False)
    action = Column(String(50), nullable=False)  # CREATE, CANCEL, REFUND, PRINT
    user_id = Column(Integer, nullable=False)
    username = Column(String(50), nullable=False)
    user_role = Column(String(20), nullable=False)
    
    # Détails de la vente
    customer_id = Column(Integer, nullable=True)
    customer_name = Column(String(100), nullable=True)
    total_amount = Column(Float, nullable=False)
    payment_method = Column(String(50), nullable=True)
    
    # Détails supplémentaires
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=func.now())
    
    def __repr__(self):
        return f"<SaleLog {self.sale_number} - {self.action}>"
    
    def to_dict(self):
        """Convertir en dictionnaire"""
        return {
            'id': self.id,
            'sale_id': self.sale_id,
            'sale_number': self.sale_number,
            'action': self.action,
            'user_id': self.user_id,
            'username': self.username,
            'user_role': self.user_role,
            'customer_id': self.customer_id,
            'customer_name': self.customer_name,
            'total_amount': self.total_amount,
            'payment_method': self.payment_method,
            'details': self.details,
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
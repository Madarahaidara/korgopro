from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from core.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=True)  # Email optionnel
    role = Column(String(20), default="CAISSIER")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    last_login = Column(DateTime, nullable=True)
    last_ip = Column(String(45), nullable=True)  # Dernière adresse IP connue
    must_change_password = Column(Boolean, default=True)  # Forcer changement mot de passe
    
    def __repr__(self):
        return f"<User {self.username}>"
    
    def to_dict(self):
        """Convertir l'utilisateur en dictionnaire"""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "last_ip": self.last_ip,
            "must_change_password": self.must_change_password
        }
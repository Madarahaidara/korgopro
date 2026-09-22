from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from core.database import Base

class User(Base):
    """PROFIL applicatif d'un utilisateur.

    ATTENTION — ARCHITECTURE :
    Supabase Auth (auth.users) est la SOURCE DE VERITE des comptes : email,
    mot de passe et statut (bannissement) y vivent. Cette table ne contient
    que le PROFIL (username, role, active, must_change_password...) et est
    alimentee par le trigger PostgreSQL `on_auth_user_changed` a partir des
    metadonnees du compte Supabase Auth.

    `password_hash` est DEPRECIE : il n'est plus ecrit par l'application (il
    ne sert qu'au repli de developpement SQLite, sans Supabase). Toute
    ecriture de mot de passe passe par core.supabase_auth.
    """

    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    # DEPRECIE : toujours vide en production (voir docstring).
    password_hash = Column(String(255), nullable=True, default="")
    # Cle de liaison vers auth.users.email : Supabase Auth exige un email.
    email = Column(String(100), unique=True, index=True, nullable=False)
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
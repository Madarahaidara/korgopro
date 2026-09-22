# core/models/treasury_models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base
import enum


class AccountType(enum.Enum):
    CASH = "CASH"           # Caisse (espèces)
    BANK = "BANK"           # Compte bancaire
    MOBILE_MONEY = "MOBILE_MONEY"  # Mobile money


class MovementType(enum.Enum):
    IN = "IN"      # Entrée (recette)
    OUT = "OUT"    # Sortie (dépense)


class TreasuryAccount(Base):
    """Compte de trésorerie : caisse, banque, mobile money."""
    __tablename__ = "treasury_accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    account_type = Column(String(20), nullable=False, default="CASH")
    currency = Column(String(10), default="FCFA")
    initial_balance = Column(Float, default=0.0)
    current_balance = Column(Float, default=0.0)
    bank_name = Column(String(100), nullable=True)       # Pour type BANK
    account_number = Column(String(50), nullable=True)    # IBAN / numéro de compte
    phone_number = Column(String(30), nullable=True)      # Pour MOBILE_MONEY
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relations
    movements = relationship("TreasuryMovement", backref="account", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<TreasuryAccount {self.name} ({self.account_type})>"


class TreasuryMovement(Base):
    """Mouvement de trésorerie : entrée ou sortie sur un compte."""
    __tablename__ = "treasury_movements"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("treasury_accounts.id"), nullable=False)
    movement_type = Column(String(10), nullable=False)  # IN / OUT
    amount = Column(Float, nullable=False)
    date = Column(DateTime, default=func.now())
    reference = Column(String(100), nullable=True)       # N° facture, reçu, etc.
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)        # Ventes, Achat, Salaire, Loyer...
    reference_type = Column(String(50), nullable=True)   # SALE, EXPENSE, MANUAL, TRANSFER
    reference_id = Column(Integer, nullable=True)        # ID de la vente/dépense liée
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=func.now())

    # Relations
    user = relationship("User", backref="treasury_movements")

    def __repr__(self):
        return f"<TreasuryMovement {self.movement_type} {self.amount}>"


class MonthlyClosure(Base):
    """Clôture mensuelle des ventes : fige les totaux du mois en trésorerie."""
    __tablename__ = "monthly_closures"

    id = Column(Integer, primary_key=True, index=True)
    period = Column(String(7), unique=True, nullable=False)  # 'YYYY-MM'
    sales_count = Column(Integer, default=0)
    total_sales = Column(Float, default=0.0)          # somme total_amount
    total_collected = Column(Float, default=0.0)      # somme (amount_paid - change)
    total_credit = Column(Float, default=0.0)         # restant dû clients
    total_out = Column(Float, default=0.0)            # dépenses du mois
    net = Column(Float, default=0.0)                  # encaissé - dépenses
    balances = Column(Text, nullable=True)            # snapshot JSON des comptes
    status = Column(String(20), default="OPEN")       # OPEN / CLOSED
    closed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    closed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())

    def __repr__(self):
        return f"<MonthlyClosure {self.period} ({self.status})>"


class CashRegisterSession(Base):
    """Session de caisse : ouverture / fermeture avec contrôle des écarts."""
    __tablename__ = "cash_register_sessions"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("treasury_accounts.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    opened_at = Column(DateTime, default=func.now())
    closed_at = Column(DateTime, nullable=True)
    opening_amount = Column(Float, default=0.0)      # Montant en caisse à l'ouverture
    expected_amount = Column(Float, default=0.0)     # Montant théorique à la fermeture
    closing_amount = Column(Float, nullable=True)    # Montant réel compté
    difference = Column(Float, nullable=True)        # Écart (closing - expected)
    total_in = Column(Float, default=0.0)            # Total entrées pendant la session
    total_out = Column(Float, default=0.0)           # Total sorties pendant la session
    status = Column(String(20), default="OPEN")      # OPEN / CLOSED
    notes = Column(Text, nullable=True)

    # Relations
    account = relationship("TreasuryAccount", backref="sessions")
    user = relationship("User", backref="cash_sessions")

    def __repr__(self):
        return f"<CashRegisterSession {self.id} ({self.status})>"

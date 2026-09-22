# core/models/store.py
# ---------------------------------------------------------------------------
# Multi-magasins : chaque magasin possède son propre stock.
#
# Les entités de stock / vente portent une colonne `store_id` (nullable pour
# rester compatible avec les bases existantes) :
#   - products.store_id             : catalogue + quantités du magasin
#   - inventory_movements.store_id  : historique des mouvements du magasin
#   - sales.store_id                : ventes réalisées dans le magasin
#
# Les lignes historiques (store_id NULL) sont rattachées au magasin par défaut
# par core.store_manager.ensure_default_store().
# ---------------------------------------------------------------------------
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime
from sqlalchemy.sql import func

from core.database import Base


class Store(Base):
    """Un magasin (point de vente) gérant son propre stock."""

    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    address = Column(Text, nullable=True)
    phone = Column(String(50), nullable=True)
    manager_name = Column(String(150), nullable=True)
    notes = Column(Text, nullable=True)
    active = Column(Boolean, default=True)
    # Magasin par défaut : reçoit les données historiques (store_id NULL).
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Store {self.code} - {self.name}>"
# core/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Lire l'URL de la base depuis la variable d'environnement KORGO_DB_URL
# Exemple: sqlite:///korgo_pro.db  ou postgresql+psycopg2://user:pass@host/dbname
DATABASE_URL = os.environ.get("KORGO_DB_URL", "sqlite:///korgo_pro.db")

# Adapter connect_args uniquement pour SQLite (check_same_thread requirement)
connect_args = {}
if DATABASE_URL.startswith("sqlite:///"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args if connect_args else None,
)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

def init_database():
    """Initialiser la base de données et créer les tables"""
    Base.metadata.create_all(bind=engine)
    print("Base de données initialisée avec succès!")

def get_db():
    """Générateur de session pour les dépendances"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
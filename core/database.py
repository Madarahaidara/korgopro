# core/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///korgo_pro.db"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
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
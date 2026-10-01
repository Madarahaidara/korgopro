# core/database.py
# ---------------------------------------------------------------------------
# Configuration du moteur SQLAlchemy.
#
# App desktop KORGO PRO — la base était initialement SQLite locale
# ("korgo_pro.db"). Depuis la migration vers PostgreSQL / Supabase, la chaîne
# de connexion est lue depuis l'environnement :
#
#   DATABASE_URL = postgresql+psycopg2://...@<projet>.supabase.co:5432/postgres
#
# Options (voir .env.example) :
#   DATABASE_URL   chaîne de connexion SQLAlchemy (sinon repli SQLite local)
#   DATABASE_ECHO  "1" pour journaliser les requêtes SQL
#
# Supabase expose deux ports PostgreSQL :
#   - 5432 : connexion directe (session pooling)  --> RECOMMANDÉ pour SQLAlchemy
#   - 6543 : transaction pooling (PgBouncer)      --> interdit les statements
#             préparés, à réserver aux APIs/edge functions.
# Utilisez le port 5432 dans DATABASE_URL pour l'app desktop.
# ---------------------------------------------------------------------------
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Charger les variables d'environnement depuis .env (optionnel, sans panique)
try:  # pragma: no cover - dépendance optionnelle
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except Exception:  # python-dotenv non installé -> on lit seulement os.environ
    pass

# Chaîne de connexion principale. Default = SQLite locale (dev / tests / sécurité)
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///" + os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "korgo_pro.db",
    ).replace("\\", "/"),
)

_echo = os.environ.get("DATABASE_ECHO", "0") == "1"


def _create_engine(url: str):
    """Crée le moteur avec les options adaptées au dialecte (PostgreSQL vs SQLite)."""
    is_sqlite = url.startswith("sqlite")

    if is_sqlite:
        return create_engine(
            url,
            echo=_echo,
            connect_args={"check_same_thread": False},
        )

    # --- Garde-fous reseau (anti-gel de l'interface) -----------------------
    # Le desktop parle a PostgreSQL (Supabase) a travers Internet. Sans bornes,
    # une connexion perdue OU une requete qui attend un verrou cote serveur
    # bloque le thread appelant SANS LIMITE : libpq attend la retransmission
    # TCP de l'OS (21 s et plus) et PostgreSQL n'applique aucun delai maximal
    # par defaut. Chaque borne ci-dessous est configurable (.env.example).
    connect_timeout = int(os.environ.get("DB_CONNECT_TIMEOUT", "10"))
    statement_timeout = int(os.environ.get("DB_STATEMENT_TIMEOUT_MS", "60000"))

    connect_args = {
        "sslmode": os.environ.get("DB_SSLMODE", "require"),
        # Abandonne une connexion injoignable au lieu d'attendre Windows.
        "connect_timeout": connect_timeout,
        # Detecte les connexions coupees en silence par le pooler / le NAT
        # (mise en veille, changement de Wi-Fi) sans attendre la requete suivante.
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
    }
    if statement_timeout > 0:
        # 0 = desactive (a n'utiliser que pour une restauration/export massif).
        connect_args["options"] = f"-c statement_timeout={statement_timeout}"

    return create_engine(
        url,
        echo=_echo,
        pool_pre_ping=True,          # vérifie la connexion avant usage (réseau)
        pool_size=int(os.environ.get("DB_POOL_SIZE", "5")),
        max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "10")),
        # Le pooler Supabase ferme les connexions inactives : on recycle avant.
        pool_recycle=int(os.environ.get("DB_POOL_RECYCLE", "300")),
        # Ne jamais attendre indefiniment une connexion du pool.
        pool_timeout=int(os.environ.get("DB_POOL_TIMEOUT", "10")),
        connect_args=connect_args,
    )


engine = _create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()


def get_dialect_name() -> str:
    """Nom du dialecte actif ('sqlite', 'postgresql', ...)."""
    return engine.url.get_backend_name()

def init_database():
    """Initialiser la base de données et créer les tables"""
    from core.models import treasury_models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    print("Base de données initialisée avec succès!")

def get_db():
    """Générateur de session pour les dépendances"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
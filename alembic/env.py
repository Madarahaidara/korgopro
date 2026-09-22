from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Ajouter la racine du projet au sys.path de manière déterministe
import sys
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Charger les variables d'environnement depuis .env (même source que core/database.py)
import os
try:  # pragma: no cover - dépendance optionnelle
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except Exception:
    pass

# Utiliser LA vraie Base déclarative de l'application, et non une copie locale.
# Les modèles s'enregistrent sur core.database.Base ; sinon target_metadata
# serait vide et les migrations Alembic ne refléteraient pas le schéma réel.
from core.database import Base

# Importer TOUS les modèles pour peupler Base.metadata
# (y compris les modèles de trésorerie, absents avant).
from core.models import customer, user, activity_log, sale_log  # noqa: F401,E402
from core.models import sale_models  # noqa: F401,E402
from core.models import stock_models  # noqa: F401,E402
from core.models import treasury_models  # noqa: F401,E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Source de vérité pour l'URL : variable d'environnement DATABASE_URL,
# sinon la valeur sqlalchemy.url d'alembic.ini (repli SQLite).
_DBVAR = os.environ.get(
    "DATABASE_URL",
    config.get_main_option("sqlalchemy.url") or "sqlite:///korgo_pro.db",
)
config.set_main_option("sqlalchemy.url", _DBVAR)

# Interpréter la config pour le logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

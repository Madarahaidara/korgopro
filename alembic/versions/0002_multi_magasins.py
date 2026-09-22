"""multi-magasins

Revision ID: 0002_multi_magasins
Revises: 0001_baseline_schema
Create Date: 2026-09-14

Multi-magasins :
  1. crée la table `stores` ;
  2. ajoute la colonne `store_id` (nullable) à products, inventory_movements
     et sales ;
  3. insère un magasin « Magasin principal » (MAG-0001) ;
  4. rattache les données existantes (store_id NULL) à ce magasin.

Idempotent : chaque étape vérifie l'état courant, la migration peut donc être
rejouée (utile car `0001` crée déjà le schéma complet sur une base neuve).

Usage:
    alembic upgrade head      # contre la base cible (DATABASE_URL)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0002_multi_magasins'
down_revision: Union[str, Sequence[str], None] = '0001_baseline_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables qui référencent un magasin
TABLES_WITH_STORE = ("products", "inventory_movements", "sales")


def _columns(bind, table):
    """Noms des colonnes de `table`, ou None si la table n'existe pas."""
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return None
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    """Applique le multi-magasins (table + colonnes + magasin par défaut)."""
    # Import des modèles pour compléter Base.metadata (table `stores`).
    from core.database import Base
    import core.models.store  # noqa: F401
    import core.models.stock_models  # noqa: F401
    import core.models.sale_models  # noqa: F401

    bind = op.get_bind()

    # 1) Table `stores` : create_all() ne crée que les tables manquantes.
    Base.metadata.create_all(bind=bind)

    # 2) Colonnes store_id : create_all() ne modifie pas les tables existantes.
    for table in TABLES_WITH_STORE:
        columns = _columns(bind, table)
        if columns is None or "store_id" in columns:
            continue
        bind.execute(sa.text(f'ALTER TABLE "{table}" ADD COLUMN "store_id" INTEGER'))
        # Contrainte de clé étrangère (ALTER ... ADD CONSTRAINT non supporté par SQLite)
        try:
            bind.execute(sa.text(
                f'ALTER TABLE "{table}" ADD CONSTRAINT "fk_{table}_store" '
                'FOREIGN KEY ("store_id") REFERENCES "stores" ("id") ON DELETE SET NULL'
            ))
        except Exception:
            pass
        # Index pour accélérer le filtrage par magasin
        try:
            bind.execute(sa.text(
                f'CREATE INDEX IF NOT EXISTS "ix_{table}_store_id" '
                f'ON "{table}" ("store_id")'
            ))
        except Exception:
            pass

    # 3) Magasin par défaut
    existing = bind.execute(sa.text("SELECT id FROM stores ORDER BY id LIMIT 1")).fetchone()
    if existing is None:
        bind.execute(sa.text(
            "INSERT INTO stores (code, name, notes, active, is_default, created_at, updated_at) "
            "VALUES ('MAG-0001', 'Magasin principal', "
            "'Magasin créé automatiquement (multi-magasins).', TRUE, TRUE, "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ))

    # 4) Rattachement des données historiques
    default_id = bind.execute(sa.text(
        "SELECT id FROM stores ORDER BY is_default DESC, id LIMIT 1"
    )).scalar()
    if default_id is not None:
        for table in TABLES_WITH_STORE:
            columns = _columns(bind, table)
            if columns is None or "store_id" not in columns:
                continue
            bind.execute(
                sa.text(f'UPDATE "{table}" SET "store_id" = :sid WHERE "store_id" IS NULL'),
                {"sid": default_id},
            )


def downgrade() -> None:
    """Retire le multi-magasins (les données store_id sont perdues)."""
    bind = op.get_bind()
    for table in TABLES_WITH_STORE:
        columns = _columns(bind, table)
        if columns and "store_id" in columns:
            try:
                bind.execute(sa.text(f'ALTER TABLE "{table}" DROP COLUMN "store_id"'))
            except Exception:
                pass
    try:
        bind.execute(sa.text("DROP TABLE stores"))
    except Exception:
        pass
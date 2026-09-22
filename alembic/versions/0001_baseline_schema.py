"""baseline schema

Revision ID: 0001_baseline_schema
Revises: 
Create Date: 2026-09-08

Construit le schéma complet depuis les modèles ORM actuels (core.database.Base).
Destiné à une base PostgreSQL / Supabase vierge.

NOTE : l'historique alembic SQLite (< 1.0, multi-racine, ne créant que des
deltas sur un schéma construit par create_all) a été archivé dans
`alembic/versions/legacy_sqlite/`. Cette baseline le remplace pour les
nouvelles bases (Supabase).

Usage:
    alembic upgrade head          # contre la DB cible (DATABASE_URL)
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0001_baseline_schema'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crée toutes les tables d'après les modèles (idempotent)."""
    from core.database import Base
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    """Supprime toutes les tables du schéma applicatif."""
    from core.database import Base
    bind = op.get_bind()
    # Ordre inverse des dépendances sinon échec FK
    Base.metadata.drop_all(bind=bind)
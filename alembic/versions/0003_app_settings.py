"""app settings singleton

Revision ID: 0003_app_settings
Revises: 0002_multi_magasins
Create Date: 2026-10-14

Paramètres applicatifs centralisés sur Supabase : table « singleton »
``app_settings`` (une seule ligne, id = 1) contenant le dictionnaire complet
des réglages dans une colonne JSON/JSONB. Remplace/augmente le fichier local
``company_settings.json`` pour que desktop et web partagent la même source de
vérité (avec repli local).

Idempotent : ``create_all`` ne crée que la table manquante, puis on insère la
ligne singleton si absente.

Usage:
    alembic upgrade head      # contre la base cible (DATABASE_URL)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0003_app_settings'
down_revision: Union[str, Sequence[str], None] = '0002_multi_magasins'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crée la table ``app_settings`` et sa ligne singleton par défaut."""
    from core.database import Base
    import core.models.app_setting  # noqa: F401  (enregistre AppSetting sur Base)

    # create_all() ne crée que les tables absentes (idempotent).
    Base.metadata.create_all(bind=op.get_bind())

    # Ligne singleton : un dictionnaire vide au départ ; chaque plateforme la
    # remplit à sa première sauvegarde (merge shallow).
    bind = op.get_bind()
    exists = bind.execute(
        sa.text("SELECT id FROM app_settings WHERE id = 1")
    ).fetchone()
    if exists is None:
        bind.execute(
            sa.text("INSERT INTO app_settings (id, data) VALUES (1, :d)"),
            {"d": "{}"},
        )


def downgrade() -> None:
    """Supprime la table des paramètres (les réglages stockés sont perdus)."""
    bind = op.get_bind()
    try:
        bind.execute(sa.text("DROP TABLE IF EXISTS app_settings"))
    except Exception:
        pass

# core/models/app_setting.py
# ---------------------------------------------------------------------------
# Paramètres applicatifs (entreprise, facturation, préférences d'affichage).
#
# Table « singleton » : une seule ligne (id = 1) dont la colonne ``data``
# contient l'intégralité du dictionnaire de paramètres — mêmes clés que
# ``company_settings.json`` côté desktop et que ``db.data.settings`` côté web.
#
# Pourquoi un dictionnaire libre plutôt qu'une colonne par paramètre :
#   * les schémas diffèrent entre desktop (``company_name``, ``company_address``…)
#     et web (``company_name``, ``address``…) : une colonne par réglage imposerait
#     un mapping rigide et une migration de schéma à chaque nouveau paramètre ;
#   * le JSONB accepte l'union des deux schémas sans conflit, chaque plateforme
#     ne lisant/écrivant que les clés qu'elle connaît.
#
# Fusion sans écrasement : chaque écriture fait un merge « shallow » au niveau
# racine (``data = data || patch``), si bien qu'une plateforme n'écrase que les
# clés qu'elle définit et jamais celles de l'autre.
# ---------------------------------------------------------------------------
from sqlalchemy import Column, Integer, JSON, DateTime, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from core.database import Base

# JSONB sur PostgreSQL (indexable, opérateur de fusion ``||``), JSON sur SQLite
# (repli développement / tests — ``jsonb`` n'y existe pas).
_JSON = JSON().with_variant(JSONB(), "postgresql")


class AppSetting(Base):
    """Paramètres applicatifs — ligne unique (``id = 1``)."""

    __tablename__ = "app_settings"

    # Clé primaire fixée à 1 par une contrainte CHECK : la table ne décrit
    # jamais plus d'une ligne (paramètres globaux de l'application).
    id = Column(Integer, primary_key=True)
    # Dictionnaire libre des paramètres (voir note de module).
    data = Column(_JSON, nullable=False, default=dict)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_app_settings_singleton"),
    )

    def __repr__(self):
        return "<AppSetting>"

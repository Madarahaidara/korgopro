# core/models/organization.py
# ---------------------------------------------------------------------------
# MULTI-ENTREPRISES (multi-tenant).
#
#   * `organizations`          : une entreprise (UUID), identifiante des données ;
#   * `organization_members`   : rattachement utilisateur <-> entreprise, avec
#     un rôle PROPRE à chaque entreprise (un même compte Supabase Auth peut
#     appartenir à plusieurs entreprises).
#
# Conventions :
#   * les UUID utilisent `sqlalchemy.Uuid` : `uuid` natif sur PostgreSQL /
#     Supabase, CHAR(32) sous SQLite (repli développement et tests) ;
#   * `public.users` reste un PROFIL applicatif GLOBAL sans entreprise : la
#     clé de liaison vers Supabase Auth est `organization_members.user_id`
#     (`auth.users.id`) ;
#   * `organization_id` est NULLABLE à ce stade : il ne devient NOT NULL
#     (migration Alembic 0006) qu'après le backfill des données existantes
#     (0005) et l'intégration des clients (Phase 6). Les clients doivent
#     être déployiés APRÈS l'application de la migration 0004 (colonnes),
#     jamais avant.
#
# Rôles : même vocabulaire canonique que core.permissions.CANONICAL_ROLES
# (ADMIN, GESTIONNAIRE, SUPERVISEUR, ASSISTANT, CAISSIER).
# ---------------------------------------------------------------------------
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.sql import func

from core.database import Base

#: Ligne « entreprise héritée » créée par la migration 0005 pour les données
#: préexistantes au multi-entreprises (code unique, réutilisé par les tests).
LEGACY_ORGANIZATION_CODE = "KORGO-DEFAULT"

#: Rôles autorisés dans une organisation (miroir de core/permissions.py).
ORGANIZATION_ROLES = (
    "ADMIN",
    "GESTIONNAIRE",
    "SUPERVISEUR",
    "ASSISTANT",
    "CAISSIER",
)


def organization_id_column():
    """Colonne standard `organization_id` (nullable, indexée, FK -> organizations).

    Utilisée par TOUTES les tables métier (ventes, stock, clients, trésorerie…).
    `ON DELETE SET NULL` : la suppression d'une entreprise ne casse jamais de
    contrainte métier — ses lignes deviennent simplement invisibles (NULL n'est
    dans aucune liste d'organisations RLS). Après la migration 0006 (NOT NULL),
    la suppression d'une entreprise porteuse de données est refusée par la BDD :
    il faudra la désactiver plutôt que la supprimer.
    """
    return Column(
        "organization_id",
        Uuid,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


class Organization(Base):
    """Une entreprise cliente de Korgo Pro (tenant)."""

    __tablename__ = "organizations"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    code = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    # Devise / TVA par défaut de l'entreprise (FCFA = convention du projet).
    country = Column(String(100), nullable=True, default="BJ")
    currency = Column(String(10), nullable=True, default="FCFA")
    tax_rate = Column(Float, nullable=True, default=0.0)
    active = Column(Boolean, nullable=False, default=True)
    # Évolution future : licences / abonnements (free, pro, enterprise).
    subscription_plan = Column(String(50), nullable=True, default="free")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Organization {self.code} - {self.name}>"


class OrganizationMember(Base):
    """Rattachement d'un utilisateur Supabase Auth à une entreprise.

    - `user_id` : `auth.users.id` (UUID Supabase Auth) ;
    - `role`    : rôle de l'utilisateur DANS CETTE entreprise (unique par
      (user_id, organization_id)) ;
    - `active`  : permet de suspendre un membre sans toucher au compte.
    """

    __tablename__ = "organization_members"

    __table_args__ = (
        UniqueConstraint(
            "user_id", "organization_id", name="uq_organization_members_user_org"
        ),
        CheckConstraint(
            "role IN ('ADMIN','GESTIONNAIRE','SUPERVISEUR','ASSISTANT','CAISSIER')",
            name="ck_organization_members_role",
        ),
    )

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    # UUID du compte Supabase Auth (auth.users.id). PAS de ForeignKey ORM :
    # le schema `auth` n'existe ni sous SQLite (dev/tests) ni dans le
    # metadata ; la FK est posee par la migration 0004, uniquement sur
    # PostgreSQL (voir alembic/versions/0004_multi_entreprise.py).
    user_id = Column(Uuid, nullable=False, index=True)
    organization_id = Column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    role = Column(String(20), nullable=False, default="CAISSIER")
    active = Column(Boolean, nullable=False, default=True)
    # Parrain (auth.users.id) : meme remarque que user_id, sans FK ORM.
    invited_by = Column(Uuid, nullable=True)
    invited_at = Column(DateTime, nullable=True)
    joined_at = Column(DateTime, default=func.now())
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return (
            f"<OrganizationMember {self.user_id} -> {self.organization_id} "
            f"({self.role})>"
        )

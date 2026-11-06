# PLAN DE MIGRATION MULTI-ENTREPRISES — Korgo Pro

**Date :** 19/10/2026  
**Projet :** Korgo Pro  
**Statut :** Phase 2 — Conception du modèle multi-entreprises (aucun changement de base de production)  
**Prérequis :** Validation du rapport `docs/audit_multitenant.md`

---

## 1. MODÈLE DE DONNÉES CIBLE

### 1.1 Nouvelles tables

#### `organizations`

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Identifiant unique de l'entreprise |
| `name` | VARCHAR(200) | NOT NULL | Nom légal ou commercial de l'entreprise |
| `code` | VARCHAR(50) | UNIQUE, NOT NULL | Code court (ex. "KORGO-001") |
| `email` | VARCHAR(100) | NULLABLE | Email de contact de l'entreprise |
| `phone` | VARCHAR(50) | NULLABLE | Téléphone de contact |
| `address` | TEXT | NULLABLE | Adresse postale |
| `city` | VARCHAR(100) | NULLABLE | Ville |
| `country` | VARCHAR(100) | NULLABLE, DEFAULT 'BJ' | Pays (code ISO) |
| `currency` | VARCHAR(10) | NULLABLE, DEFAULT 'FCFA' | Devise par défaut |
| `tax_rate` | FLOAT | NULLABLE, DEFAULT 0 | Taux de TVA par défaut |
| `active` | BOOLEAN | NOT NULL, DEFAULT true | Entreprise active ou suspendue |
| `subscription_plan` | VARCHAR(50) | NULLABLE, DEFAULT 'free' | Plan d'abonnement (free, pro, enterprise) |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Date de création |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Date de dernière modification |

#### `organization_members`

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Identifiant unique de la liaison |
| `user_id` | UUID | NOT NULL, FK → auth.users(id) | Utilisateur Supabase Auth |
| `organization_id` | UUID | NOT NULL, FK → organizations(id) | Entreprise |
| `role` | VARCHAR(20) | NOT NULL, DEFAULT 'CAISSIER' | Rôle dans cette entreprise |
| `active` | BOOLEAN | NOT NULL, DEFAULT true | Membre actif ou suspendu |
| `invited_by` | UUID | NULLABLE, FK → auth.users(id) | Utilisateur qui a invité ce membre |
| `invited_at` | TIMESTAMPTZ | NULLABLE | Date d'invitation |
| `joined_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Date d'entrée effective |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Date de création de la liaison |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Date de dernière modification |

**Contraintes additionnelles :**
- UNIQUE(`user_id`, `organization_id`) — un utilisateur ne peut pas être deux fois membre de la même entreprise
- CHECK(role IN ('ADMIN','GESTIONNAIRE','SUPERVISEUR','ASSISTANT','CAISSIER'))

### 1.2 Tables commerciales recevant `organization_id`

Chaque table métier existante reçoit une colonne `organization_id` (UUID, nullable initialement, puis NOT NULL après backfill) avec une clé étrangère vers `organizations(id)` et un index.

Tables concernées :
- `customers`, `suppliers`, `products`, `stores`
- `sales`, `sale_items`, `sale_returns`, `sale_return_items`
- `proforma_invoices`, `proforma_invoice_items`
- `inventory_movements`, `stock_alerts`

## 2. MIGRATIONS ALEMBIC VERSIONNÉES

```python
"""multi-entreprise

Revision ID: 0004_multi_entreprise
Revises: 0003_app_settings
Create Date: 2026-10-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0004_multi_entreprise'
down_revision: Union[str, None] = '0003_app_settings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES_WITH_ORG = (
    'customers', 'suppliers', 'products', 'stores',
    'sales', 'sale_items', 'sale_returns', 'sale_return_items',
    'proforma_invoices', 'proforma_invoice_items',
    'inventory_movements', 'stock_alerts',
    'purchase_orders', 'purchase_order_items',
    'treasury_accounts', 'treasury_movements',
    'cash_register_sessions', 'monthly_closures',
    'activity_logs', 'sale_logs',
)

def upgrade() -> None:
    # 1) Table organizations
    op.create_table(
        'organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('country', sa.String(length=100), nullable=True, server_default='BJ'),
        sa.Column('currency', sa.String(length=10), nullable=True, server_default='FCFA'),
        sa.Column('tax_rate', sa.Float(), nullable=True, server_default='0'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('subscription_plan', sa.String(length=50), nullable=True, server_default='free'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_organizations_code'),
    )
    op.create_index('ix_organizations_active', 'organizations', ['active'])

    # 2) Table organization_members
    op.create_table(
        'organization_members',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False, server_default='CAISSIER'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('invited_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('invited_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'organization_id', name='uq_organization_members_user_org'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['auth.users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invited_by'], ['auth.users.id'], ondelete='SET NULL'),
        sa.CheckConstraint("role IN ('ADMIN','GESTIONNAIRE','SUPERVISEUR','ASSISTANT','CAISSIER')", name='ck_organization_members_role'),
    )
    op.create_index('ix_organization_members_organization_id', 'organization_members', ['organization_id'])
    op.create_index('ix_organization_members_user_id', 'organization_members', ['user_id'])
    op.create_index('ix_organization_members_active', 'organization_members', ['active'])

    # 3) Ajouter organization_id (nullable) aux tables métier
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in TABLES_WITH_ORG:
        if not inspector.has_table(table):
            continue
        columns = {col['name'] for col in inspector.get_columns(table)}
        if 'organization_id' in columns:
            continue
        op.add_column(table, sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True))
        op.create_index(f'ix_{table}_organization_id', table, ['organization_id'])
        try:
            op.create_foreign_key(
                f'fk_{table}_organization_id',
                table, 'organizations',
                ['organization_id'], ['id'],
                ondelete='SET NULL',
            )
        except Exception:
            pass

def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in reversed(TABLES_WITH_ORG):
        if not inspector.has_table(table):
            continue
        try:
            op.drop_constraint(f'fk_{table}_organization_id', table, type_='foreignkey')
        except Exception:
            pass
        try:
            op.drop_index(f'ix_{table}_organization_id', table_name=table)
        except Exception:
            pass
        try:
            op.drop_column(table, 'organization_id')
        except Exception:
            pass

### 2.2 Migration `0005_backfill_organization.py` (attribution des données existantes)

Cette migration doit être examinée et validée manuellement avant exécution sur production.

```python
"""backfill organization

Revision ID: 0005_backfill_organization
Revises: 0004_multi_entreprise
Create Date: 2026-10-19

Crée une organisation par défaut pour les données existantes
et rattache toutes les lignes dont organization_id est NULL.
REFUSE de poursuivre si l'attribution est ambiguë.
"""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = '0005_backfill_organization'
down_revision: Union[str, None] = '0004_multi_entreprise'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES_WITH_ORG = (
    'customers', 'suppliers', 'products', 'stores',
    'sales', 'sale_items', 'sale_returns', 'sale_return_items',
    'proforma_invoices', 'proforma_invoice_items',
    'inventory_movements', 'stock_alerts',
    'purchase_orders', 'purchase_order_items',
    'treasury_accounts', 'treasury_movements',
    'cash_register_sessions', 'monthly_closures',
    'activity_logs', 'sale_logs',
)

def upgrade() -> None:
    bind = op.get_bind()

    # Vérifier qu'il n'existe pas déjà d'organisation
    existing = bind.execute(sa.text("SELECT id FROM organizations LIMIT 1")).fetchone()
    if existing:
        raise RuntimeError(
            f"Une organisation existe déjà (id={existing[0]}). "
            "Cette migration ne doit être exécutée qu'une seule fois."
        )

    # Créer l'organisation par défaut pour les données existantes
    result = bind.execute(sa.text("""
        INSERT INTO organizations (name, code, active, subscription_plan, created_at, updated_at)
        VALUES ('Korgo Pro — Données existantes', 'KORGO-DEFAULT', true, 'free', now(), now())
        RETURNING id
    """))
    default_org_id = result.scalar()

    # Rattacher toutes les lignes dont organization_id est NULL
    for table in TABLES_WITH_ORG:
        bind.execute(sa.text(f"""
            UPDATE "{table}"
            SET organization_id = :oid
            WHERE organization_id IS NULL
        """), {"oid": default_org_id})

    # Vérifier qu'il ne reste aucune ligne sans organisation
    for table in TABLES_WITH_ORG:

### 2.3 Migration `0006_organization_id_required.py` (rendre NOT NULL)

```python
"""organization_id required

Revision ID: 0006_organization_id_required
Revises: 0005_backfill_organization
Create Date: 2026-10-19

Rend organization_id NOT NULL sur toutes les tables métier
après validation du backfill.
"""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = '0006_organization_id_required'
down_revision: Union[str, None] = '0005_backfill_organization'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES_WITH_ORG = (
    'customers', 'suppliers', 'products', 'stores',
    'sales', 'sale_items', 'sale_returns', 'sale_return_items',
    'proforma_invoices', 'proforma_invoice_items',
    'inventory_movements', 'stock_alerts',
    'purchase_orders', 'purchase_order_items',
    'treasury_accounts', 'treasury_movements',
    'cash_register_sessions', 'monthly_closures',
    'activity_logs', 'sale_logs',
)

def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES_WITH_ORG:
        count = bind.execute(sa.text(f"""
            SELECT COUNT(*) FROM "{table}" WHERE organization_id IS NULL
        """)).scalar()
        if count and count > 0:
            raise RuntimeError(

## 3. SÉCURITÉ RLS (Row Level Security)

### 3.1 Nouvelles fonctions de sécurité

Fichier : `supabase_org_functions.sql`

```sql
-- app_security.is_admin_in_org(p_organization_id uuid) -> boolean
-- app_security.current_organization_ids() -> uuid[]
-- app_security.can_in_org(p_permission text, p_organization_id uuid) -> boolean
-- app_security.current_member_role(p_organization_id uuid) -> text
```

### 3.2 Politiques RLS par table

Pour chaque table métier avec `organization_id` :

| Action | Politique | Condition |
|--------|-----------|-----------|
| SELECT | `org_read_{table}` | `organization_id = ANY(app_security.current_organization_ids())` |

## 4. PARCOURS D'INSCRIPTION AUTOMATIQUE

### 4.1 Flux atomique (côté serveur)

1. L'application cliente envoie : `organization_name`, `organization_code`, `admin_name`, `admin_email`, `admin_password`.
2. Une fonction serveur (Edge Function ou RPC `SECURITY DEFINER`) exécute dans une transaction :
   a. Vérifie que l'email n'existe pas déjà dans `auth.users`.
   b. Crée le compte dans `auth.users` (email, mot de passe hashé, metadata avec username/role/active).
   c. Crée l'enregistrement dans `organizations`.
   d. Crée l'enregistrement dans `organization_members` avec `role='ADMIN'`, `active=true`.
   e. Crée une ligne dans `app_settings` si nécessaire.
   f. Retourne `{ ok: true, organization_id, user_id }`.
3. En cas d'erreur à n'importe quelle étape, rollback complet.


## 5. STRATÉGIE DE RESTAURATION ET RETOUR ARRIÈRE

| Étape | Action de rollback |
|-------|-------------------|
| `0004_multi_entreprise` | `downgrade()` supprime les colonnes `organization_id`, les index, les FK, puis les tables `organization_members` et `organizations`. |
| `0005_backfill_organization` | Pas de rollback automatique. Restaurer depuis une sauvegarde SQL avant cette migration. |
| `0006_organization_id_required` | `downgrade()` rend `organization_id` nullable à nouveau. |

**Procédure de sécurité :**
1. Faire une sauvegarde complète de la base Supabase avant toute migration.
2. Tester chaque migration sur une copie de la base de production.
3. Exécuter les migrations une par une, en vérifiant le résultat après chacune.
4. En cas d'échec, restaurer la sauvegarde et analyser l'erreur.

## 6. FICHIERS À CRÉER OU MODIFIER (Récapitulatif)

### Base de données

| Fichier | Action |
|---------|--------|
| `alembic/versions/0004_multi_entreprise.py` | Créer |
| `alembic/versions/0005_backfill_organization.py` | Créer |
| `alembic/versions/0006_organization_id_required.py` | Créer |
| `supabase_org_functions.sql` | Créer |
| `supabase_rls_multitenant.sql` | Créer |

### Backend Python (desktop)

| Fichier | Modification |
|---------|-------------|
| `core/models/user.py` | Ajouter relation vers `organization_members` |
| `core/models/*.py` | Ajouter colonne `organization_id` à chaque modèle métier |
| `core/supabase_auth.py` | Accepter `organization_id` dans les fonctions de création |
| `controllers/auth_controller.py` | Retourner les organisations de l'utilisateur après login |
| `core/permissions.py` | Ajouter évaluation des permissions par organisation |
| `core/store_manager.py` | Porter la portée magasin vers organisation + magasin |
| `ui/views/login_view.py` | Ajouter sélection d'organisation |
| `ui/views/main_window.py` | Afficher l'organisation active |

### Frontend Web

| Fichier | Modification |
|---------|-------------|
| `web/src/api/authApi.js` | Ajouter fonction d'inscription organisation |
| `web/src/api/remoteAuth.js` | Retourner les organisations après login |
| `web/src/context/AuthContext.jsx` | Gérer l'organisation active |
| `web/src/api/db.js` / `remote.jsx` | Ajouter `organization_id` aux requêtes |
| `web/src/pages/Login.jsx` | Formulaire d'inscription entreprise |

### Frontend Mobile

| Fichier | Modification |
|---------|-------------|
| `mobile/src/api/authApi.js` | Ajouter inscription organisation |
| `mobile/src/api/rpc.js` | Ajouter `p_organization_id` aux appels RPC |
| `mobile/src/context/AuthContext.js` | Gérer l'organisation active |
| `mobile/src/screens/LoginScreen.js` | Formulaire d'inscription entreprise |

## 7. VALIDATION REQUISE AVANT PRODUCTION

Avant d'appliquer toute migration sur la base de production :

- [ ] Accès au tableau de bord Supabase obtenu et testé
- [ ] Sauvegarde complète de la base effectuée
- [ ] Migration `0004` testée sur une copie de la base
- [ ] Migration `0005` testée avec vérification du backfill (zéro ligne sans `organization_id`)
- [ ] Migration `0006` testée (toutes les tables ont `organization_id NOT NULL`)
- [ ] Politiques RLS testées (isolation inter-entreprises vérifiée via API directe)
- [ ] Parcours d'inscription testé sur les trois plateformes
- [ ] Tests de régression sur les fonctionnalités existantes (ventes, stock, facturation)

---

**Attente :** Validation de ce plan avant toute exécution sur la base de production. Aucune migration ne sera lancée automatiquement sans accord explicite.
### 4.2 Empêchement des doublons

- Un email existant dans `auth.users` ne peut pas créer une nouvelle organisation via ce parcours.
- L'utilisateur existant doit être invité dans une organisation existante par un admin de celle-ci.
- Le parcours de connexion (login) est distinct du parcours d'inscription (signup).
| INSERT | `org_insert_{table}` | `organization_id = ANY(app_security.current_organization_ids())` AND rôle autorisé |
| UPDATE | `org_update_{table}` | `organization_id = ANY(app_security.current_organization_ids())` AND rôle autorisé |
| DELETE | `org_delete_{table}` | `organization_id = ANY(app_security.current_organization_ids())` AND rôle admin |

Pour les tables sans `organization_id` (`users`, `app_settings`, `user_sessions`) : conserver les politiques existantes, éventuellement affinées.

### 3.3 Protection contre la modification libre de `organization_id`

- La politique UPDATE inclut une `WITH CHECK` qui vérifie que l'utilisateur est admin de l'organisation cible s'il essaie de changer `organization_id`.
- Un utilisateur non-admin ne peut pas modifier `organization_id` d'une ligne existante.
                f"{table} contient encore {count} ligne(s) sans organization_id. "
                "Exécuter d'abord 0005_backfill_organization."
            )
        op.alter_column(table, 'organization_id', nullable=False)

def downgrade() -> None:
    for table in TABLES_WITH_ORG:
        op.alter_column(table, 'organization_id', nullable=True)
```
        count = bind.execute(sa.text(f"""
            SELECT COUNT(*) FROM "{table}" WHERE organization_id IS NULL
        """)).scalar()
        if count and count > 0:
            raise RuntimeError(
                f"{count} ligne(s) dans '{table}' n'ont pas pu être rattachées à une organisation. "
                "Migration interrompue pour éviter une perte de données."
            )

def downgrade() -> None:
    # Pas de retour arrière possible après backfill sans perte de données
    # L'utilisateur doit restaurer depuis une sauvegarde
    pass
```
    try:
        op.drop_table('organization_members')
    except Exception:
        pass
    try:
        op.drop_table('organizations')
    except Exception:
        pass
```
### 2.1 Migration `0004_multi_entreprise.py` (création des structures)

Crée les tables `organizations` et `organization_members`, ajoute `organization_id` (nullable) aux tables métier, et prépare les index / contraintes étrangères.
- `purchase_orders`, `purchase_order_items`
- `treasury_accounts`, `treasury_movements`
- `cash_register_sessions`, `monthly_closures`
- `activity_logs`, `sale_logs`

### 1.3 Tables sans `organization_id`

| Table | Raison |
|-------|--------|
| `organizations` | Table racine |
| `organization_members` | Table de liaison (a ses propres FK) |
| `users` | Profil applicatif global (un utilisateur peut appartenir à plusieurs entreprises via `organization_members`) |
| `auth.users` | Géré par Supabase Auth (ne pas modifier) |
| `app_settings` | Peut rester global (une ligne `id=1`) avec les préférences de l'entreprise stockées dans le JSON `data` sous clé `organization_<id>`, OU devenir par organisation (une ligne par `organization_id`) |
| `user_sessions` | Lié à `auth.users.id`, l'organisation est déduite via `organization_members` |
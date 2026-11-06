# AUDIT MULTI-ENTREPRISES — Korgo Pro

**Date de l'audit :** 19/10/2026  
**Projet :** Korgo Pro  
**Statut :** Phase 1 — Audit uniquement, aucune modification de la base de production

---

## 1. ARCHITECTURE ACTUELLE

### 1.1 Trois versions, une seule base Supabase

| Version | Technologie | Point d'entrée | Connexion Supabase |
|---------|------------|----------------|-------------------|
| **Windows (desktop)** | Python 3 + PySide6 (Qt) + SQLAlchemy | `app_bootstrap.py` / `run_application()` | SQLAlchemy / psycopg2, port 5432 (session pooling), utilisateur `postgres` avec mot de passe |
| **Web** | React 18 + Vite + `@supabase/supabase-js` | `web/src/App.jsx` | PostgREST REST API, clé publique (anon/publishable), `web/.env` |
| **Android (mobile)** | React Native + Expo + `@supabase/supabase-js` | `mobile/App.js` | PostgREST REST API, clé publique, `mobile/.env`, AsyncStorage |

Les trois versions ciblent le **même projet Supabase** (`tvvvgrqzcjtzdqxhnxtc.supabase.co`) et partagent le même schéma PostgreSQL `public`.

### 1.2 Schéma de base de données (découvert via les modèles SQLAlchemy et les fichiers SQL)

Tables présentes dans `public` :

- `users` : Profils applicatifs (username, role, active, email…) — `email` lié à `auth.users.email`
- `auth.users` : Comptes Supabase Auth (email, mot de passe, statut) — géré par Supabase
- `customers` : Clients
- `suppliers` : Fournisseurs
- `products` : Produits / catalogue — `supplier_id`, `store_id`
- `stores` : Magasins / points de vente — `is_default`
- `sales` : Ventes / factures — `customer_id`, `cashier_id`, `store_id`
- `sale_items` : Lignes de vente — `sale_id`, `product_id`
- `sale_returns`, `sale_return_items` : Retours de vente
- `proforma_invoices`, `proforma_invoice_items` : Devis / proformas — `customer_id`, `created_by`
- `inventory_movements` : Mouvements de stock — `product_id`, `user_id`, `store_id`
- `stock_alerts` : Alertes de stock — `product_id`
- `purchase_orders`, `purchase_order_items` : Commandes d'achat — `supplier_id`, `user_id`
- `treasury_accounts` : Comptes de trésorerie
- `treasury_movements` : Mouvements de trésorerie — `account_id`, `user_id`
- `cash_register_sessions` : Sessions de caisse — `account_id`, `user_id`
- `monthly_closures` : Clôtures mensuelles — `closed_by`
- `activity_logs` : Journal d'activité — `user_id`
- `sale_logs` : Journal des ventes — `sale_id`, `user_id`
- `app_settings` : Paramètres applicatifs (singleton, JSONB) — `id = 1`
- `user_sessions` : Sessions actives (single-session) — `user_id` → `auth.users.id`

### 1.3 Authentification et autorisation actuelles

- **Supabase Auth (`auth.users`)** est la source de vérité des comptes (email + mot de passe + statut).
- **`public.users`** est une table de profil alimentée par des triggers PostgreSQL (`on_auth_user_changed`, `on_auth_user_deleted`) depuis `auth.users`.
- Le desktop vérifie aussi directement `auth.users` via SQLAlchemy (`core/supabase_auth.py`).
- Le web et le mobile utilisent `supabase.auth.signInWithPassword()` puis lisent le profil `public.users`.
- **Rôles applicatifs :** `ADMIN`, `GESTIONNAIRE`, `SUPERVISEUR`, `ASSISTANT`, `CAISSIER` (définis dans `core/permissions.py` et répliqués côté serveur dans `supabase_mobile_rpc.sql`).
- **RLS (Row Level Security) :** activé sur la plupart des tables via `supabase_rls_policies.sql`. Deux classes d'accès : `admin` (écriture complète) et `user` (lecture + écriture opérationnelle limitée). Aucun filtrage par organisation n'existe.

### 1.4 Fichiers SQL déjà déployés sur Supabase

| Fichier | Rôle |
|---------|------|
| `supabase_users_supabase_only.sql` | Profil `public.users`, triggers auth→profil, RPC admin (`admin_create_user`, `admin_update_user_profile`, `admin_delete_user`, `admin_set_user_active`) |
| `supabase_rls_policies.sql` | RLS sur toutes les tables, fonctions `app_security.is_admin()`, `app_security.current_email()` |
| `supabase_single_session.sql` | Table `user_sessions`, verrou « un seul appareil par utilisateur », RPC session |
| `supabase_mobile_rpc.sql` | RPC `app_*` pour le mobile (vente, paiement, annulation, stock, trésorerie) avec vérification de droits côté serveur |
| `supabase_app_settings.sql` | Table `app_settings` (singleton JSONB) + RPC `app_merge_settings` |
| `supabase_monthly_closures.sql` | Table `monthly_closures` + RLS |

### 1.5 Migrations Alembic

| Révision | Description |

## 2. TABLES ET FONCTIONS CONCERNÉES PAR LE MULTI-ENTREPRISES

### 2.1 Tables commerciales devant recevoir `organization_id`

Toutes les tables contenant des données métier appartenant à une entreprise :

`customers`, `suppliers`, `products`, `stores`, `sales`, `sale_items`, `sale_returns`, `sale_return_items`, `proforma_invoices`, `proforma_invoice_items`, `inventory_movements`, `stock_alerts`, `purchase_orders`, `purchase_order_items`, `treasury_accounts`, `treasury_movements`, `cash_register_sessions`, `monthly_closures`, `activity_logs`, `sale_logs`.

### 2.2 Tables de référentiel transverse (pas d'`organization_id`)

- `organizations` (nouvelle)
- `organization_members` (nouvelle, liaison utilisateur ↔ entreprise)
- `users` (profil, lié à `auth.users` — pas d'`organization_id` car un utilisateur peut appartenir à plusieurs entreprises)
- `app_settings` (paraît être global — pourrait devenir par organisation ou rester global avec une clé `organization_id` dans le JSON)
- `user_sessions` (lié à `auth.users.id`, pas directement à une organisation)

### 2.3 Fonctions SQL et RPC à réviser

- `app_security.is_admin()` — vérifie globalement si un utilisateur est admin, sans notion d'entreprise → doit devenir `app_security.is_admin_in_org(p_organization_id)`
- `app_security.current_role()` — retourne le rôle global → doit devenir rôle par organisation
- `app_security.can(p_permission)` — matrice de permissions globale → doit devenir `app_security.can_in_org(p_permission, p_organization_id)`
- Toutes les RPC `app_*` dans `supabase_mobile_rpc.sql` — n'ont pas de paramètre d'organisation
- Tous les triggers `on_auth_user_changed` — ne gèrent pas d'organisation

### 2.4 Politiques RLS actuelles

| Groupe de tables | Lecture | Écriture |
|-----------------|---------|----------|
| `sales`, `sale_items`, `payments`, `sale_returns`, `sale_return_items`, `proforma_invoices`, `proforma_invoice_items`, `inventory_movements`, `stock_alerts` | `user_read_*` (tous les authentifiés) | `admin_insert_*` / `admin_update_*` / `admin_delete_*` (admin uniquement) |
| `customers`, `suppliers`, `products`, `stores`, `purchase_orders`, `purchase_order_items`, `treasury_accounts`, `treasury_movements`, `cash_register_sessions` | `user_read_*` (tous les authentifiés) | `admin_insert_*` / `admin_update_*` / `admin_delete_*` (admin uniquement) |
| `users` | lecture restreinte | déclenché par auth, pas d'écriture directe |
| `app_settings` | tous les authentifiés | admin uniquement |
| `monthly_closures` | tous les authentifiés | admin uniquement |


## 3. RISQUES DE SÉCURITÉ IDENTIFIÉS

1. **Aucune isolation entre entreprises** : toutes les tables partagent le même espace de noms. Un utilisateur de l'entreprise A peut lire (et, s'il est admin, modifier) les données de l'entreprise B.
2. **`is_admin()` est global** : un administrateur d'une entreprise a des droits sur toutes les données de toutes les entreprises.
3. **Aucune table `organizations` / `organization_members`** : il n'existe aucun moyen d'associer un utilisateur à une entreprise spécifique.
4. **La clé publique (anon key) est utilisée par le web et le mobile** : sans RLS par organisation, un utilisateur malveillant peut contourner l'interface et accéder directement aux données via l'API REST PostgREST.
5. **Aucun contrôle sur `organization_id` côté client** : si une colonne `organization_id` est ajoutée sans RLS appropriée, un utilisateur peut modifier sa propre `organization_id` pour accéder aux données d'une autre entreprise.
6. **Le modèle « single session » actuel lie une session à un utilisateur global**, pas à un utilisateur dans une organisation spécifique. Un utilisateur appartenant à plusieurs entreprises devrait pouvoir avoir des sessions distinctes par entreprise.
7. **Les fonctions `app_security` sont dans le schéma `app_security`** (non exposé par PostgREST) — bon pour la sécurité, mais elles doivent être étendues pour supporter le multi-tenant.

## 4. INCOMPATIBILITÉS POTENTIELLES

| Problème | Description | Impact |
|----------|-------------|--------|
| Rôles globaux | `users.role` est global, pas par entreprise | Un utilisateur ne peut pas être caissier dans l'entreprise A et admin dans l'entreprise B |
| `app_security.is_admin()` | Vérifie le rôle global sans organisation | Un admin de l'entreprise A peut écrire dans l'entreprise B |
| `user_sessions` | Lie une session à `auth.users.id` uniquement | Un utilisateur multi-entreprises ne peut pas avoir de sessions actives dans plusieurs entreprises simultanément |
| `app_settings` | Table singleton globale (`id = 1`) | Les paramètres d'entreprise (nom, adresse, TVA) ne sont pas isolés |
| Pas d'`organization_id` | Aucune colonne d'appartenance entreprise | Migration nécessaire sur toutes les tables métier |
| Clé publique partagée | Web et mobile utilisent la même anon key | Sans RLS par org, l'isolation repose uniquement sur le code applicatif |
**Problème :** aucune politique ne filtre par `organization_id`. Toutes les données sont visibles par tout utilisateur authentifié (lecture) ou par tout admin (écriture).
|----------|-------------|
| `0001_baseline_schema.py` | Crée toutes les tables depuis les modèles ORM |
| `0002_multi_magasins.py` | Ajoute `stores` + `store_id` sur `products`, `inventory_movements`, `sales` |
| `0003_app_settings.py` | Ajoute `app_settings` (singleton) |
| `legacy_sqlite/` | Historique SQLite archivé (non utilisé sur Supabase) |

## 5. FICHIERS À MODIFIER

### 5.1 Base de données (SQL / migrations)

| Fichier | Action |
|---------|--------|
| Nouvelle migration Alembic `0004_multi_entreprise.py` | Créer `organizations`, `organization_members`, ajouter `organization_id` aux tables métier, backfill des données existantes |
| Nouveau fichier SQL `supabase_rls_multitenant.sql` | Remplacer/étendre les politiques RLS pour filtrer par `organization_id` |
| Nouveau fichier SQL `supabase_org_functions.sql` | Fonctions `app_security.is_admin_in_org()`, `app_security.current_organization_id()`, `app_security.can_in_org()` |

## 6. PLAN DE MIGRATION RECOMMANDÉ (Phase 2 à Phase 3)

### Étape A — Préparation (sans toucher la production)

1. Créer les documents de conception (`docs/plan_migration_multitenant.md`).
2. Préparer les fichiers SQL de migration (idempotents, testables sur une copie de la base).
3. Préparer les migrations Alembic versionnées (`0004_multi_entreprise.py`, etc.).
4. Préparer les tests unitaires et d'intégration sur environnement de test.

### Étape B — Migration de schéma (à valider avant exécution production)

1. Créer `organizations` (UUID, nom, code, active, created_at).
2. Créer `organization_members` (user_id → auth.users.id, organization_id, role, active, created_at).
3. Ajouter `organization_id` (nullable, UUID) à toutes les tables métier listées ci-dessus.
4. **Backfill** : déterminer l'organisation par défaut pour les données existantes. Si des données ne peuvent pas être attribuées sans ambiguïté, la migration doit s'arrêter et signaler l'erreur.
5. Créer les index et contraintes FK sur `organization_id`.
6. Rendre `organization_id` NOT NULL après validation du backfill.

### Étape C — Sécurité RLS

1. Remplacer les politiques RLS existantes par des politiques filtrant sur `organization_id`.
2. Créer les fonctions `app_security` pour le multi-tenant (`is_admin_in_org`, `current_organization_id`, `can_in_org`).
3. Interdire la modification libre de `organization_id` par un utilisateur non administrateur de l'organisation cible.

### Étape D — Parcours d'inscription

1. Créer une fonction serveur (Edge Function ou RPC transactionnelle) qui, atomiquement :
   - Crée le compte Supabase Auth.
   - Crée l'organisation.
   - Crée le lien `organization_members` avec rôle `ADMIN`.
   - Initialise les paramètres (`app_settings` ou équivalent par organisation).
2. Mettre à jour les trois applications pour utiliser ce parcours.
3. Empêcher un utilisateur existant de créer une deuxième organisation par erreur (il doit rejoindre une organisation existante via invitation).

### Étape E — Intégration aux trois applications

1. **Desktop** : ajouter sélection d'organisation au login, filtrer les requêtes SQLAlchemy par `organization_id`.
2. **Web** : ajouter `organization_id` aux appels PostgREST, protéger les routes.
3. **Mobile** : ajouter `organization_id` aux RPC, gérer la sélection d'organisation.

### Étape F — Synchronisation

1. Vérifier que Realtime est configuré pour les tables par organisation.
2. S'assurer que la resynchronisation après déconnexion recharge les données de l'organisation active.
3. Ajouter la prévention des doublons de vente (idempotence).

### Étape G — Tests

1. Tests d'inscription d'une nouvelle entreprise.
2. Tests d'isolation inter-entreprises.
3. Tests d'usurpation de rôle.
4. Tests de cohérence des stocks avec ventes simultanées.
5. Tests de sauvegarde/restauration.

### Étape H — Déploiement

## 7. ACCÈS ET DÉCISIONS MANQUANTES

Les éléments suivants doivent être confirmés avant de passer à la Phase 2 :

1. **Accès Supabase** : Aucun accès au tableau de bord Supabase n'a été fourni. Les migrations SQL ne peuvent pas être appliquées sur la production sans cet accès.
2. **Données existantes** : Il n'est pas clair si la base de production contient déjà des données commerciales réelles. Si oui, un backfill d'`organization_id` est nécessaire. Si non, le schéma cible peut être créé directement.
3. **Politique d'inscription** : Une nouvelle entreprise peut-elle être créée librement par tout utilisateur, ou uniquement sur invitation d'un administrateur système ?
4. **Utilisateur multi-entreprises** : Un utilisateur peut-il appartenir à plusieurs entreprises simultanément ? (Le modèle proposé le permet, mais cela impacte la gestion de session.)
5. **Clé publique actuelle** : La valeur de `VITE_SUPABASE_ANON_KEY` / `EXPO_PUBLIC_SUPABASE_ANON_KEY` est présente dans les fichiers `.env` mais ne doit pas être révélée dans ce rapport.
6. **Environnement de test** : Un projet Supabase de staging est nécessaire pour tester les migrations avant production.

## 8. STRATÉGIE DE MIGRATION RECOMMANDÉE (Résumé)

1. **Ne rien modifier sur la production** avant validation complète sur une copie de test.
2. **Créer le schéma cible** : `organizations`, `organization_members`, `organization_id` sur toutes les tables métier.
3. **Migrer progressivement** : d'abord les structures, puis le backfill, puis les contraintes NOT NULL, puis les politiques RLS.
4. **Garder la compatibilité** : les anciennes colonnes restent pendant la transition, les nouvelles fonctionnalités utilisent `organization_id`.
5. **Rollback** : chaque migration doit avoir un script de downgrade testé.
6. **Aucune clé `service_role`** dans les applications clientes (Windows, Web, Android).

---

**Suivant :** Production de `docs/plan_migration_multitenant.md` avec le détail du schéma cible et des migrations SQL versionnées.

1. Documenter la procédure de migration.
2. Préparer un plan de retour arrière (rollback).
3. Déployer sur un environnement de staging avant production.

## 9. TESTS NÉCESSAIRES

| Test | Objectif |
|------|----------|
| Inscription nouvelle entreprise | Création atomique compte + organisation + premier admin |
| Connexion même utilisateur sur 3 appareils | Cohérence des données Windows / Web / Android |
| Isolation inter-entreprises | Entreprise A ne peut pas lire les données de l'entreprise B |
| Usurpation de rôle admin | Un caissier ne peut pas s'attribuer le rôle ADMIN |
| Doublon d'inscription | Un email existant ne peut pas créer une deuxième organisation |
| Doublon de vente | Même vente ne peut pas être enregistrée deux fois |
| Cohérence des stocks | Ventes simultanées ne rendent pas le stock négatif |
| Session expirée | Reconnexion après expiration gérée proprement |
| Fonctions SQL + factures | Les RPC et factures fonctionnent avec `organization_id` |
| Sauvegarde / restauration | La base peut être sauvegardée et restaurée avec l'isolation |
| `supabase_mobile_rpc.sql` | Ajouter `p_organization_id` aux RPC `app_*` |
| `supabase_users_supabase_only.sql` | Les RPC admin existants doivent vérifier l'appartenance à l'organisation |

### 5.2 Backend Python (desktop)

| Fichier | Action |
|---------|--------|
| `core/models/user.py` | Ajouter `organization_id` (nullable) ou créer `OrganizationMember` modèle |
| `core/models/*.py` | Ajouter `organization_id` à tous les modèles métier |
| `core/database.py` | Aucun changement (moteur SQLAlchemy inchangé) |
| `core/supabase_auth.py` | Les fonctions de création utilisateur doivent accepter `organization_id` |
| `controllers/auth_controller.py` | L'authentification doit retourner l'organisation(s) de l'utilisateur |
| `core/store_manager.py` | La portée magasin doit devenir portée organisation + magasin |
| `core/permissions.py` | La matrice de permissions doit être évaluable par organisation |
| `ui/views/login_view.py` | Ajouter sélection de l'organisation active à la connexion |
| `ui/views/main_window.py` | Afficher l'organisation active, filtrer les données |
| `app_bootstrap.py` | Initialiser l'organisation par défaut si absente |

### 5.3 Frontend Web

| Fichier | Action |
|---------|--------|
| `web/src/api/supabase.js` | Aucun changement (client inchangé) |
| `web/src/api/authApi.js` | Ajouter inscription multi-entreprise (création org + premier admin) |
| `web/src/api/remoteAuth.js` | Retourner l'organisation(s) de l'utilisateur après login |
| `web/src/context/AuthContext.jsx` | Gérer l'organisation active dans le contexte |
| `web/src/api/db.js` / `remote.jsx` | Ajouter `organization_id` aux requêtes et à l'hydratation |
| `web/src/pages/Login.jsx` | Ajouter formulaire d'inscription entreprise |
| `web/src/pages/*.jsx` | Filtrer par organisation active |

### 5.4 Frontend Mobile

| Fichier | Action |
|---------|--------|
| `mobile/src/api/supabase.js` | Aucun changement |
| `mobile/src/api/authApi.js` | Ajouter inscription multi-entreprise |
| `mobile/src/api/rpc.js` | Ajouter `organization_id` aux appels RPC |
| `mobile/src/api/remote.js` | Ajouter `organization_id` aux mappings |
| `mobile/src/context/AuthContext.js` | Gérer l'organisation active |
| `mobile/src/screens/LoginScreen.js` | Ajouter formulaire d'inscription entreprise |
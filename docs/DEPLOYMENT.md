# Korgo Pro - Guide de Déploiement et Maintenance

## Table des Matières

1. [Déploiement en Production](#déploiement-en-production)
2. [Déploiement en Développement](#déploiement-en-développement)
3. [Architecture](#architecture)
4. [Gestion des Configurations](#gestion-des-configurations)
5. [Sauvegarde et Récupération](#sauvegarde-et-récupération)
6. [Troubleshooting](#troubleshooting)
7. [Maintenance Régulière](#maintenance-régulière)

---

## Déploiement en Production

### Prérequis

- **Python 3.11+** (vérifier avec `python --version`)
- **Accès administrateur** sur le serveur/poste
- **Base de données** : PostgreSQL recommandé (SQLite pour petite équipe)
- **Espace disque** : Min 500 MB, recommandé 2 GB

### Installation Production

#### 1. Cloner le repository

```bash
git clone https://github.com/Madarahaidara/korgopro.git
cd korgopro
git checkout main  # ou tag de version spécifique
```

#### 2. Configurer l'environnement

```bash
# Créer le fichier .env basé sur le template
cp .env.example .env

# Éditer .env avec les paramètres de production
# Configuration minimale requise :
# - KORGO_DB_URL=postgresql://user:pass@host:5432/korgo_pro
# - SECRET_KEY=<secret_aléatoire_fort>
# - LOG_LEVEL=INFO
```

**Générer une SECRET_KEY sécurisée :**

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

#### 3. Installer les dépendances

```bash
# Créer un virtualenv
python -m venv venv

# Activer le virtualenv (Windows)
.\venv\Scripts\activate
# OU (Linux/Mac)
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Vérifier l'installation
python -c "from PySide6 import QtWidgets; print('PySide6 OK')"
```

#### 4. Initialiser la base de données

```bash
# Si utilisant PostgreSQL, créer la DB d'abord :
# psql -U postgres
# CREATE DATABASE korgo_pro;
# CREATE USER korgo WITH PASSWORD 'password';
# GRANT ALL PRIVILEGES ON DATABASE korgo_pro TO korgo;

# Exécuter les migrations (si applicable)
python scripts/init_db.py
```

#### 5. Lancer l'application

```bash
python main.py
```

**Vérifications initiales :**
- ✅ Interface se charge sans erreurs
- ✅ Authentification fonctionne
- ✅ Base de données accessible
- ✅ Rapports peuvent être exportés

---

## Déploiement en Développement

### Installation Locale Rapide

```bash
# 1. Clone et setup
git clone https://github.com/Madarahaidara/korgopro.git
cd korgopro

# 2. Virtualenv + dépendances
python -m venv venv
.\venv\Scripts\activate  # Windows: .\venv\Scripts\activate
pip install -r requirements.txt

# 3. Copier et éditer .env
cp .env.example .env
# Optionnel : modifier KORGO_DB_URL pour utiliser une DB test

# 4. Lancer
python main.py
```

### Développement avec Reload Automatique

```bash
# Installer watchdog pour reload auto
pip install watchdog[watchmedo]

# Lancer app avec reload auto sur changements
watchmedo auto-restart -d . -p '*.py' -- python main.py
```

### Tests Locaux

```bash
# Installer pytest
pip install pytest pytest-qt pytest-cov

# Lancer tous les tests
pytest

# Lancer tests spécifiques
pytest tests/test_auth.py -v

# Avec coverage
pytest --cov=. --cov-report=html
```

---

## Architecture

### Structure du Projet

```
korgopro/
├── main.py                      # Point d'entrée
├── core/                        # Logique métier
│   ├── database.py              # Gestion DB (SQLAlchemy)
│   ├── database_manager.py      # Opérations DB
│   └── security.py              # Authentification & sécurité
├── ui/                          # Interface utilisateur
│   ├── views/                   # Écrans (Login, Dashboard, Ventes, etc.)
│   ├── components/              # Composants réutilisables
│   ├── themes/                  # QSS, tokens, theme manager
│   └── icons/                   # Icônes et assets
├── controllers/                 # Logique contrôleur (MVC)
│   └── auth_controller.py       # Gestion authentification
├── utils/                       # Utilitaires
│   ├── settings_manager.py      # Configuration
│   └── resource_path.py         # Gestion des chemins
├── scripts/                     # Scripts utilitaires
│   └── init_db.py               # Initialisation DB
├── tests/                       # Tests unitaires
│   └── test_*.py                # Tests par module
├── docs/                        # Documentation
│   ├── ARCHITECTURE.md          # Vue générale
│   ├── DEPLOYMENT.md            # Ce fichier
│   ├── CONTRIBUTING.md          # Guide contribution
│   └── CHANGELOG.md             # Historique versions
├── data/                        # Données non trackées (rapports, exports)
├── .env.example                 # Template configuration
├── README.md                    # Début rapide
└── requirements.txt             # Dépendances figées
```

### Flux de Données Simplifié

```
[UI View] → [Controller] → [Core Logic] → [Database]
                                        ↓
                               [core/database.py]
                                        ↓
                             [SQLAlchemy ORM]
```

**Exemple : Créer une vente**

1. User clique "Nouvelle vente" → `SaleView`
2. `SaleView` appelle `SaleController.create_sale(data)`
3. `SaleController` valide les données
4. `core/database_manager.execute_sql()` insère dans la DB
5. Réponse retournée → UI mise à jour

---

## Gestion des Configurations

### Fichier .env

Template inclus : `.env.example`

**Variables critiques :**

```env
# Database
KORGO_DB_URL=sqlite:///korgo_pro.db        # SQLite (dev)
# KORGO_DB_URL=postgresql://user:pass@localhost:5432/korgo_pro

# Sécurité
SECRET_KEY=<secret_fort_generé>            # Pour hash sessions/tokens

# Logging
LOG_LEVEL=INFO                              # DEBUG, INFO, WARNING, ERROR

# Optional
COMPANY_NAME=Mon Entreprise                # Nom affiché
DEBUG_MODE=false                            # Activer mode debug
```

### Validation au Démarrage

L'application valide la configuration au démarrage :

```python
# core/__init__.py or main.py
from utils.settings_manager import SettingsManager

sm = SettingsManager()
# Raises ConfigurationError si variables manquantes
```

---

## Sauvegarde et Récupération

### Stratégie de Sauvegarde

#### Pour SQLite (Development/Small Teams)

```bash
# Sauvegarde manuelle
cp korgo_pro.db backups/korgo_pro_$(date +%Y%m%d_%H%M%S).db

# Restauration
cp backups/korgo_pro_YYYYMMDD_HHMMSS.db korgo_pro.db
```

#### Pour PostgreSQL (Production)

```bash
# Sauvegarde complète
pg_dump -U korgo -h localhost korgo_pro > backups/korgo_pro_$(date +%Y%m%d).sql

# Sauvegarde compressée
pg_dump -U korgo -h localhost korgo_pro | gzip > backups/korgo_pro_$(date +%Y%m%d).sql.gz

# Restauration
psql -U korgo -h localhost korgo_pro < backups/korgo_pro_YYYYMMDD.sql
# OU
gunzip -c backups/korgo_pro_YYYYMMDD.sql.gz | psql -U korgo -h localhost korgo_pro
```

### Fréquence de Sauvegarde

- **Production** : Quotidienne (minuit) + après modifications critiques
- **Staging** : Hebdomadaire
- **Développement** : Manuelle (avant gros changements)

### Vérification de Sauvegarde

```bash
# Vérifier intégrité sauvegarde PostgreSQL
pg_dump -U korgo -h localhost korgo_pro --verbose --no-data > /dev/null && echo "Backup OK"
```

---

## Troubleshooting

### Problèmes Courants

#### 1. **Erreur de connexion DB**

**Symptôme :** `Error connecting to database`

**Solutions :**
```bash
# Vérifier KORGO_DB_URL dans .env
grep KORGO_DB_URL .env

# Pour SQLite
ls -la korgo_pro.db

# Pour PostgreSQL
psql -U korgo -h localhost -d korgo_pro -c "SELECT version();"
```

#### 2. **Interface ne charge pas**

**Symptôme :** Crash au lancement, erreur QSS

**Solutions :**
```bash
# Vérifier les fichiers theme
ls ui/themes/

# Vérifier les dépendances PySide6
python -c "from PySide6 import QtWidgets, QtCore, QtGui; print('OK')"

# Logs détaillés
python main.py 2>&1 | head -50
```

#### 3. **Erreur d'authentification**

**Symptôme :** "Identifiants incorrects"

**Solutions :**
- Vérifier l'existence de l'utilisateur en DB
- Réinitialiser mot de passe :
  ```bash
  python scripts/reset_user_password.py --user admin
  ```
- Vérifier SECRET_KEY dans .env (cohérente avec session existantes)

#### 4. **Espace disque plein**

**Symptôme :** Export PDF/rapports échouent

**Solutions :**
```bash
# Nettoyer les anciens rapports
ls -lt data/rapports/ | tail -20  # Voir fichiers anciens
rm data/rapports/rapport_*_2024*.xlsx  # Supprimer anciens

# Vérifier espace disponible
df -h

# Archiver si nécessaire
tar -czf backups/rapports_2024.tar.gz data/rapports/
```

#### 5. **Performance dégradée**

**Symptôme :** Lenteurs, timeouts

**Solutions :**
```bash
# Vérifier taille DB
du -sh korgo_pro.db

# Analyser logs
tail -100 debug.log | grep ERROR

# Nettoyer old logs si présents
find logs/ -mtime +30 -delete

# Pour PostgreSQL : ANALYZE
psql -U korgo -d korgo_pro -c "ANALYZE;"
```

---

## Maintenance Régulière

### Checklist Hebdomadaire

- [ ] ✅ Vérifier les backups ont été créés
- [ ] ✅ Consulter les logs pour erreurs/avertissements
- [ ] ✅ Tester créer/modifier une vente
- [ ] ✅ Tester export PDF
- [ ] ✅ Espace disque > 500 MB libre

### Checklist Mensuelle

- [ ] ✅ Vérifier les mises à jour de dépendances :
  ```bash
  pip list --outdated
  ```
- [ ] ✅ Nettoyer les anciens rapports/exports
- [ ] ✅ Revoir les logs pour patterns de problèmes
- [ ] ✅ Sauvegarder & tester restauration
- [ ] ✅ Exécuter les tests :
  ```bash
  pytest -v
  ```

### Checklist Annuelle

- [ ] ✅ Audit de sécurité (dépendances, secrets)
- [ ] ✅ Optimisation DB (VACUUM, ANALYZE pour PostgreSQL)
- [ ] ✅ Révision architecture
- [ ] ✅ Plan de migration version majeure
- [ ] ✅ Archivage données anciennes

---

## Mise à Jour de l'Application

### Avant une Mise à Jour

```bash
# 1. Backup complet
pg_dump -U korgo korgo_pro | gzip > backups/pre_update_$(date +%Y%m%d).sql.gz

# 2. Noter version actuelle
git describe --tags

# 3. Arrêter app si en production
# (Fermer fenêtre ou arrêter processus)
```

### Mise à Jour

```bash
# 1. Récupérer derniers changements
git fetch origin

# 2. Afficher nouveautés
git log main..origin/main --oneline

# 3. Mettre à jour branche
git pull origin main

# 4. Mettre à jour dépendances (si changé)
pip install -r requirements.txt

# 5. Vérifier configs
# (Si nouveau fichier .env requis)
diff .env.example .env

# 6. Lancer
python main.py
```

### Après Mise à Jour

- ✅ Vérifier l'interface charge
- ✅ Tester fonctionnalité clé (login, vente)
- ✅ Vérifier les logs pour erreurs
- ✅ Valider performance

---

## Support et Escalade

### Pour Obtenir de l'Aide

1. **Consulter ce guide** → [Troubleshooting](#troubleshooting)
2. **Lire les logs** → `python main.py 2>&1 | tail -100`
3. **Vérifier les issues** → https://github.com/Madarahaidara/korgopro/issues
4. **Créer une issue** avec :
   - Version Python (`python --version`)
   - Système d'exploitation
   - Erreur exact (screenshot + log)
   - Reproduction steps

### Escalade

Pour les problèmes critiques (data loss, sécurité) :
- Arrêter l'application
- Restaurer depuis backup
- Documenter le problème
- Contacter le mainteneur

---

## Références

- [README Principal](../README.md)
- [Architecture Technique](../docs/ARCHITECTURE.md)
- [Guide de Contribution](../docs/CONTRIBUTING.md)
- [Changelog](../docs/CHANGELOG.md)
- [Documentation API (WIP)](../docs/API.md)

---

**Dernière mise à jour**: August 2026  
**Mainteneur**: Korgo Team  
**Support**: GitHub Issues

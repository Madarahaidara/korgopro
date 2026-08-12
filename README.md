# Korgo Pro — Système de Gestion d'Entreprise

Korgo Pro est une **application de gestion d'entreprise** complète (ventes, stock, facturation) écrite en **Python 3.11+** avec une interface graphique moderne en **PySide6** et base de données **SQLAlchemy-compatible**.

> 🚀 **Nouvelle version 0.2.0 !** Theme tokens, composants réutilisables, menus responsive, et documentation complète.

## 📋 Table des Matières

- [Démarrage Rapide](#démarrage-rapide)
- [Documentation](#-documentation)
- [Fonctionnalités](#-fonctionnalités)
- [Améliorations Récentes](#-améliorations-récentes)
- [Architecture](#-architecture)
- [Support & Contribution](#-support--contribution)

---

## 🚀 Démarrage Rapide

### Prérequis

- **Python 3.11+** (`python --version`)
- **Git**
- Recommandé : **virtualenv/venv**

### Installation (< 5 minutes)

#### Linux / macOS

```bash
# 1. Clone le projet
git clone https://github.com/Madarahaidara/korgopro.git
cd korgopro

# 2. Créer virtualenv
python3 -m venv venv
source venv/bin/activate

# 3. Installer dépendances
pip install -r requirements.txt

# 4. Copier config (optionnel)
cp .env.example .env

# 5. Lancer
python main.py
```

#### Windows (PowerShell)

```powershell
# 1. Clone
git clone https://github.com/Madarahaidara/korgopro.git
cd korgopro

# 2. Virtualenv
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Dépendances
pip install -r requirements.txt

# 4. Config (optionnel)
Copy-Item .env.example .env

# 5. Lancer
python main.py
```

### Identifiants de Test

| User | Password | Role |
|------|----------|------|
| `admin` | `password` | ADMIN |
| `user` | `password` | USER |

> **Note** : Les données de test peuvent être générées avec `python scripts/recreate_db.py`

---

## 📚 Documentation

La documentation complète est organisée dans le dossier `docs/`. **Accédez à [docs/INDEX.md](docs/INDEX.md) pour voir tous les guides disponibles**.

### Documents Clés

| Document | Pour Qui ? | Contenu |
|----------|-----------|---------|
| **[docs/INDEX.md](docs/INDEX.md)** | Tous | 📍 **COMMENCER ICI** - Index complet |
| **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** | Admins, Ops | Installation prod, troubleshooting, backups |
| **[docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)** | Devs | Workflow dev, code style, tests |
| **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** | Devs, Architects | Structure du projet, flux de données |
| **[docs/MAINTENANCE.md](docs/MAINTENANCE.md)** | Ops | Monitoring, performance, sécurité long-terme |
| **[docs/CHANGELOG.md](docs/CHANGELOG.md)** | Tous | Historique versions & roadmap |
| **[ui/components/README.md](ui/components/README.md)** | Frontend Devs | Component library API |

---

## ✨ Fonctionnalités

### Core (v0.1.0)
- ✅ **Authentification** avec gestion des rôles (ADMIN/USER)
- ✅ **Gestion des Ventes** : création, modification, suppression
- ✅ **Gestion du Stock** : inventory tracking, alertes seuil
- ✅ **Facturation** : factures, proformas, export PDF
- ✅ **Rapports** : analyses de ventes, bénéfices, exports Excel
- ✅ **Paramètres Entreprise** : configuration, logo, données

### Nouveau (v0.2.0)
- ✨ **Theme System** : Tokens-based design (light/dark)
- ✨ **Responsive Menu** : Adaptive sidebar + mobile drawer
- ✨ **Component Library** : Buttons, Cards, composants réutilisables
- ✨ **Accessibility** : Screen reader support, keyboard navigation
- ✨ **Documentation** : Guides complets pour users, admins, devs
- ✨ **Database Config** : Support PostgreSQL + SQLite configurable

---

## 🎯 Améliorations Récentes

### v0.2.0 (2026-08-12)

**Design & UX**
- 🎨 Palette de couleurs token-based (25+ variables)
- 📱 Menu responsive adaptatif (desktop/mobile)
- 🧩 Composant library avec 3 composants + plus à venir
- ♿ Amélioration accessibilité (AccessibleNames, focus rings)

**Développement**
- 📚 Documentation complète (5 nouveaux guides)
- ⚙️ Configuration environnement (.env.example)
- 🔄 Database configurable (KORGO_DB_URL)
- 🤖 CI baseline (.github/workflows/)

**Données**
- 📂 Artefacts volumineux dans `data/` non-trackés
- 🔒 Secrets en `.env`, pas en code

---

## 🏗️ Architecture

### Vue Générale

```
korgopro/
├── main.py                    # Point d'entrée
├── core/                      # Logique métier
│   ├── database.py           # SQLAlchemy ORM
│   ├── security.py           # Auth & validation
│   └── database_manager.py   # Opérations DB
├── ui/                       # Interface (PySide6)
│   ├── views/               # Écrans (Login, Dashboard, etc.)
│   ├── components/          # Composants réutilisables
│   └── themes/              # QSS, tokens, theme manager
├── controllers/             # Logique contrôleur (MVC)
├── utils/                   # Utilitaires
├── tests/                   # Tests unitaires
├── docs/                    # Documentation
└── data/                    # Fichiers non-trackés (rapports, exports)
```

### Stack Technologique

| Couche | Technologie |
|--------|------------|
| **UI** | PySide6 (Qt for Python) |
| **Database** | SQLAlchemy ORM (PostgreSQL/SQLite) |
| **Backend** | Python 3.11+ |
| **Reports** | FPDF, openpyxl (PDF, Excel) |
| **Config** | python-dotenv (.env) |
| **CI/CD** | GitHub Actions (pytest) |

> Voir [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) pour détails complets

---

## 🔧 Configuration

### Variables d'Environnement (.env)

Créer un fichier `.env` basé sur `.env.example` :

```env
# Database (optionnel, fallback: sqlite:///korgo_pro.db)
KORGO_DB_URL=sqlite:///korgo_pro.db
# KORGO_DB_URL=postgresql://user:pass@localhost:5432/korgo_pro

# Sécurité (généré avec: python -c "import secrets; print(secrets.token_hex(32))")
SECRET_KEY=<secret_généré>

# Logging
LOG_LEVEL=INFO

# Optionnel
COMPANY_NAME=Mon Entreprise
DEBUG_MODE=false
```

> **Sécurité** : Ne jamais committer `.env` réel. Utiliser `.env.example` comme template.

---

## 🧪 Tests

### Lancer les Tests

```bash
# Tous les tests
pytest

# Avec coverage
pytest --cov=. --cov-report=html

# Tests spécifiques
pytest tests/test_auth.py -v
```

### Style de Code

```bash
# Format
black .

# Lint
flake8 ui/ core/ controllers/ utils/
```

> Voir [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) pour détails

---

## 📦 Dépendances

### Installation

```bash
pip install -r requirements.txt
```

### Dev Tools (optionnel)

```bash
pip install pytest pytest-qt pytest-cov black flake8
```

### Principales Dépendances

- **PySide6** : Interface utilisateur
- **SQLAlchemy** : ORM base de données
- **python-dotenv** : Configuration via .env
- **FPDF2** : Génération PDF
- **openpyxl** : Excel sheets

---

## 🚨 Troubleshooting

### "AttributeError: module 'qtpy' has no attribute 'QtCore'"

```bash
pip uninstall qtpy -y
pip install PySide6
```

### "Database file locked"

```bash
# Vérifier autres processus
ps aux | grep main.py
# Tuer si nécessaire
pkill -f "python main.py"
```

### "Connection refused" (PostgreSQL)

```bash
# Vérifier KORGO_DB_URL dans .env
# Vérifier PostgreSQL est running
psql -U postgres -c "SELECT 1;"
```

> Voir [docs/DEPLOYMENT.md#troubleshooting](docs/DEPLOYMENT.md#troubleshooting) pour plus

---

## 🔐 Sécurité

### Bonnes Pratiques

- ✅ Ne **jamais** committer `.env` avec secrets réels
- ✅ Utiliser **SECRET_KEY** fort (générer avec `secrets`)
- ✅ Mettre `.env` et `korgo_pro.db` dans `.gitignore`
- ✅ Garder dépendances à jour : `pip list --outdated`
- ✅ Archiver/supprimer rapports sensibles ancien

> Voir [docs/MAINTENANCE.md#sécurité](docs/MAINTENANCE.md#sécurité)

---

## 💾 Sauvegarde

### PostgreSQL

```bash
# Backup
pg_dump -U korgo korgo_pro | gzip > backups/korgo_$(date +%Y%m%d).sql.gz

# Restore
gunzip -c backups/korgo_20260812.sql.gz | psql -U korgo korgo_pro
```

### SQLite

```bash
# Backup
cp korgo_pro.db backups/korgo_$(date +%Y%m%d).db

# Restore
cp backups/korgo_20260812.db korgo_pro.db
```

> Voir [docs/DEPLOYMENT.md#sauvegarde-et-récupération](docs/DEPLOYMENT.md#sauvegarde-et-récupération)

---

## 🤝 Support & Contribution

### Poser une Question

1. **Consulter la [documentation](docs/INDEX.md)** d'abord
2. **Vérifier les [issues existantes](https://github.com/Madarahaidara/korgopro/issues)**
3. **Créer une nouvelle issue** avec détails et logs

### Contribuer

1. Lire [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)
2. Fork & créer branche : `git checkout -b feature/my-feature`
3. Tester : `pytest`, `black .`, `flake8`
4. Commit : messages conventionnels
5. Push & créer Pull Request

### Codes de Conduite

- Respect mutuellement
- Commentaires constructifs
- Pas de divulgation d'infos privées

---

## 📊 Roadmap

### v0.3.0 (Q4 2026)
- [ ] Components: Input, Select, Table, Modal
- [ ] Theme switcher UI
- [ ] Bcrypt password migration
- [ ] Enhanced error handling & logging
- [ ] Auth module test coverage

### v0.4.0 (Q1 2027)
- [ ] Multi-language (i18n)
- [ ] Mobile-responsive version
- [ ] Cloud backup integration
- [ ] Advanced reporting

> Voir [docs/CHANGELOG.md#upcoming](docs/CHANGELOG.md#upcoming)

---

## 📄 License

[Spécifier votre licence : MIT, GPL, etc.]

---

## 👥 Auteurs & Mainteneurs

- **Créateur** : [Your Name]
- **Mainteneur** : Korgo Team
- **Contributors** : [À complèter]

---

## 📞 Contact

- **Support** : [Email/Discord/Forum]
- **Security Issues** : security@korgo.example.com (confidential)
- **Documentation** : Voir [docs/](docs/)

---

<div align="center">

**Merci d'utiliser Korgo Pro !** ❤️

[⭐ Star on GitHub](https://github.com/Madarahaidara/korgopro) | [📖 Read the Docs](docs/INDEX.md) | [🐛 Report Issues](https://github.com/Madarahaidara/korgopro/issues)

</div>

---

**Dernière mise à jour** : 2026-08-12  
**Version** : 0.2.0  
**Status** : 🟢 Stable (en développement actif)

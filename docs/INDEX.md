# Documentation Index - Korgo Pro

**Bienvenue dans la documentation de Korgo Pro !** Ce fichier vous guide vers les ressources appropriées.

## 📚 Pour Les Utilisateurs

### Premiers Pas

| Document | Audience | Durée |
|----------|----------|-------|
| [README.md](../README.md) | Tous | 5 min |
| [Quick Start](../README.md#installation-rapide) | Nouveaux utilisateurs | 10 min |

### Utilisation

- **Gestion des Ventes** : (À venir)
- **Gestion du Stock** : (À venir)
- **Exportation de Rapports** : (À venir)
- **Gestion du Profil** : (À venir)

---

## 🔧 Pour Les Administrateurs/Ops

### Installation & Déploiement

| Document | Sujet | Durée |
|----------|-------|-------|
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Installation prod, troubleshooting | 30 min |
| [MAINTENANCE.md](./MAINTENANCE.md) | Maintenance long-terme, alertes | 20 min |

### Checklists Utiles

**Avant Go-Live :**
- [ ] Database configurée (PostgreSQL ou SQLite)
- [ ] `.env` rempli avec valeurs de prod
- [ ] Backups en place et testés
- [ ] Utilisateurs créés et testés
- [ ] Certificats SSL (si serveur distant)

**Quotidien :**
- [ ] App est responsive
- [ ] Pas d'erreurs graves en logs
- [ ] Backup effectué

**Mensuellement :**
- [ ] Nettoyer anciens fichiers
- [ ] Mettre à jour dépendances
- [ ] Audit sécurité

---

## 👨‍💻 Pour Les Développeurs

### Avant de Commencer

| Document | Sujet | Temps |
|----------|-------|-------|
| [CONTRIBUTING.md](./CONTRIBUTING.md) | Flux dev, code style, tests | 20 min |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Structure du projet | 15 min |

### Développement

1. **Setup Local** : Voir [CONTRIBUTING.md - Setup Local](./CONTRIBUTING.md#setup-local)
2. **Workflow** : Voir [CONTRIBUTING.md - Flux de Développement](./CONTRIBUTING.md#flux-de-développement)
3. **Tests** : `pytest` dans le répertoire root
4. **Code Style** : `black .` puis `flake8`

### Ressources Techniques

- **Database ORM** : SQLAlchemy (voir [core/database.py](../core/database.py))
- **UI Framework** : PySide6 (voir [ui/](../ui/))
- **Component Library** : [ui/components/README.md](../ui/components/README.md)
- **Theme System** : [ui/themes/README.md](../ui/themes/) (À créer)

### Common Tasks

#### Créer une Nouvelle Vue

```python
# ui/views/my_view.py
from PySide6.QtWidgets import QWidget, QVBoxLayout
from ui.components import CustomButton, CustomCard

class MyView(QWidget):
    def __init__(self, user_data):
        super().__init__()
        self.user_data = user_data
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        # Utiliser les composants
        card = CustomCard(title="Contenu")
        btn = CustomButton("Enregistrer", variant="primary")
        
        layout.addWidget(card)
        layout.addWidget(btn)
```

#### Ajouter un Nouvel Endpoint DB

```python
# core/database_manager.py
def get_my_data(self, filter_id: int):
    """Get custom data by filter."""
    query = "SELECT * FROM my_table WHERE id = ?"
    return self.execute_sql(query, (filter_id,))
```

#### Écrire un Test

```python
# tests/test_my_feature.py
import pytest
from my_module import my_function

class TestMyFeature:
    def test_returns_value(self):
        result = my_function("input")
        assert result == "expected"
    
    def test_handles_error(self):
        with pytest.raises(ValueError):
            my_function(None)
```

---

## 📋 Vue d'Ensemble des Documents

### Structure

```
docs/
├── INDEX.md                    # Ce fichier
├── README.md (root)            # Quick start
├── ARCHITECTURE.md             # Vue système
├── DEPLOYMENT.md               # Installation prod
├── MAINTENANCE.md              # Ops long-terme
├── CONTRIBUTING.md             # Contribution
├── CHANGELOG.md                # Historique versions
├── MAINTENANCE.md              # Maintenance ops
└── (Other docs)
```

### Documents Détaillés

#### 1. **README.md** (root)
**Pour :** Tout le monde  
**Contient :** Quick start, structure, utilisation basique  
**Durée :** 5-10 min

#### 2. **ARCHITECTURE.md**
**Pour :** Devs, architects  
**Contient :** Structure du projet, flux de données, conventions  
**Durée :** 15-20 min

#### 3. **DEPLOYMENT.md**
**Pour :** Admins, DevOps, devs ops  
**Contient :** Installation prod, troubleshooting, backups  
**Durée :** 30 min (référence)

#### 4. **MAINTENANCE.md**
**Pour :** Admins, devops  
**Contient :** Monitoring, perf, sécurité, incidents, compliance  
**Durée :** 20 min (référence)

#### 5. **CONTRIBUTING.md**
**Pour :** Devs, contributeurs  
**Contient :** Workflow git, code style, tests, commit messages  
**Durée :** 20 min

#### 6. **CHANGELOG.md**
**Pour :** Tous (pour voir changements)  
**Contient :** Historique versions, breaking changes, roadmap  
**Durée :** 10-15 min

#### 7. **ui/components/README.md**
**Pour :** Frontend devs  
**Contient :** Component API, usage examples, tokens  
**Durée :** 10-15 min

---

## 🔍 Recherche Rapide

**Besoin de ...**

| Besoin | Document | Section |
|--------|----------|---------|
| Installer localement | CONTRIBUTING.md | [Setup Local](./CONTRIBUTING.md#setup-local) |
| Déployer en prod | DEPLOYMENT.md | [Installation Production](./DEPLOYMENT.md#installation-production) |
| Réparer un bug | DEPLOYMENT.md | [Troubleshooting](./DEPLOYMENT.md#troubleshooting) |
| Écrire du code | CONTRIBUTING.md | [Flux de Développement](./CONTRIBUTING.md#flux-de-développement) |
| Utiliser un component | ui/components/README.md | [Components](../ui/components/README.md) |
| Voir changements | CHANGELOG.md | [Version History](./CHANGELOG.md) |
| Monitorer app | MAINTENANCE.md | [Surveillance](./MAINTENANCE.md#surveillance) |
| Gérer utilisateurs | MAINTENANCE.md | [Gestion Utilisateurs](./MAINTENANCE.md#gestion-des-utilisateurs) |
| Sécuriser l'app | MAINTENANCE.md | [Sécurité](./MAINTENANCE.md#sécurité) |
| Reporter un bug | CHANGELOG.md | [How to Report Issues](./CHANGELOG.md#how-to-report-issues) |

---

## 🚀 Checklists Rapides

### ⚡ Premier Lancement (5 min)

```bash
# 1. Clone
git clone https://github.com/Madarahaidara/korgopro.git
cd korgopro

# 2. Setup
python -m venv venv
.\venv\Scripts\activate  # Windows: .\venv\Scripts\activate
pip install -r requirements.txt

# 3. Copier config
cp .env.example .env

# 4. Lancer
python main.py
```

### 🔄 Mise à Jour (10 min)

1. Backup DB: `pg_dump korgo_pro > backup.sql`
2. Pull: `git pull origin main`
3. Dépendances: `pip install -r requirements.txt`
4. Lancer: `python main.py`
5. Test: Login + créer un élément

### 🧪 Avant une PR (10 min)

```bash
# Format
black .

# Lint
flake8 ui/ core/ controllers/

# Tests
pytest

# Vérifier
git status
```

---

## 📞 Support

### Où Poser des Questions

1. **Issues GitHub** : Pour bugs/features
   - https://github.com/Madarahaidara/korgopro/issues

2. **Discussions** (si enabled) : Pour questions générales
   - https://github.com/Madarahaidara/korgopro/discussions

3. **Documentation** : Chercher d'abord ici !
   - Ctrl+F dans ce fichier
   - Parcourir les guides

### Escalade

- **Bug sécurité** → Contactez security@[domain] (confidentiellement)
- **Data loss** → Voir MAINTENANCE.md [Récupération d'Urgence](./MAINTENANCE.md#récupération-durgence)
- **Performance** → Voir MAINTENANCE.md [Performance](./MAINTENANCE.md#gestion-des-performances)

---

## 📖 Ressources Externes

- [PySide6 Docs](https://doc.qt.io/qtforpython-6/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)
- [Git Best Practices](https://git-scm.com/book/en/v2)
- [Python Style Guide (PEP 8)](https://pep8.org/)

---

## 🗺️ Roadmap Documentation

- [ ] API Documentation (REST endpoints if added)
- [ ] Troubleshooting FAQ
- [ ] Video tutorials
- [ ] Architecture diagrams (Mermaid)
- [ ] Database schema reference
- [ ] Security hardening guide

---

**Dernière mise à jour** : 2026-08-12  
**Version** : 0.2.0  
**Mainteneur** : Korgo Team

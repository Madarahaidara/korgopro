# Guide de Contribution - Korgo Pro

Bienvenue ! Ce guide explique comment contribuer au projet Korgo Pro.

## Table des Matières

1. [Code of Conduct](#code-of-conduct)
2. [Avant de Commencer](#avant-de-commencer)
3. [Flux de Développement](#flux-de-développement)
4. [Style de Code](#style-de-code)
5. [Tests](#tests)
6. [Documentation](#documentation)
7. [Soumettre une PR](#soumettre-une-pr)
8. [Conventions de Commit](#conventions-de-commit)

---

## Code of Conduct

Nous attendons du respect mutuellement, collaborations constructives, et un environnement inclusif.

**Comportements inacceptables :**
- Harcèlement ou discrimination
- Commentaires offensants
- Divulgation de données privées (PII)
- Spam ou auto-promotion

---

## Avant de Commencer

### Prérequis

- **Python 3.11+**
- **Git**
- **PySide6** (framework Qt)
- Venv/virtualenv

### Setup Local

```bash
# 1. Fork & clone
git clone https://github.com/YOUR_USERNAME/korgopro.git
cd korgopro
git remote add upstream https://github.com/Madarahaidara/korgopro.git

# 2. Branche de développement
git checkout -b feature/your-feature-name

# 3. Virtualenv
python -m venv venv
.\venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# 4. Dépendances
pip install -r requirements.txt
pip install pytest pytest-qt pytest-cov black flake8  # dev tools

# 5. Vérifier setup
python main.py  # Doit lancer sans erreur
```

---

## Flux de Développement

### 1. Créer une Branche

```bash
# Toujours partir de main mise à jour
git checkout main
git pull upstream main

# Créer une branche descriptive
git checkout -b feature/add-invoice-export
# ou
git checkout -b bugfix/fix-login-validation
# ou
git checkout -b docs/improve-readme
```

**Conventions de nommage :**
- `feature/...` — Nouvelle fonctionnalité
- `bugfix/...` — Correction de bug
- `docs/...` — Documentation
- `refactor/...` — Refactorisation
- `perf/...` — Amélioration de performance

### 2. Développer Localement

```bash
# Créer/modifier fichiers
# Tester localement : python main.py

# Ajouter & commit
git add .
git commit -m "feature: add invoice export to PDF"

# Push à votre fork
git push origin feature/add-invoice-export
```

### 3. Tester Avant de Commiter

```bash
# Lancer les tests existants
pytest

# Format + linting
black ui/views/  # Formate le code
flake8 ui/views/  # Vérifie le style

# Si erreurs, corriger et recommiter
git add .
git commit --amend  # Ajoute au commit précédent sans créer nouveau
git push -f origin feature/add-invoice-export
```

### 4. Créer une Pull Request

```bash
# Pousser branche vers votre fork
git push origin feature/add-invoice-export

# Aller sur GitHub et créer PR
# - Base: Madarahaidara/korgopro main
# - Compare: YOUR_USERNAME/korgopro feature/add-invoice-export
```

### 5. Code Review & Itération

- Répondez aux commentaires de review
- Apportez les changements demandés
- Re-poussez votre branche (auto-mise à jour de la PR)
- **Ne force-push pas** (sauf si absolument nécessaire)

### 6. Merge

Une fois approuvée, un mainteneur mergera votre PR.

---

## Style de Code

### Python

Nous utilisons **Black** pour le formatting et **flake8** pour la qualité.

```bash
# Formater votre code
black .

# Vérifier les erreurs de style
flake8 ui/ core/ controllers/ utils/
```

**Conventions :**

```python
# Classes : PascalCase
class LoginView(QWidget):
    pass

# Fonctions/variables : snake_case
def handle_login_attempt():
    user_input = input()
    return user_input

# Constantes : UPPER_CASE
MAX_LOGIN_ATTEMPTS = 3
DEFAULT_TIMEOUT = 30

# Docstrings : format Google-style
def save_user(user_id: int, data: dict) -> bool:
    """
    Save user data to database.
    
    Args:
        user_id (int): The user's unique ID
        data (dict): User data to save (name, email, etc.)
    
    Returns:
        bool: True if saved successfully, False otherwise
    
    Raises:
        ValueError: If user_id is invalid
    """
    if user_id <= 0:
        raise ValueError(f"Invalid user_id: {user_id}")
    
    # Implementation...
    return True
```

### Structure de Fichier

```python
# 1. Imports standards
import os
import sys
from datetime import datetime

# 2. Imports tiers
from PySide6.QtWidgets import QWidget, QVBoxLayout
from sqlalchemy import Column, String

# 3. Imports locaux
from core.database import Database
from utils.settings_manager import SettingsManager

# 4. Constants
TIMEOUT_SECONDS = 30

# 5. Classes
class MyView(QWidget):
    ...

# 6. Fonctions
def helper_function():
    ...

# 7. Main / Entry
if __name__ == "__main__":
    ...
```

---

## Tests

### Écrire des Tests

```python
# tests/test_auth.py
import pytest
from controllers.auth_controller import AuthController

class TestAuthentication:
    def setup_method(self):
        """Setup before each test"""
        self.auth = AuthController()
    
    def test_valid_login(self):
        """Test successful login"""
        result = self.auth.authenticate("admin", "password")
        assert result is not None
        assert result['username'] == "admin"
    
    def test_invalid_password(self):
        """Test login with wrong password"""
        result = self.auth.authenticate("admin", "wrong_pass")
        assert result is None
    
    def test_nonexistent_user(self):
        """Test login with nonexistent user"""
        result = self.auth.authenticate("nonexistent", "pass")
        assert result is None
    
    def test_empty_username(self):
        """Test login with empty username"""
        result = self.auth.authenticate("", "password")
        assert result is None
```

### Exécuter les Tests

```bash
# Tous les tests
pytest

# Tests spécifiques
pytest tests/test_auth.py

# Verbose + coverage
pytest -v --cov=. --cov-report=html

# Seulement tests qui matched "login"
pytest -k "login"
```

**Coverage Minimum :** 70% pour le code critique (auth, database)

---

## Documentation

### Docstrings

Utiliser le style Google-style (voir section [Style de Code](#python)):

```python
def calculate_total(items: list, tax_rate: float = 0.1) -> float:
    """
    Calculate total including tax.
    
    Args:
        items (list): List of item prices
        tax_rate (float): Tax percentage (0.1 = 10%). Defaults to 0.1.
    
    Returns:
        float: Total price with tax
    
    Example:
        >>> calculate_total([10, 20, 30], 0.1)
        66.0
    """
    subtotal = sum(items)
    return subtotal * (1 + tax_rate)
```

### Documenter les Vues/Composants

```python
class DashboardView(QWidget):
    """
    Main dashboard view displaying business metrics.
    
    Shows:
    - Sales summary (today, this week, this month)
    - Top products sold
    - Recent transactions
    - Company statistics
    
    Signals:
        - view_changed: Emitted when switching to another view
    
    Attributes:
        - user_data (dict): Current logged-in user info
        - refresh_timer (QTimer): Auto-refresh every 60 seconds
    
    Example:
        dashboard = DashboardView(user_data={'id': 1, 'role': 'admin'})
        main_window.setCentralWidget(dashboard)
    """
```

### Mettre à Jour la Documentation

1. **README.md** — Quick start pour utilisateurs
2. **docs/ARCHITECTURE.md** — Vue générale (mise à jour si changements majeurs)
3. **docs/DEPLOYMENT.md** — Installation & maintenance
4. **docs/CONTRIBUTING.md** — Ce fichier (update si processus change)
5. **docs/CHANGELOG.md** — Chaque version
6. **Code inline** — Docstrings et commentaires pour logique complexe

---

## Soumettre une PR

### Checklist Avant de Soumettre

- [ ] ✅ Code formé avec `black`
- [ ] ✅ Pas d'erreurs `flake8`
- [ ] ✅ Tous les tests passent (`pytest`)
- [ ] ✅ Coverage >= 70% (testé : `--cov`)
- [ ] ✅ Docstrings ajoutés/mis à jour
- [ ] ✅ Pas de `print()` hardcodé (utiliser logger)
- [ ] ✅ Pas de secrets/clés API (utiliser .env)
- [ ] ✅ Branche à jour avec `main`

### Description de la PR

```markdown
## Description
Brief overview of changes.

## Type of Change
- [x] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Related Issues
Fixes #123

## Testing
How to test this change:
1. Run `python main.py`
2. Navigate to Dashboard
3. Verify metrics update correctly

## Screenshots (if applicable)
[Add before/after screenshots]

## Checklist
- [x] Tests pass locally
- [x] Documentation updated
- [x] No breaking changes
```

### Révision & Feedback

- **Soyez ouvert** aux suggestions et feedback
- **Rendez service** aux reviewers en répondant rapidement
- **Améliorez progressivement** plutôt que de tout refaire d'un coup
- **Demandez clarification** si un commentaire n'est pas clair

---

## Conventions de Commit

### Message Format

```
<type>: <subject>

<body>

<footer>
```

**Types :**
- `feat` — Nouvelle fonctionnalité
- `fix` — Correction de bug
- `docs` — Documentation
- `style` — Formatting, braces, semicolons, etc.
- `refactor` — Code restructuring sans changement fonctionnel
- `perf` — Amélioration de performance
- `test` — Ajouter/mettre à jour tests
- `chore` — Dépendances, build config, etc.

**Exemple :**

```
feat: add invoice export to PDF

- Implement export dialog with template selection
- Support multiple invoice formats (standard, compact)
- Add retry logic for failed exports
- Update user settings to remember last format

Fixes #456
```

### Règles

- Sujet : ≤ 50 caractères, pas de point final
- Utiliser l'impératif ("add", pas "added")
- Body : Expliquer le POURQUOI, pas le COMMENT
- Référencer issues : "Fixes #123", "Related to #456"

---

## Arborescence des Branches

```
main (branche stable)
├── feature/add-invoice-export
├── bugfix/fix-login-crash
└── docs/improve-deployment-guide

upstream/main (branche principale du repo)
```

**Avant de merger à main :**
- ✅ All tests pass
- ✅ Code reviewed (2+ approvals)
- ✅ No conflicts
- ✅ CI green

---

## Ressources Utiles

- [Korgo Pro Architecture](ARCHITECTURE.md)
- [Deployment Guide](DEPLOYMENT.md)
- [API Documentation (WIP)](API.md)
- [PySide6 Documentation](https://doc.qt.io/qtforpython-6/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)

---

## Questions ?

- Check existing issues/discussions
- Ask in PR comments
- Email: (contact info if available)
- Read the [Troubleshooting guide](DEPLOYMENT.md#troubleshooting)

---

**Merci d'avoir contribué à Korgo Pro ! 🎉**

Votre travail rend cette application meilleure pour tous.

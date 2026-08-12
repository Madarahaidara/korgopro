Korgo Pro — Guide rapide

Résumé

Korgo Pro est une application de gestion (ventes, stock, facturation) écrite en Python avec une interface PySide6 et une persistance via SQLAlchemy (SQLite par défaut).

Prérequis

- Python 3.11+
- Sur Windows, PowerShell ou cmd
- Recommandé : créer un environnement virtuel (venv)

Installation (Windows PowerShell)

1. Créer et activer un virtualenv :

   python -m venv .venv
   .\.venv\Scripts\Activate.ps1   # PowerShell
   # ou
   .\.venv\Scripts\activate.bat   # cmd

2. Installer les dépendances :

   # Si vous avez requirements.txt
   python -m pip install -r requirements.txt

   # Sinon utilisez pyproject.toml / poetry si vous préférez

Démarrage

- Lancer l'application GUI :

   python main.py

- Scripts utiles :
  - diagnonstique.py  — script de diagnostic
  - recreate_db.py    — recrée une base de données de test (préremplie)
  - init_db.py        — initialiser la base et tables

Configuration via .env

Le projet peut utiliser des variables d'environnement pour la configuration. Exemple : créer un fichier `.env` basésur `.env.example`.

- Fichier exemple : .env.example (à la racine)
- Variable principale : KORGO_DB_URL (par défaut sqlite:///korgo_pro.db)

Tests

- Il existe des scripts de test (test_*.py). Recommandé : standardiser avec pytest.
- Exécuter les tests (après installation des dépendances) :

   pytest

Bonnes pratiques

- Ne pas committer la base SQLite ou fichiers de données (korgo_pro.db, rapports .xlsx, users_export.json). Mettre ces fichiers dans un dossier data/ ignoré par git.
- Utiliser un .env pour secrets et chemins (ne pas committer .env réel).
- Ajouter CI (GitHub Actions) pour exécuter les tests automatiquement.

Documentation

Voir le dossier docs/ pour l'architecture, l'audit de sécurité et d'autres informations techniques :
- docs/architecture.md
- docs/audit_securite_changements.txt

Contact & Contribution

- Ouvrir une issue ou une PR pour proposer des changements.
- Avant de pousser : formater le code et exécuter les tests localement.

Merci — si vous voulez, je peux générer aussi un requirements.txt, ajouter un .github/workflows de CI, ou rendre le chemin DB configurable.
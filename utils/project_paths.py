from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def add_project_root_to_path() -> None:
    """Ajoute la racine du projet au sys.path si nécessaire."""
    root = str(PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def get_project_root() -> Path:
    """Retourne le répertoire racine du projet."""
    return PROJECT_ROOT


def get_resource_path(relative_path: str) -> str:
    """Retourne le chemin absolu d'une ressource relative à la racine du projet."""
    return str(PROJECT_ROOT / relative_path)

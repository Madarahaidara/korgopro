import sys
from pathlib import Path
from .project_paths import get_project_root


def resource_path(relative_path: str) -> str:
    """Obtenez le chemin absolu vers une ressource, fonctionne pour dev et pour PyInstaller."""
    try:
        base_path = Path(sys._MEIPASS)
    except AttributeError:
        base_path = get_project_root()

    return str(base_path / relative_path)


def get_icon_path(icon_name: str) -> str:
    """Retourne le chemin complet d'une icône."""
    return resource_path(f"ui/icons/{icon_name}")

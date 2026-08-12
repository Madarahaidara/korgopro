from pathlib import Path
import json
from PySide6.QtWidgets import QApplication
from utils.resource_path import resource_path


def _load_variables(theme_key: str = "light") -> dict:
    """Charge les variables de thème depuis ui/themes/variables.json."""
    vars_path = Path(resource_path("ui/themes/variables.json"))
    if not vars_path.exists():
        return {}
    try:
        data = json.loads(vars_path.read_text(encoding="utf-8"))
        # Retourner le jeu de variables demandé (ex: 'light' ou 'dark')
        return data.get(theme_key, {})
    except Exception:
        return {}


def load_theme(app: QApplication | None = None, theme: str = "light") -> str:
    """Charge et applique un thème QSS à l'application Qt.

    Si une application est fournie, le style est appliqué directement.
    Le fichier ui/themes/variables.json peut définir des tokens qui seront
    substitués dans le QSS (ex: {{PRIMARY}}, {{BG}}).

    Retourne le contenu CSS final appliqué.
    """
    theme_path = Path(resource_path(f"ui/themes/{theme}.qss"))
    if not theme_path.exists():
        raise FileNotFoundError(f"Theme file not found: {theme_path}")

    qss = theme_path.read_text(encoding="utf-8")

    # Charger les variables pour le thème (light/dark)
    vars_map = _load_variables(theme_key=("dark" if theme.lower().startswith("dark") else "light"))

    # Substituer les tokens {{KEY}} par leurs valeurs
    if vars_map:
        for k, v in vars_map.items():
            token = f"{{{{{k}}}}}"
            qss = qss.replace(token, v)

    if app is not None:
        app.setStyleSheet(qss)
    return qss

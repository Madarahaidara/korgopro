from pathlib import Path
from PySide6.QtWidgets import QApplication
from utils.resource_path import resource_path


def load_theme(app: QApplication | None = None, theme: str = "light") -> str:
    """Charge et applique un thème QSS à l'application Qt.

    Si une application est fournie, le style est appliqué directement.
    Retourne le contenu CSS du thème pour usage optionnel.
    """
    theme_path = Path(resource_path(f"ui/themes/{theme}.qss"))
    if not theme_path.exists():
        raise FileNotFoundError(f"Theme file not found: {theme_path}")

    qss = theme_path.read_text(encoding="utf-8")
    if app is not None:
        app.setStyleSheet(qss)
    return qss

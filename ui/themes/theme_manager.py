import re
from pathlib import Path

from PySide6.QtWidgets import QApplication

from utils.resource_path import resource_path

# Références aux ressources Qt (":/icons/xxx.svg") dans les feuilles de style.
# Le projet n'embarque pas de bundle .qrc : ces chemins sont résolus vers les
# fichiers réels de "ui/icons/" (dev comme build PyInstaller via _MEIPASS).
_QSS_ICON_REF = re.compile(r":/icons/([\w\-./]+)")


def _resolve_qss_icons(qss: str) -> str:
    """Remplace les chemins de ressources Qt ':/icons/<fichier>' par le chemin
    absolu du fichier correspondant dans ui/icons/ (slashes positifs)."""
    return _QSS_ICON_REF.sub(
        lambda m: Path(resource_path(f"ui/icons/{m.group(1)}")).as_posix(), qss
    )


def load_theme(app: QApplication | None = None, theme: str = "light") -> str:
    """Charge et applique un thème QSS à l'application Qt.

    Si une application est fournie, le style est appliqué directement.
    Retourne le contenu CSS du thème pour usage optionnel.
    """
    theme_path = Path(resource_path(f"ui/themes/{theme}.qss"))
    if not theme_path.exists():
        raise FileNotFoundError(f"Theme file not found: {theme_path}")

    qss = theme_path.read_text(encoding="utf-8")
    qss = _resolve_qss_icons(qss)
    if app is not None:
        app.setStyleSheet(qss)
    return qss

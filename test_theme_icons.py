"""Test : charge tous les thèmes et vérifie que les icônes ':/icons/' sont
résolues vers des fichiers existants (aucun avertissement Qt attendu)."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication

from ui.themes.theme_manager import load_theme, _resolve_qss_icons
from utils.resource_path import resource_path

app = QApplication([])

for theme in ("light", "dark", "admin", "dashboard", "login", "main",
              "sale_view", "stock_view"):
    qss = load_theme(app, theme=theme)
    assert ":/icons/" not in qss, f"{theme}.qss: référence ':/icons/' restante"
    # Vérifier que chaque chemin d'icône présent dans le QSS existe
    import re
    for path in re.findall(r"url\(([^)]+)\)", qss):
        if path.endswith((".svg", ".png", ".ico")):
            assert os.path.exists(path), f"{theme}.qss: icône absente {path}"
    print(f"  {theme:12s} OK")

# Cas ciblé : admin.qss
qss = _resolve_qss_icons("image: url(:/icons/check.svg); url(:/icons/arrow-down.svg)")
assert qss.startswith("image: url(") and "ui/icons/check.svg" in qss
assert "ui/icons/arrow-down.svg" in qss
print("  admin.qss    OK (check.svg + arrow-down.svg résolus)")

# Appliquer le thème admin à l'app : Qt ne doit émettre aucun avertissement
load_theme(app, theme="admin")
print("\nTous les thèmes se chargent sans référence Qt invalide.")

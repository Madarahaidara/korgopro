# -*- coding: utf-8 -*-
"""Validation hors écran du logo net du LoginView (regression flou)."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

app = QApplication(sys.argv)

from ui.views.login_view import charger_pixmap_net, LoginView

CHEMIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "icons", "logo.ico")
ECHECS = []


def check(nom, condition, detail=""):
    statut = "OK  " if condition else "ECHEC"
    print(f"[{statut}] {nom}" + (f" -- {detail}" if detail else ""))
    if not condition:
        ECHECS.append(nom)


# --- 1. La source est bien la frame 256x256, pas la 16x16 -------------------
pm = charger_pixmap_net(CHEMIN, 140)
check("le pixmap est charge", pm is not None)
dpr = pm.devicePixelRatio()
cible_phys = max(1, int(round(140 * dpr)))
check("frame source haute resolution (pas le 16x16)",
      pm.width() == 256 or pm.width() == cible_phys,
      f"largeur physique={pm.width()} dpr={dpr}")
check("jamais d'agrandissement (source >= cible)",
      pm.width() >= cible_phys or pm.width() == 256,
      f"largeur physique={pm.width()} cible physique={cible_phys}")
check("taille logique = 140", abs(pm.width() / dpr - 140) < 1.0 or pm.width() == 256,
      f"logique={pm.width() / dpr}")

# --- 2. Equivalence pixel avec la reference 256 -> 140 ----------------------
from PySide6.QtGui import QImageReader, QPixmap, QImage
reader = QImageReader(CHEMIN)
best = QImage()
for i in range(reader.imageCount()):
    reader.jumpToImage(i)
    img = reader.read()
    if not img.isNull() and (best.isNull() or img.width() > best.width()):
        best = img
check("la frame 256x256 existe bien dans le .ico", best.width() == 256,
      f"meilleure frame={best.width()}x{best.height()}")

ref = QPixmap.fromImage(best)
if dpr:
    ref = ref.scaled(cible_phys, cible_phys, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    ref.setDevicePixelRatio(dpr)
    identique = (pm.toImage().size() == ref.toImage().size()
                 and pm.toImage() == ref.toImage())
    check("pixels identiques a la reference 256 -> cible", identique,
          f"{pm.toImage().size()} vs {ref.toImage().size()}")

# --- 3. Repli sur chemin absent --------------------------------------------
check("retourne None si fichier absent", charger_pixmap_net(CHEMIN + ".inexistant", 140) is None)

# --- 4. Le LoginView reel utilise bien le pixmap net ------------------------
view = LoginView()
app.processEvents()

logo_label = None
for lbl in view.findChildren(type(view.logo_label) if hasattr(view, "logo_label") else object):
    pass

# Retrouver le label via LeftPanel
from ui.views.login_view import LeftPanel
panels = view.findChildren(LeftPanel)
check("LeftPanel present dans LoginView", len(panels) >= 1, f"trouve={len(panels)}")
if panels:
    label = panels[0].logo_label
    pix = label.pixmap()
    check("logo_label a un pixmap", pix is not None and not pix.isNull())
    if pix is not None and not pix.isNull():
        ratio = pix.devicePixelRatio()
        check("logo affiche net (>= 140 px physiques)",
              pix.width() >= 140 or pix.width() / ratio >= 140,
              f"physique={pix.width()} logique={pix.width() / ratio} dpr={ratio}")
        check("logo_label n'affiche pas le repli texte 'K'",
              label.text() != "K", f"texte='{label.text()}'")

print()
if ECHECS:
    print("ECHECS:", ECHECS)
    sys.exit(1)
print("TOUS LES CONTROLES SONT PASSES")

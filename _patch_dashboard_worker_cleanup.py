# -*- coding: utf-8 -*-
"""Patch : retire de `dashboard_view.py` le code remplace par le worker.

Le tableau de bord collecte desormais ses donnees dans `DashboardDataWorker`
(thread) et ne fait plus aucune requete dans le thread UI. Les methodes
obsoletes sont supprimees pour eviter qu'elles soient reutilisees :

  * `debug_sales_data`   : bruit de debogage (4 requetes + prints au login) ;
  * `load_chart_data`    : remplacee par `_render_chart` (rendu seul) ;
  * `load_top_products`  : remplacee par `_render_top_products` ;
  * `load_recent_sales`  : remplacee par `_render_recent_sales` ;
  * `_get_db_session`    : plus aucun appelant dans la vue.

Lancement : python _patch_dashboard_worker_cleanup.py
"""
from __future__ import annotations

import io
import re
import sys

PATH = "ui/views/dashboard_view.py"

# Nouvelles lignes de fin de fichier preservees a l'identique (\n ou \r\n).
raw = io.open(PATH, "rb").read()
newline = "\r\n" if b"\r\n" in raw[:8000] else "\n"
src = raw.decode("utf-8")

avant = len(src.splitlines())

# 1) Les quatre methodes obsoletes, de `debug_sales_data` jusqu'a `refresh_data`.
debut = src.index("    def debug_sales_data(self):")
fin = src.index("    def refresh_data(self):")
assert debut < fin, "bornes invalides"
supprime = src[debut:fin]
src = src[:debut] + src[fin:]

# 2) `_get_db_session`, plus utilisee par la vue.
src, n = re.subn(
    r"\n    def _get_db_session\(self\):\n"
    r"(?:.*\n)*?"
    r"        return SessionLocal\(\)\n",
    "\n",
    src,
    count=1,
)

assert n == 1, "methode _get_db_session introuvable"
assert "debug_sales_data" not in src
assert "load_chart_data" not in src
assert "load_top_products" not in src
assert "load_recent_sales" not in src

with io.open(PATH, "w", encoding="utf-8", newline="") as handle:
    handle.write(src.replace("\r\n", newline) if newline == "\n" else src)

print(f"OK : {len(supprime.splitlines())} lignes obsoletes supprimees, "
      f"{avant} -> {len(src.splitlines())} lignes")
sys.exit(0)

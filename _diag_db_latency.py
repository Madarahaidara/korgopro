# -*- coding: utf-8 -*-
"""Latence reelle de la base desktop (Supabase) : connexion + SELECT 1.

POURQUOI
--------
Chaque requete executee dans le thread Qt gele l'interface pendant au moins un
aller-retour reseau. Ce script mesure cet aller-retour pour transformer le
nombre de requetes (voir ``_diag_freeze_desktop.py``) en secondes de gel.

LECTURE SEULE : seuls des ``SELECT 1`` sont envoyes, aucune donnee modifiee.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text  # noqa: E402

from core.database import engine  # noqa: E402


def main() -> int:
    print(f"Cible : {engine.url.host}:{engine.url.port} "
          f"({engine.url.get_backend_name()})")

    t0 = time.perf_counter()
    try:
        conn = engine.connect()  # ouvre TCP + TLS + auth si le pool est vide
    except Exception as exc:  # noqa: BLE001 - diagnostic hors-ligne tolere
        print(f"Connexion impossible : {type(exc).__name__}: {exc}")
        return 1
    print(f"Connexion (pool vide)  : {(time.perf_counter() - t0) * 1000:7.0f} ms")

    t0 = time.perf_counter()
    conn.execute(text("SELECT 1"))
    print(f"1er SELECT 1           : {(time.perf_counter() - t0) * 1000:7.0f} ms")

    temps = []
    for _ in range(5):
        t0 = time.perf_counter()
        conn.execute(text("SELECT 1"))
        temps.append((time.perf_counter() - t0) * 1000.0)
    conn.close()

    print("SELECT 1 suivants (ms) : " + ", ".join(f"{v:.0f}" for v in temps))
    moyenne = sum(temps) / len(temps)
    print(f"Aller-retour moyen     : {moyenne:7.0f} ms")

    # Traduction en gel d'ecran : requetes mesurees par _diag_freeze_desktop.
    # « avant » = etat initial ; « apres » = requetes restant dans le thread
    # UI apres les correctifs P0 (le reste part en worker).
    for label, avant, apres in (("Login (MainWindow)", 123, 3),
                                ("Dashboard (timer 30 s)", 11, 0),
                                ("StockView (ouverture)", 43, 43),
                                ("Battement session (5 min)", 1, 0)):
        print(f"{label:28s} {avant:3d} -> {apres:3d} req.  "
              f"{avant * moyenne / 1000:6.1f} s -> {apres * moyenne / 1000:5.1f} s "
              "de gel thread UI")

    return 0


if __name__ == "__main__":
    sys.exit(main())

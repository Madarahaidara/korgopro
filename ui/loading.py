# ui/loading.py
"""Retours visuels de latence : spinner animé et voile de chargement.

La latence vers Supabase (~150 ms par aller-retour, mesurés dans
``docs/diagnostic_gel_desktop.md``) rend tous les chargements visibles.
Plutôt que de figer le thread Qt (l'erreur initiale), les vues lancent leurs
requêtes dans un worker QThread et signalent l'attente avec ces widgets :

* ``LoadingSpinner`` — arc tournant peint (aucune image externe) ;
* ``LoadingOverlay`` — voile translucide + spinner + message, posé au-dessus
  d'un widget parent (vue entière ou simple tableau).

Comportements clés :

* **Anti-scintillement** : le voile ne s'affiche qu'après ``SHOW_DELAY_MS``
  (150 ms). Une réponse rapide (SQLite local, cache) ne fait jamais clignoter
  l'écran ; une réponse lente (réseau) apparaît donc signifiée.
* **Profondeur** : ``start()``/``stop()`` s'apparient (un départ de worker /
  un résultat livré). Deux chargements superposés restent affichés jusqu'au
  dernier ``stop()``.
* **Durée écoulée** : au-delà d'une seconde, le message affiche le temps
  (« … (3 s) ») pour rendre la latence réseau explicite à l'utilisateur.
"""

import time

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

#: Teinte principale de l'application (voir splash / thèmes).
DEFAULT_COLOR = QColor("#268B83")


class LoadingSpinner(QWidget):
    """Arc tournant peint — aucun asset externe, coût quasi nul.

    Le QTimer (30 ms) ne fait qu'invalider le widget : le repaint est
    minuscule et ne pèse rien sur le thread UI même pendant une latence.
    """

    def __init__(self, parent=None, size=32, color=None, thickness=3):
        super().__init__(parent)
        self._angle = 0
        self._color = color or DEFAULT_COLOR
        self._thickness = thickness
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._rotate)

    def _rotate(self):
        self._angle = (self._angle + 10) % 360
        self.update()

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Piste claire (fond de l'arc).
        track = QColor(self._color)
        track.setAlpha(40)
        pen_track = QPen(track)
        pen_track.setWidthF(self._thickness)
        pen_track.setCapStyle(Qt.RoundCap)
        painter.setPen(pen_track)
        rect = self.rect().adjusted(4, 4, -4, -4)
        painter.drawArc(rect, 0, 360 * 16)

        # Arc actif.
        pen = QPen(self._color)
        pen.setWidthF(self._thickness)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, self._angle * 16, 200 * 16)


class LoadingOverlay(QWidget):
    """Voile translucide + spinner + message posé au-dessus d'un parent.

    Usage (toujours par paires worker/rendu)::

        overlay = LoadingOverlay(self, "Chargement des factures…")
        …
        overlay.start()          # juste avant worker.start()
        …
        overlay.stop()           # première ligne du slot de rendu (et d'erreur)

    ``start()`` accepte un message pour les vues qui couvrent plusieurs
    chargements (ex. admin : journal système vs journal des ventes).
    """

    #: Délai avant affichage : pas de scintillement sur réponse rapide.
    SHOW_DELAY_MS = 150

    def __init__(self, parent, message="Chargement…", color=None):
        super().__init__(parent)
        self.setObjectName("LoadingOverlay")
        self._depth = 0
        self._message = message
        self._shown_at = None
        self._color = color or DEFAULT_COLOR

        self.setStyleSheet(
            "LoadingOverlay {"
            " background-color: rgba(255, 255, 255, 185);"
            " border-radius: 6px;"
            "}"
        )

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(8)

        self._spinner = LoadingSpinner(size=36, color=self._color)
        layout.addWidget(self._spinner, 0, Qt.AlignHCenter)

        self._label = QLabel(message)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setWordWrap(True)
        self._label.setStyleSheet(
            "color: #2F4255; font-size: 12px;"
            " background: transparent; border: none;"
        )
        layout.addWidget(self._label, 0, Qt.AlignHCenter)

        # Anti-scintillement : affichage différé de SHOW_DELAY_MS.
        self._show_timer = QTimer(self)
        self._show_timer.setSingleShot(True)
        self._show_timer.setInterval(self.SHOW_DELAY_MS)
        self._show_timer.timeout.connect(self._show_now)

        # Compteur d'attente affiché au-delà d'une seconde.
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._update_elapsed)

        # Suit les redimensionnements du parent couvert.
        if parent is not None:
            parent.installEventFilter(self)
            self.setGeometry(parent.rect())
        self.hide()

    # ----- état ----------------------------------------------------------

    @property
    def depth(self):
        """Nombre de chargements ouverts non soldés (0 = tout terminé)."""
        return self._depth

    def eventFilter(self, obj, event):
        if obj is self.parent() and event.type() == QEvent.Resize:
            self.setGeometry(obj.rect())
        return super().eventFilter(obj, event)

    # ----- cycle de vie ---------------------------------------------------

    def start(self, message=None):
        """Ouvre une attente (appelé au lancement d'un worker)."""
        if message:
            self._message = message
        self._depth += 1
        self._label.setText(self._message)
        if self.isVisible():
            # Déjà affiché par un autre chargement : texte rafraîchi seul.
            return
        if not self._show_timer.isActive():
            # Pas de redémarrage : le premier départ fixe l'affichage.
            self._show_timer.start()

    def stop(self):
        """Ferme une attente (appelé une fois par résultat livré)."""
        if self._depth > 0:
            self._depth -= 1
        if self._depth > 0:
            # Un autre chargement reste ouvert : le voile reste en place.
            self._label.setText(self._message)
            return
        self._show_timer.stop()
        self._elapsed_timer.stop()
        self._spinner.stop()
        self._shown_at = None
        self.hide()

    # ----- affichage ------------------------------------------------------

    def _show_now(self):
        if self._depth <= 0:
            return  # tout était terminé avant le délai : rien à afficher
        self._shown_at = time.monotonic()
        self._label.setText(self._message)
        self._spinner.start()
        self.raise_()
        self.show()
        self._elapsed_timer.start()

    def _update_elapsed(self):
        if self._shown_at is None or not self.isVisible():
            return
        seconds = int(time.monotonic() - self._shown_at)
        if seconds >= 1:
            self._label.setText(f"{self._message} ({seconds} s)")

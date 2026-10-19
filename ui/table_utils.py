"""Règles communes de lisibilité et de redimensionnement des tableaux Qt."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView


_STRETCH_HEADERS = (
    "produit", "client", "description", "raison", "notes", "note",
    "utilisateur", "fournisseur", "catégorie", "categorie", "désignation",
    "designation", "nom", "email", "adresse", "détail", "detail",
)


def configure_responsive_table(table, preserve_column_modes=False):
    """Applique des largeurs souples et une navigation cohérente à un tableau.

    Les colonnes descriptives prennent l'espace disponible. Les autres restent
    redimensionnables et le défilement horizontal apparaît lorsque la fenêtre
    est trop étroite pour préserver leur lisibilité.
    """
    if not isinstance(table, QTableView):
        return

    model = table.model()
    if model is None or model.columnCount() == 0:
        return

    header = table.horizontalHeader()
    if not preserve_column_modes:
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setMinimumSectionSize(82)
        header.setMaximumSectionSize(1600)
        header.setStretchLastSection(False)

        stretch_columns = []
        for column in range(model.columnCount()):
            label = str(model.headerData(column, Qt.Horizontal, Qt.DisplayRole) or "")
            normalized = label.strip().lower()
            if any(name in normalized for name in _STRETCH_HEADERS):
                header.setSectionResizeMode(column, QHeaderView.Stretch)
                stretch_columns.append(column)
        if not stretch_columns:
            last_label = str(
                model.headerData(model.columnCount() - 1, Qt.Horizontal, Qt.DisplayRole) or ""
            ).strip().lower()
            if last_label not in {"action", "actions", "actions "}:
                header.setStretchLastSection(True)
    # Les tableaux purement numériques ou à colonnes d'action gardent leur
    # largeur choisie par l'écran et peuvent défiler horizontalement.
    table.setAlternatingRowColors(True)
    table.setWordWrap(False)
    table.setTextElideMode(Qt.ElideRight)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
    table.verticalHeader().setDefaultSectionSize(40)

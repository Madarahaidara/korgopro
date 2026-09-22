# ui/views/settings_view.py
"""Vue « Paramètres » (desktop) — présentation en cartes et barre d'action fixe.

REFONTE VISUELLE
----------------
* **Style centralisé** dans ``ui/themes/settings_view.qss``, piloté par
  ``objectName`` et calé sur la palette bleu marine de l'application
  (``#2F4255`` / ``#3A6B9F`` / ``#1B3A7A``, fond ``#f8fafc``) : l'écran ne
  détonne plus face à Dashboard, Caisse et Administration (l'ancien écran
  utilisait un bleu ciel ``#3b82f6`` codé en dur dans ~500 lignes de QSS
  éparpillées dans le code).
* **Cartes de section** (icône + titre + phrase d'explication) et champs en
  blocs « libellé au-dessus », répartis en 2 colonnes sur écran large et
  1 colonne en dessous (voir :class:`FieldGrid`).
* **Un seul niveau de défilement** par onglet et **barre d'action persistante**
  (Annuler / Enregistrer toujours accessibles, plus besoin de descendre).
  L'ancienne version imbriquait une zone défilante par onglet dans une zone
  défilante générale.
* **Icônes SVG** de ``ui/icons`` à la place des emojis (cohérent avec le reste
  de l'application).

CORRECTIONS AU PASSAGE
----------------------
* Le badge d'état compare la **saisie au cliché de la saisie** : auparavant le
  dictionnaire complet des paramètres était comparé au formulaire, donc
  toujours différent — l'écran annonçait « modifications non sauvegardées » et
  activait Enregistrer dès l'ouverture.
* La **devise** n'est plus silencieusement remplacée par « USD » : la liste
  propose les codes réellement utilisés par l'application (``FCFA`` par défaut
  dans ``SettingsManager`` et les modèles) et conserve une valeur inconnue au
  lieu de l'écraser à l'enregistrement.
* Le logo affiche un aperçu avec le nom/poids du fichier au lieu d'un emoji
  « 📷 » de 90 px.
* Numérotation : aperçu en direct du prochain numéro de facture.

L'API publique ne change pas : signal ``settings_changed``, gestionnaire
``settings_manager``, méthodes :meth:`load_current_settings`,
:meth:`save_all_settings`, :meth:`select_logo`, :meth:`clear_logo`,
:meth:`load_logo_preview`, :meth:`load_footer_template`.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
    QSizePolicy, QSpinBox, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from ui.icons.icon_manager import IconManager
from utils.resource_path import resource_path
from utils.settings_manager import SettingsManager

#: Devises proposées : ``(libellé affiché, code enregistré)``.
#: ``FCFA`` est la valeur par défaut de ``SettingsManager`` et des modèles
#: métier : elle doit rester sélectionnable pour ne pas être écrasée.
CURRENCY_CHOICES = (
    ("FCFA — Franc CFA", "FCFA"),
    ("XAF — Franc CFA (CEMAC)", "XAF"),
    ("XOF — Franc CFA (UEMOA)", "XOF"),
    ("USD — Dollar américain", "USD"),
    ("EUR — Euro", "EUR"),
)

#: Langues : ``(libellé, code)`` — ordre conservé (index 0 = français).
LANGUAGE_CHOICES = (
    ("Français", "fr"),
    ("English", "en"),
)

#: Formats de date : ``(libellé, format Qt)``.
DATE_FORMAT_CHOICES = (
    ("JJ/MM/AAAA", "dd/MM/yyyy"),
    ("MM/JJ/AAAA", "MM/dd/yyyy"),
    ("AAAA-MM-JJ", "yyyy-MM-dd"),
)

#: Modèles de pied de facture proposés en un clic.
FOOTER_TEMPLATES = (
    ("Standard",
     "Merci pour votre confiance.\n"
     "Veuillez régler par virement bancaire sous 30 jours."),
    ("Minimaliste", "Merci pour votre confiance."),
    ("Professionnel",
     "Société XYZ\nSIRET: 123 456 789\nRCS: Paris B\n"
     "IBAN: FR76 XXXX XXXX XXXX\n\nMerci pour votre confiance."),
)

#: Anciens libellés de modèles (avec emoji) : conservés pour compatibilité si
#: un appelant les utilise encore.
_LEGACY_TEMPLATE_ALIASES = {
    "📝 Standard": "Standard",
    "✨ Minimaliste": "Minimaliste",
    "💼 Professionnel": "Professionnel",
}


# ---------------------------------------------------------------------------
# Briques d'interface réutilisables
# ---------------------------------------------------------------------------
class FormField(QWidget):
    """Bloc de formulaire : libellé, champ de saisie, aide optionnelle.

    Présentation « libellé au-dessus du champ » (plutôt que libellé à gauche) :
    le bloc reste lisible sur une colonne comme sur deux, et les libellés longs
    ne compriment plus les champs.
    """

    def __init__(self, label, widget, hint=None, parent=None):
        super().__init__(parent)
        self.widget = widget
        self.label = QLabel(label)
        self.label.setObjectName("FieldLabel")
        self.hint = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.label)

        widget.setMinimumHeight(38)
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(widget)

        if hint:
            self.hint = QLabel(hint)
            self.hint.setObjectName("FieldHint")
            self.hint.setWordWrap(True)
            layout.addWidget(self.hint)


class FieldGrid(QWidget):
    """Grille de champs : 2 colonnes sur écran large, 1 colonne en dessous.

    Le nombre de colonnes suit la largeur réellement offerte : les formulaires
    restent compacts sur grand écran (moins de défilement) et lisibles sur un
    écran étroit, sans jamais tronquer un champ.
    """

    #: Largeur en dessous de laquelle on repasse à une seule colonne.
    MIN_FIELD_WIDTH = 320

    def __init__(self, columns=2, parent=None):
        super().__init__(parent)
        self.max_columns = max(1, columns)
        self._fields = []      # [(FormField, span)]
        self._columns = 0

        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(20)
        self.grid.setVerticalSpacing(16)

    def add_field(self, label, widget, hint=None, span=1):
        """Ajouter un champ (``span`` : nombre de colonnes occupées)."""
        field = FormField(label, widget, hint)
        self._fields.append((field, max(1, int(span))))
        self._apply_columns(force=True)
        return widget

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_columns()

    def _apply_columns(self, force=False):
        width = self.width()
        columns = self.max_columns
        if width > 0:
            columns = max(1, min(self.max_columns, width // self.MIN_FIELD_WIDTH))

        if not force and columns == self._columns:
            return
        self._columns = columns

        # Repositionner les champs (les widgets ne sont pas détruits)
        while self.grid.count():
            self.grid.takeAt(0)

        row = 0
        column = 0
        for field, span in self._fields:
            span = min(span, columns)
            if column + span > columns:
                row += 1
                column = 0
            self.grid.addWidget(field, row, column, 1, span)
            column += span
            if column >= columns:
                row += 1
                column = 0


class SectionCard(QFrame):
    """Carte de section : bandeau (icône + titre + sous-titre) et corps.

    Toute la présentation est déléguée au QSS via ``objectName`` — la carte
    n'embarque plus un seul ``setStyleSheet`` local.
    """

    def __init__(self, icon_name, title, subtitle=None, parent=None):
        super().__init__(parent)
        self.setObjectName("SectionCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("CardHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(12)

        icon_label = QLabel()
        icon_label.setObjectName("CardIcon")
        icon = _icon(icon_name)
        if icon is not None:
            icon_label.setPixmap(icon.pixmap(20, 20))
        else:
            icon_label.hide()
        header_layout.addWidget(icon_label)

        titles = QVBoxLayout()
        titles.setSpacing(1)
        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        titles.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("CardSubtitle")
            subtitle_label.setWordWrap(True)
            titles.addWidget(subtitle_label)
        header_layout.addLayout(titles)
        header_layout.addStretch()

        layout.addWidget(header)

        body = QWidget()
        body.setObjectName("CardBody")
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(20, 18, 20, 20)
        self.body_layout.setSpacing(16)
        layout.addWidget(body)


def _icon(name):
    """Charge ``ui/icons/<name>.svg`` ; renvoie ``None`` si absent.

    Icônes posées en décoration des cartes uniquement : leur absence ne doit
    jamais empêcher l'écran de fonctionner (déploiement sans ressources).
    """
    from PySide6.QtGui import QIcon

    path = resource_path(os.path.join("ui", "icons", f"{name}.svg"))
    if not os.path.exists(path):
        return None
    return QIcon(path)


# ---------------------------------------------------------------------------
# Vue principale
# ---------------------------------------------------------------------------
class SettingsView(QWidget):
    """Écran « Paramètres » — trois onglets, barre d'action persistante.

    L'API publique de l'ancienne version est conservée : signal
    ``settings_changed``, méthodes :meth:`load_current_settings`,
    :meth:`save_all_settings`, :meth:`select_logo`, :meth:`clear_logo`,
    :meth:`load_logo_preview`, :meth:`load_footer_template`.
    """

    settings_changed = Signal(dict)

    #: État « propre » du formulaire : pastille neutre, boutons désactivés.
    STATE_CLEAN = "saved"
    #: État « modifié » : pastille ambre, Annuler/Enregistrer actifs.
    STATE_DIRTY = "dirty"

    def __init__(self, user_data, settings_manager):
        super().__init__()
        self.user_data = user_data
        self.settings_manager = settings_manager
        self.current_logo_path = ""
        #: Cliché des valeurs du formulaire telles qu'enregistrées — la
        #: comparaison « saisie vs cliché » remplace l'ancien bug qui comparait
        #: le dictionnaire complet des paramètres (toujours différent).
        self._saved_form = {}

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setObjectName("settingsView")

        self._build_ui()
        self.load_current_settings()
        self._connect_signals()

    # -- construction -------------------------------------------------------
    def _build_ui(self):
        self.setStyleSheet(self._load_stylesheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        self.tab_widget = self._create_tabs()
        root.addWidget(self.tab_widget, 1)

        root.addWidget(self._create_action_bar())

        # Raccourcis clavier : Enregistrer / Annuler sans quitter la saisie.
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save_all_settings)
        QShortcut(QKeySequence("Escape"), self, activated=self.load_current_settings)

    @staticmethod
    def _load_stylesheet():
        """Charge la feuille dédiée ``ui/themes/settings_view.qss``.

        Une feuille séparée (plutôt qu'un patch dans le thème global) garde
        l'écran lisible : retouches futures en un seul endroit, sans risque
        pour les autres vues.
        """
        path = resource_path(os.path.join("ui", "themes", "settings_view.qss"))
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return handle.read()
        except OSError:
            # Dégradé contrôlé : l'écran reste utilisable sans habillage.
            return ""

    def _create_tabs(self):
        tabs = QTabWidget()
        tabs.setObjectName("SettingsTabs")
        tabs.setDocumentMode(True)
        tabs.addTab(self._make_page(self._create_company_tab()), "Entreprise")
        tabs.addTab(self._make_page(self._create_general_tab()), "Général")
        tabs.addTab(self._make_page(self._create_billing_tab()), "Facturation")
        return tabs

    @staticmethod
    def _make_page(content):
        """Page d'onglet : un seul niveau de défilement.

        L'ancienne version imbriquait une scroll area par onglet dans une
        scroll area générale — molette imprévisible, doubles barres.
        """
        page = QWidget()
        page.setObjectName("settingsView")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("TabScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        return page

    def _create_company_tab(self):
        """Onglet Entreprise : identité, informations légales, logo."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 22, 28, 28)
        layout.setSpacing(20)

        # Carte 1 : informations de l'entreprise
        self.company_name_input = QLineEdit()
        self.company_name_input.setPlaceholderText("Nom de l'entreprise")
        self.company_address_input = QLineEdit()
        self.company_address_input.setPlaceholderText("Adresse complète")
        self.company_po_box_input = QLineEdit()
        self.company_po_box_input.setPlaceholderText("Ex. : BP 1234")
        self.company_phone_input = QLineEdit()
        self.company_phone_input.setPlaceholderText("Ex. : +237 6 00 00 00 00")
        self.company_email_input = QLineEdit()
        self.company_email_input.setPlaceholderText("contact@entreprise.com")

        info_card = SectionCard(
            "logo", "Informations de l'entreprise",
            "Ces informations apparaissent en en-tête des factures et proformas.")
        info_grid = FieldGrid(columns=2)
        info_grid.add_field("Nom", self.company_name_input)
        info_grid.add_field("Téléphone", self.company_phone_input)
        info_grid.add_field("Adresse", self.company_address_input, span=2)
        info_grid.add_field("Boîte postale", self.company_po_box_input)
        info_grid.add_field("Email", self.company_email_input)
        info_card.body_layout.addWidget(info_grid)
        layout.addWidget(info_card)

        # Carte 2 : informations légales
        self.company_ifu_input = QLineEdit()
        self.company_ifu_input.setPlaceholderText("N° d'identification fiscale unique")
        self.company_rccm_input = QLineEdit()
        self.company_rccm_input.setPlaceholderText("Registre du commerce")

        legal_card = SectionCard(
            "check", "Informations légales",
            "Numéros mentionnés sur les documents officiels (IFU, RCCM).")
        legal_grid = FieldGrid(columns=2)
        legal_grid.add_field("IFU", self.company_ifu_input)
        legal_grid.add_field("RCCM", self.company_rccm_input)
        legal_card.body_layout.addWidget(legal_grid)
        layout.addWidget(legal_card)

        # Carte 3 : logo — aperçu réel (nom + poids du fichier) au lieu de l'
        # ancien emoji « 📷 » de 90 px.
        self.logo_preview = QLabel()
        self.logo_preview.setObjectName("LogoImage")
        self.logo_preview.setAlignment(Qt.AlignCenter)
        self.logo_filename = QLabel("Aucun logo sélectionné")
        self.logo_filename.setObjectName("LogoFilename")
        self.logo_hint = QLabel("PNG, JPG ou SVG — format carré recommandé")
        self.logo_hint.setObjectName("LogoHint")

        self.select_logo_btn = QPushButton("Choisir un logo")
        self.select_logo_btn.setObjectName("GhostButton")
        self.select_logo_btn.setMinimumHeight(34)
        self.select_logo_btn.clicked.connect(self.select_logo)
        self.clear_logo_btn = QPushButton("Supprimer")
        self.clear_logo_btn.setObjectName("DangerButton")
        self.clear_logo_btn.setMinimumHeight(34)
        self.clear_logo_btn.setEnabled(False)
        self.clear_logo_btn.clicked.connect(self.clear_logo)

        logo_card = SectionCard(
            "edit", "Logo de l'entreprise",
            "Affiché en haut des factures imprimées.")
        logo_box = QHBoxLayout()
        logo_box.setSpacing(18)
        preview = QFrame()
        preview.setObjectName("LogoPreview")
        preview.setFixedSize(104, 104)
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(2, 2, 2, 2)
        preview_layout.addWidget(self.logo_preview)
        logo_box.addWidget(preview, 0, Qt.AlignTop)

        logo_side = QVBoxLayout()
        logo_side.setSpacing(6)
        logo_side.addWidget(self.logo_filename)
        logo_side.addWidget(self.logo_hint)
        logo_buttons = QHBoxLayout()
        logo_buttons.setSpacing(8)
        logo_buttons.addWidget(self.select_logo_btn)
        logo_buttons.addWidget(self.clear_logo_btn)
        logo_buttons.addStretch()
        logo_side.addLayout(logo_buttons)
        logo_side.addStretch()
        logo_box.addLayout(logo_side, 1)
        logo_card.body_layout.addLayout(logo_box)
        layout.addWidget(logo_card)

        layout.addStretch()
        return container

    def _create_general_tab(self):
        """Onglet Général : langue, devise, format de date, affichage."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 22, 28, 28)
        layout.setSpacing(20)

        # Les combos portent leur code en ``data`` (itemData) : plus de
        # correspondance fragile par libellé ou par index, et une valeur
        # inconnue du fichier de réglages est conservée telle quelle.
        self.language_combo = QComboBox()
        for label_, code in LANGUAGE_CHOICES:
            self.language_combo.addItem(label_, code)
        self.currency_combo = QComboBox()
        for label_, code in CURRENCY_CHOICES:
            self.currency_combo.addItem(label_, code)
        self.date_format_combo = QComboBox()
        for label_, fmt in DATE_FORMAT_CHOICES:
            self.date_format_combo.addItem(label_, fmt)

        prefs_card = SectionCard(
            "monitor", "Préférences générales",
            "Langue de l'interface, devise des montants, format des dates.")
        prefs_grid = FieldGrid(columns=2)
        prefs_grid.add_field(
            "Langue", self.language_combo, hint="Appliquée après redémarrage.")
        prefs_grid.add_field(
            "Devise", self.currency_combo,
            hint="Symbole affiché sur les factures et rapports.")
        prefs_grid.add_field(
            "Format de date", self.date_format_combo,
            hint="Utilisé sur les documents imprimés.", span=2)
        prefs_card.body_layout.addWidget(prefs_grid)
        layout.addWidget(prefs_card)

        self.animation_check = QCheckBox("Activer les animations")
        self.animation_check.setChecked(True)
        display_card = SectionCard(
            "check", "Affichage", "Effets visuels de l'application.")
        display_card.body_layout.addWidget(self.animation_check)
        layout.addWidget(display_card)

        layout.addStretch()
        return container

    def _create_billing_tab(self):
        """Onglet Facturation : fiscalité, numérotation, pied de page."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 22, 28, 28)
        layout.setSpacing(20)

        # Carte 1 : fiscalité
        self.tax_rate_spin = QDoubleSpinBox()
        self.tax_rate_spin.setRange(0, 100)
        self.tax_rate_spin.setSuffix(" %")
        self.tax_rate_spin.setDecimals(2)
        self.tax_rate_spin.setValue(20.0)
        self.discount_spin = QDoubleSpinBox()
        self.discount_spin.setRange(0, 100)
        self.discount_spin.setSuffix(" %")
        self.discount_spin.setDecimals(2)

        tax_card = SectionCard(
            "add", "Paramètres fiscaux",
            "Taux appliqués par défaut sur les nouvelles ventes.")
        tax_grid = FieldGrid(columns=2)
        tax_grid.add_field("Taux de TVA", self.tax_rate_spin)
        tax_grid.add_field("Remise par défaut", self.discount_spin)
        tax_card.body_layout.addWidget(tax_grid)
        layout.addWidget(tax_card)

        # Carte 2 : numérotation — même format que le module de vente
        # (``sale_services.generate_sale_number`` : préfixe + numéro sur
        # 4 chiffres, ex. FAC0001) et aperçu en direct.
        self.invoice_prefix_input = QLineEdit()
        self.invoice_prefix_input.setPlaceholderText("FAC")
        self.invoice_prefix_input.setMaxLength(5)
        self.invoice_prefix_input.setFixedWidth(90)
        self.invoice_start_spin = QSpinBox()
        self.invoice_start_spin.setRange(1, 99999)
        self.invoice_start_spin.setPrefix("N° ")
        self.invoice_start_spin.setFixedWidth(130)
        self.payment_terms_spin = QSpinBox()
        self.payment_terms_spin.setRange(0, 90)
        self.payment_terms_spin.setSuffix(" jours")
        self.payment_terms_spin.setValue(30)
        self.payment_terms_spin.setSpecialValueText("À réception")

        numbering_card = SectionCard(
            "refresh", "Numérotation des factures",
            "Format « préfixe + numéro sur 4 chiffres » (ex. : FAC0001), "
            "identique au module de vente.")
        numbering_grid = FieldGrid(columns=2)
        numbering_widget = QWidget()
        numbering_row = QHBoxLayout(numbering_widget)
        numbering_row.setContentsMargins(0, 0, 0, 0)
        numbering_row.setSpacing(8)
        numbering_row.addWidget(self.invoice_prefix_input)
        numbering_row.addWidget(self.invoice_start_spin)
        numbering_row.addStretch()
        numbering_grid.add_field(
            "Préfixe et prochain numéro", numbering_widget,
            hint="Choisir un numéro supérieur au dernier numéro émis.")
        self.number_preview = QLabel()
        self.number_preview.setObjectName("NumberPreview")
        self.number_preview.setAlignment(Qt.AlignCenter)
        numbering_grid.add_field("Aperçu du prochain numéro", self.number_preview)
        numbering_grid.add_field(
            "Délai de paiement", self.payment_terms_spin,
            hint="Mentionné sur les conditions de règlement.")
        numbering_card.body_layout.addWidget(numbering_grid)
        layout.addWidget(numbering_card)

        # Carte 3 : pied de page
        self.invoice_footer_input = QTextEdit()
        self.invoice_footer_input.setPlaceholderText(
            "Merci pour votre confiance.\n"
            "Conditions de paiement : 30 jours nets.")
        self.invoice_footer_input.setMinimumHeight(80)
        self.invoice_footer_input.setMaximumHeight(120)

        template_row = QHBoxLayout()
        template_row.setSpacing(8)
        template_row.addStretch()
        for label_, _code in FOOTER_TEMPLATES:
            btn = QPushButton(label_)
            btn.setObjectName("GhostButton")
            btn.setMinimumHeight(32)
            btn.clicked.connect(
                lambda checked=False, name=label_: self.load_footer_template(name))
            template_row.addWidget(btn)

        footer_card = SectionCard(
            "edit", "Pied de page des factures",
            "Texte imprimé en bas de chaque facture.")
        footer_card.body_layout.addWidget(self.invoice_footer_input)
        footer_card.body_layout.addLayout(template_row)
        layout.addWidget(footer_card)

        layout.addStretch()
        return container

    def _create_action_bar(self):
        """Barre d'action persistante : toujours visible, même en bas de page.

        L'ancien pied de page était DANS la zone défilante : dès qu'on
        modifiait un champ en bas d'onglet, les boutons disparaissaient sous
        le pli.
        """
        bar = QFrame()
        bar.setObjectName("ActionBar")
        bar.setMaximumHeight(74)
        bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(12)

        # Pastille d'état : la propriété dynamique ``state`` pilote la couleur
        # dans le QSS (``StatusPill[state="dirty"]``) — plus de setStyleSheet
        # réécrit à chaque frappe.
        self.status_pill = QFrame()
        self.status_pill.setObjectName("StatusPill")
        self.status_pill.setProperty("state", self.STATE_CLEAN)
        pill_layout = QHBoxLayout(self.status_pill)
        pill_layout.setContentsMargins(14, 6, 14, 6)
        pill_layout.setSpacing(8)
        self.status_pill_icon = QLabel("●")
        self.status_pill_icon.setObjectName("StatusPillIcon")
        self.status_pill_text = QLabel("Paramètres à jour")
        self.status_pill_text.setObjectName("StatusPillText")
        pill_layout.addWidget(self.status_pill_icon)
        pill_layout.addWidget(self.status_pill_text)
        layout.addWidget(self.status_pill)

        layout.addStretch()

        self.cancel_btn = QPushButton("Annuler")
        self.cancel_btn.setObjectName("SecondaryButton")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.load_current_settings)
        layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Enregistrer")
        self.save_btn.setObjectName("PrimaryButton")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_all_settings)
        layout.addWidget(self.save_btn)
        return bar

    # -- réactivité ---------------------------------------------------------
    def _connect_signals(self):
        """Détection des modifications : tout champ connecté fait basculer la
        pastille et active Annuler/Enregistrer."""
        for widget in (
            self.company_name_input, self.company_address_input,
            self.company_po_box_input, self.company_phone_input,
            self.company_email_input, self.company_ifu_input,
            self.company_rccm_input, self.invoice_prefix_input,
        ):
            widget.textChanged.connect(self._on_settings_changed)

        for combo in (self.language_combo, self.currency_combo,
                      self.date_format_combo):
            combo.currentIndexChanged.connect(self._on_settings_changed)

        self.animation_check.stateChanged.connect(self._on_settings_changed)

        for spin in (self.tax_rate_spin, self.discount_spin,
                     self.invoice_start_spin, self.payment_terms_spin):
            spin.valueChanged.connect(self._on_settings_changed)

        self.invoice_footer_input.textChanged.connect(self._on_settings_changed)

        # Aperçu en direct du prochain numéro de facture.
        self.invoice_prefix_input.textChanged.connect(self._update_number_preview)
        self.invoice_start_spin.valueChanged.connect(self._update_number_preview)

    def _update_number_preview(self):
        """Aperçu du prochain numéro, au format du module de vente."""
        prefix = self.invoice_prefix_input.text().strip() or "FAC"
        self.number_preview.setText(f"{prefix}{self.invoice_start_spin.value():04d}")

    def _on_settings_changed(self, *_args):
        """Compare la saisie au cliché des valeurs enregistrées.

        L'ancien code comparait la saisie au dictionnaire COMPLET des
        paramètres : le formulaire n'en couvre qu'une partie, donc la
        comparaison échouait toujours — « modifications non sauvegardées »
        était affiché et Enregistrer actif dès l'ouverture.
        """
        dirty = self._collect_form_data() != self._saved_form
        self.save_btn.setEnabled(dirty)
        self.cancel_btn.setEnabled(dirty)
        self._set_state(self.STATE_DIRTY if dirty else self.STATE_CLEAN)

    def _set_state(self, state):
        """Bascule la pastille d'état via la propriété QSS ``state``."""
        if self.status_pill.property("state") == state:
            return
        self.status_pill.setProperty("state", state)
        if state == self.STATE_DIRTY:
            self.status_pill_text.setText("Modifications non enregistrées")
        else:
            self.status_pill_text.setText("Paramètres à jour")
        # Ré-appliquer le QSS sur les widgets concernés.
        for widget in (self.status_pill, self.status_pill_text):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    # -- données ------------------------------------------------------------
    def _collect_form_data(self):
        """Collecte les données du formulaire (mêmes clés qu'avant)."""
        return {
            "company_name": self.company_name_input.text().strip(),
            "company_address": self.company_address_input.text().strip(),
            "company_po_box": self.company_po_box_input.text().strip(),
            "company_phone": self.company_phone_input.text().strip(),
            "company_email": self.company_email_input.text().strip(),
            "company_ifu": self.company_ifu_input.text().strip(),
            "company_rccm": self.company_rccm_input.text().strip(),
            "company_logo": self.current_logo_path,
            "language": self.language_combo.currentData(),
            "currency": self._get_currency_code(),
            "date_format": self.date_format_combo.currentData(),
            "animations": self.animation_check.isChecked(),
            "tax_rate": self.tax_rate_spin.value(),
            "discount": self.discount_spin.value(),
            "invoice_prefix": self.invoice_prefix_input.text().strip(),
            "invoice_start": self.invoice_start_spin.value(),
            "payment_terms": self.payment_terms_spin.value(),
            "invoice_footer": self.invoice_footer_input.toPlainText().strip(),
        }

    def _get_currency_code(self):
        """Code devise réellement sélectionné (``itemData``).

        L'ancienne version retombait silencieusement sur « USD » pour toute
        valeur inconnue : avec le défaut ``FCFA`` de ``SettingsManager``, la
        simple ouverture de l'écran puis Enregistrer changeait la devise de
        toutes les factures. Désormais ``FCFA`` est proposé et une valeur
        inconnue est préservée.
        """
        code = self.currency_combo.currentData()
        return code if code else self.currency_combo.currentText()

    @staticmethod
    def _select_combo_data(combo, value, label=None):
        """Sélectionne l'élément dont la ``data`` vaut ``value``.

        Si la valeur n'est pas dans la liste (réglage ancien ou manuel), elle
        est ajoutée en fin de liste plutôt qu'écrasée.
        """
        index = combo.findData(value)
        if index < 0:
            combo.addItem(label or str(value), value)
            index = combo.count() - 1
        combo.setCurrentIndex(index)

    def load_footer_template(self, template_name):
        """Charge un modèle de pied de page (accepte les anciens noms emoji)."""
        name = _LEGACY_TEMPLATE_ALIASES.get(template_name, template_name)
        for label_, text in FOOTER_TEMPLATES:
            if label_ == name:
                self.invoice_footer_input.setPlainText(text)
                return

    def select_logo(self):
        """Sélectionne un logo via une boîte de dialogue fichier."""
        path, _filter = QFileDialog.getOpenFileName(
            self, "Sélectionner un logo", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.svg)")
        if path:
            self.current_logo_path = path
            self.load_logo_preview(path)
            self.clear_logo_btn.setEnabled(True)
            self._on_settings_changed()

    def load_logo_preview(self, logo_path):
        """Affiche l'aperçu du logo (image + nom et poids du fichier)."""
        pixmap = QPixmap(logo_path)
        if pixmap.isNull():
            self.logo_preview.setText("Image\ninvalide")
            self.logo_filename.setText(os.path.basename(logo_path))
            QMessageBox.warning(
                self, "Logo",
                "Impossible de charger cette image.\n"
                "Vérifiez que le fichier est une image valide.")
            return
        self.logo_preview.setPixmap(pixmap.scaled(
            88, 88, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.logo_filename.setText(
            f"{os.path.basename(logo_path)} — "
            f"{os.path.getsize(logo_path) / 1024:.0f} Ko")

    def clear_logo(self):
        """Retire le logo de l'aperçu (l'enregistrement validera le choix)."""
        self.logo_preview.setText("Aucun\nlogo")
        self.logo_filename.setText("Aucun logo sélectionné")
        self.current_logo_path = ""
        self.clear_logo_btn.setEnabled(False)
        self._on_settings_changed()

    def load_current_settings(self):
        """Recharge les paramètres depuis ``SettingsManager`` et remet
        la pastille à l'état « propre »."""
        settings = self.settings_manager.get_all_settings()

        self.company_name_input.setText(settings.get("company_name", ""))
        self.company_address_input.setText(settings.get("company_address", ""))
        self.company_po_box_input.setText(settings.get("company_po_box", ""))
        self.company_phone_input.setText(settings.get("company_phone", ""))
        self.company_email_input.setText(settings.get("company_email", ""))
        self.company_ifu_input.setText(settings.get("company_ifu", ""))
        self.company_rccm_input.setText(settings.get("company_rccm", ""))

        # Logo
        logo_path = settings.get("company_logo", "")
        self.current_logo_path = logo_path
        if logo_path and os.path.exists(logo_path):
            self.load_logo_preview(logo_path)
            self.clear_logo_btn.setEnabled(True)
        else:
            self.logo_preview.setText("Aucun\nlogo")
            self.logo_filename.setText("Aucun logo sélectionné")
            self.current_logo_path = ""
            self.clear_logo_btn.setEnabled(False)

        # Général
        self._select_combo_data(
            self.language_combo, settings.get("language", "fr"))
        self._select_combo_data(
            self.currency_combo, settings.get("currency", "FCFA"))
        self._select_combo_data(
            self.date_format_combo, settings.get("date_format", "dd/MM/yyyy"))
        self.animation_check.setChecked(settings.get("animations", True))

        # Facturation
        self.tax_rate_spin.setValue(float(settings.get("tax_rate", 20.0)))
        self.discount_spin.setValue(float(settings.get("discount", 0)))
        self.invoice_prefix_input.setText(settings.get("invoice_prefix", "FAC"))
        self.invoice_start_spin.setValue(int(settings.get("invoice_start", 1)))
        self.payment_terms_spin.setValue(int(settings.get("payment_terms", 30)))
        self.invoice_footer_input.setPlainText(settings.get("invoice_footer", ""))
        self._update_number_preview()

        # Cliché de la saisie telle qu'enregistrée : la pastille compare
        # désormais ce cliché (et non plus le dictionnaire complet).
        self._saved_form = self._collect_form_data()
        self.save_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self._set_state(self.STATE_CLEAN)

    def save_all_settings(self):
        """Valide, enregistre, émet ``settings_changed`` puis recharge."""
        if not self.company_name_input.text().strip():
            QMessageBox.warning(
                self, "Champ requis",
                "Le nom de l'entreprise est obligatoire.")
            self.company_name_input.setFocus()
            return

        settings_to_save = self._collect_form_data()

        if self.settings_manager.save_settings(settings_to_save):
            self.settings_changed.emit(settings_to_save)
            self.load_current_settings()
        else:
            QMessageBox.critical(
                self, "Erreur",
                "Erreur lors de l'enregistrement des paramètres.")

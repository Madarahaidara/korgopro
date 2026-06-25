# ui/views/settings_view.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QGroupBox, QMessageBox, QFileDialog,
    QTextEdit, QDoubleSpinBox, QComboBox, QTabWidget, QFrame,
    QSpinBox, QCheckBox, QGridLayout, QSizePolicy, QScrollArea,
    QSpacerItem
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QFont, QIcon
import os
from utils.settings_manager import SettingsManager


class SettingsView(QWidget):
    """Vue des paramètres moderne et 100% responsive"""
    
    settings_changed = Signal(dict)
    
    def __init__(self, user_data, settings_manager):
        super().__init__()
        self.user_data = user_data
        self.settings_manager = settings_manager
        self.current_logo_path = ""
        self.original_settings = {}
        
        # Configuration du widget principal
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        self._build_ui()
        self.load_current_settings()
        self._connect_signals()
        
    def _build_ui(self):
        """Construit l'interface utilisateur responsive"""
        # Layout principal avec marges adaptatives
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(15)
        
        # En-tête avec titre
        header_widget = self._create_header()
        main_layout.addWidget(header_widget)
        
        # Onglets avec scroll
        self.tab_widget = QTabWidget()
        self.tab_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                background: white;
            }
            QTabBar::tab {
                padding: 10px 20px;
                margin-right: 4px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                background: #f0f0f0;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background: #3498db;
                color: white;
            }
            QTabBar::tab:hover:!selected {
                background: #e0e0e0;
            }
        """)
        
        # Création des onglets avec scroll areas
        self.tab_widget.addTab(self._create_scrollable_tab(self._create_company_tab()), "🏢 Entreprise")
        self.tab_widget.addTab(self._create_scrollable_tab(self._create_general_tab()), "⚙️ Général")
        self.tab_widget.addTab(self._create_scrollable_tab(self._create_billing_tab()), "📄 Facturation")
        
        main_layout.addWidget(self.tab_widget)
        
        # Pied de page avec boutons d'action
        footer_widget = self._create_footer()
        main_layout.addWidget(footer_widget)
    
    def _create_header(self):
        """Crée l'en-tête responsive"""
        header = QWidget()
        header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        header.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2c3e50, stop:1 #34495e);
                border-radius: 8px;
            }
        """)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 15, 20, 15)
        
        # Titre
        title_label = QLabel("⚙️ Paramètres")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: white;")
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # Sous-titre
        subtitle = QLabel("Configuration de l'application")
        subtitle.setStyleSheet("color: #bdc3c7; font-size: 12px;")
        subtitle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        layout.addWidget(title_label)
        layout.addWidget(subtitle)
        
        return header
    
    def _create_footer(self):
        """Crée le pied de page avec les boutons d'action"""
        footer = QFrame()
        footer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        footer.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 8px;
                border: 1px solid #e0e0e0;
            }
        """)
        
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(15)
        
        # Statut
        self.status_label = QLabel("✅ Aucune modification")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #27ae60;
                font-weight: bold;
                padding: 5px 10px;
                background-color: #e8f5e9;
                border-radius: 4px;
            }
        """)
        self.status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        layout.addWidget(self.status_label)
        layout.addStretch()
        
        # Bouton Annuler
        self.cancel_btn = QPushButton("✖ Annuler")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setMinimumWidth(120)
        self.cancel_btn.setMinimumHeight(36)
        self.cancel_btn.clicked.connect(self.load_current_settings)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        
        # Bouton Enregistrer
        self.save_btn = QPushButton("💾 Enregistrer")
        self.save_btn.setEnabled(False)
        self.save_btn.setMinimumWidth(120)
        self.save_btn.setMinimumHeight(36)
        self.save_btn.clicked.connect(self.save_all_settings)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #219653;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        
        layout.addWidget(self.cancel_btn)
        layout.addWidget(self.save_btn)
        
        return footer
    
    def _create_scrollable_tab(self, content_widget):
        """Encapsule un widget dans une QScrollArea responsive"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: #f0f0f0;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a0a0a0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """)
        
        # Configurer le widget contenu
        content_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scroll.setWidget(content_widget)
        
        return scroll
    
    def _create_company_tab(self):
        """Crée l'onglet Entreprise responsive"""
        tab = QWidget()
        tab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        main_layout = QVBoxLayout(tab)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Groupe Informations de l'entreprise
        basic_group = QGroupBox("Informations de l'entreprise")
        basic_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        basic_group.setStyleSheet(self._get_group_box_style())
        
        basic_layout = QGridLayout(basic_group)
        basic_layout.setSpacing(12)
        basic_layout.setContentsMargins(20, 25, 20, 20)
        basic_layout.setColumnStretch(0, 0)  # Labels
        basic_layout.setColumnStretch(1, 1)  # Champs
        
        # Nom
        label_name = QLabel("Nom :")
        label_name.setMinimumWidth(120)
        label_name.setStyleSheet("font-weight: 500; color: #2c3e50;")
        
        self.company_name_input = QLineEdit()
        self.company_name_input.setPlaceholderText("Nom de votre entreprise")
        self.company_name_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.company_name_input.setMinimumHeight(32)
        self.company_name_input.setStyleSheet(self._get_input_style())
        
        basic_layout.addWidget(label_name, 0, 0)
        basic_layout.addWidget(self.company_name_input, 0, 1)
        
        # Adresse
        label_address = QLabel("Adresse :")
        label_address.setMinimumWidth(120)
        label_address.setStyleSheet("font-weight: 500; color: #2c3e50;")
        
        self.company_address_input = QLineEdit()
        self.company_address_input.setPlaceholderText("Adresse de l'entreprise")
        self.company_address_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.company_address_input.setMinimumHeight(32)
        self.company_address_input.setStyleSheet(self._get_input_style())
        
        basic_layout.addWidget(label_address, 1, 0)
        basic_layout.addWidget(self.company_address_input, 1, 1)
        
        # Boîte Postale
        label_po_box = QLabel("Boîte Postale :")
        label_po_box.setMinimumWidth(120)
        label_po_box.setStyleSheet("font-weight: 500; color: #2c3e50;")
        
        self.company_po_box_input = QLineEdit()
        self.company_po_box_input.setPlaceholderText("BP 1234")
        self.company_po_box_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.company_po_box_input.setMinimumHeight(32)
        self.company_po_box_input.setStyleSheet(self._get_input_style())
        
        basic_layout.addWidget(label_po_box, 2, 0)
        basic_layout.addWidget(self.company_po_box_input, 2, 1)
        
        # Téléphone
        label_phone = QLabel("Téléphone :")
        label_phone.setMinimumWidth(120)
        label_phone.setStyleSheet("font-weight: 500; color: #2c3e50;")
        
        self.company_phone_input = QLineEdit()
        self.company_phone_input.setPlaceholderText("Téléphone")
        self.company_phone_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.company_phone_input.setMinimumHeight(32)
        self.company_phone_input.setStyleSheet(self._get_input_style())
        
        basic_layout.addWidget(label_phone, 3, 0)
        basic_layout.addWidget(self.company_phone_input, 3, 1)
        
        # Email
        label_email = QLabel("Email :")
        label_email.setMinimumWidth(120)
        label_email.setStyleSheet("font-weight: 500; color: #2c3e50;")
        
        self.company_email_input = QLineEdit()
        self.company_email_input.setPlaceholderText("Email")
        self.company_email_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.company_email_input.setMinimumHeight(32)
        self.company_email_input.setStyleSheet(self._get_input_style())
        
        basic_layout.addWidget(label_email, 4, 0)
        basic_layout.addWidget(self.company_email_input, 4, 1)
        
        main_layout.addWidget(basic_group)
        
        # Groupe Informations légales
        legal_group = QGroupBox("Informations légales")
        legal_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        legal_group.setStyleSheet(self._get_group_box_style())
        
        legal_layout = QGridLayout(legal_group)
        legal_layout.setSpacing(12)
        legal_layout.setContentsMargins(20, 25, 20, 20)
        legal_layout.setColumnStretch(0, 0)
        legal_layout.setColumnStretch(1, 1)
        
        # IFU
        label_ifu = QLabel("IFU :")
        label_ifu.setMinimumWidth(120)
        label_ifu.setStyleSheet("font-weight: 500; color: #2c3e50;")
        
        self.company_ifu_input = QLineEdit()
        self.company_ifu_input.setPlaceholderText("IFU - Ex: 1234567890A")
        self.company_ifu_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.company_ifu_input.setMinimumHeight(32)
        self.company_ifu_input.setStyleSheet(self._get_input_style())
        
        legal_layout.addWidget(label_ifu, 0, 0)
        legal_layout.addWidget(self.company_ifu_input, 0, 1)
        
        # RCCM
        label_rccm = QLabel("RCCM :")
        label_rccm.setMinimumWidth(120)
        label_rccm.setStyleSheet("font-weight: 500; color: #2c3e50;")
        
        self.company_rccm_input = QLineEdit()
        self.company_rccm_input.setPlaceholderText("RCCM - Ex: RC-BNV-2023-1234")
        self.company_rccm_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.company_rccm_input.setMinimumHeight(32)
        self.company_rccm_input.setStyleSheet(self._get_input_style())
        
        legal_layout.addWidget(label_rccm, 1, 0)
        legal_layout.addWidget(self.company_rccm_input, 1, 1)
        
        main_layout.addWidget(legal_group)
        
        # Groupe Logo
        logo_group = QGroupBox("Logo")
        logo_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        logo_group.setStyleSheet(self._get_group_box_style())
        
        logo_layout = QHBoxLayout(logo_group)
        logo_layout.setContentsMargins(20, 25, 20, 20)
        logo_layout.setSpacing(20)
        
        # Prévisualisation
        self.logo_preview = QLabel()
        self.logo_preview.setFixedSize(120, 120)
        self.logo_preview.setAlignment(Qt.AlignCenter)
        self.logo_preview.setText("📷 Aucun logo")
        self.logo_preview.setStyleSheet("""
            QLabel {
                background-color: #f8f9fa;
                border: 2px dashed #bdc3c7;
                border-radius: 8px;
                color: #7f8c8d;
                font-size: 12px;
            }
        """)
        self.logo_preview.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
        # Boutons
        buttons_widget = QWidget()
        buttons_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        buttons_layout = QVBoxLayout(buttons_widget)
        buttons_layout.setSpacing(10)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        
        self.select_logo_btn = QPushButton("📁 Choisir logo")
        self.select_logo_btn.setMinimumHeight(36)
        self.select_logo_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.select_logo_btn.clicked.connect(self.select_logo)
        self.select_logo_btn.setStyleSheet(self._get_button_style("#3498db", "#2980b9"))
        
        self.clear_logo_btn = QPushButton("🗑 Supprimer")
        self.clear_logo_btn.setMinimumHeight(36)
        self.clear_logo_btn.setEnabled(False)
        self.clear_logo_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.clear_logo_btn.clicked.connect(self.clear_logo)
        self.clear_logo_btn.setStyleSheet(self._get_button_style("#e74c3c", "#c0392b"))
        
        buttons_layout.addWidget(self.select_logo_btn)
        buttons_layout.addWidget(self.clear_logo_btn)
        
        logo_layout.addWidget(self.logo_preview)
        logo_layout.addWidget(buttons_widget)
        logo_layout.addStretch()
        
        main_layout.addWidget(logo_group)
        
        # Espacement flexible
        spacer = QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)
        main_layout.addSpacerItem(spacer)
        
        return tab
    
    def _create_general_tab(self):
        """Crée l'onglet Général responsive"""
        tab = QWidget()
        tab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        main_layout = QVBoxLayout(tab)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Groupe Paramètres généraux
        general_group = QGroupBox("Paramètres généraux")
        general_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        general_group.setStyleSheet(self._get_group_box_style())
        
        general_layout = QGridLayout(general_group)
        general_layout.setSpacing(12)
        general_layout.setContentsMargins(20, 25, 20, 20)
        general_layout.setColumnStretch(0, 0)
        general_layout.setColumnStretch(1, 1)
        
        # Langue
        label_language = QLabel("Langue :")
        label_language.setMinimumWidth(120)
        label_language.setStyleSheet("font-weight: 500; color: #2c3e50;")
        
        self.language_combo = QComboBox()
        self.language_combo.addItems(["🇫🇷 Français", "🇬🇧 English"])
        self.language_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.language_combo.setMinimumHeight(32)
        self.language_combo.setStyleSheet(self._get_combo_style())
        
        general_layout.addWidget(label_language, 0, 0)
        general_layout.addWidget(self.language_combo, 0, 1)
        
        # Devise
        label_currency = QLabel("Devise :")
        label_currency.setMinimumWidth(120)
        label_currency.setStyleSheet("font-weight: 500; color: #2c3e50;")
        
        self.currency_combo = QComboBox()
        self.currency_combo.addItems([
            "💵 Dollar US ($) - USD",
            "💰 Franc CFA (FCFA) - XAF",
            "💰 Franc CFA (FCFA) - XOF"
        ])
        self.currency_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.currency_combo.setMinimumHeight(32)
        self.currency_combo.setStyleSheet(self._get_combo_style())
        
        general_layout.addWidget(label_currency, 1, 0)
        general_layout.addWidget(self.currency_combo, 1, 1)
        
        # Format de date
        label_date = QLabel("Format date :")
        label_date.setMinimumWidth(120)
        label_date.setStyleSheet("font-weight: 500; color: #2c3e50;")
        
        self.date_format_combo = QComboBox()
        self.date_format_combo.addItems([
            "📅 jj/mm/aaaa",
            "📅 mm/jj/aaaa",
            "📅 aaaa-mm-jj"
        ])
        self.date_format_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.date_format_combo.setMinimumHeight(32)
        self.date_format_combo.setStyleSheet(self._get_combo_style())
        
        general_layout.addWidget(label_date, 2, 0)
        general_layout.addWidget(self.date_format_combo, 2, 1)
        
        main_layout.addWidget(general_group)
        
        # Groupe Affichage
        display_group = QGroupBox("Affichage")
        display_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        display_group.setStyleSheet(self._get_group_box_style())
        
        display_layout = QVBoxLayout(display_group)
        display_layout.setContentsMargins(20, 25, 20, 20)
        display_layout.setSpacing(10)
        
        self.animation_check = QCheckBox("🎨 Activer les animations")
        self.animation_check.setChecked(True)
        self.animation_check.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.animation_check.setStyleSheet("""
            QCheckBox {
                font-weight: 500;
                color: #2c3e50;
                spacing: 10px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
            }
        """)
        
        display_layout.addWidget(self.animation_check)
        
        main_layout.addWidget(display_group)
        
        # Espacement flexible
        spacer = QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)
        main_layout.addSpacerItem(spacer)
        
        return tab
    
    def _create_billing_tab(self):
        """Crée l'onglet Facturation responsive"""
        tab = QWidget()
        tab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        main_layout = QVBoxLayout(tab)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Groupe Paramètres fiscaux
        tax_group = QGroupBox("Paramètres fiscaux")
        tax_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        tax_group.setStyleSheet(self._get_group_box_style())
        
        tax_layout = QGridLayout(tax_group)
        tax_layout.setSpacing(12)
        tax_layout.setContentsMargins(20, 25, 20, 20)
        tax_layout.setColumnStretch(0, 0)
        tax_layout.setColumnStretch(1, 1)
        
        # Taux de TVA
        label_tax = QLabel("Taux TVA :")
        label_tax.setMinimumWidth(120)
        label_tax.setStyleSheet("font-weight: 500; color: #2c3e50;")
        
        self.tax_rate_spin = QDoubleSpinBox()
        self.tax_rate_spin.setRange(0, 100)
        self.tax_rate_spin.setSuffix(" %")
        self.tax_rate_spin.setDecimals(2)
        self.tax_rate_spin.setValue(20.0)
        self.tax_rate_spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.tax_rate_spin.setMinimumHeight(32)
        self.tax_rate_spin.setStyleSheet(self._get_spinbox_style())
        
        tax_layout.addWidget(label_tax, 0, 0)
        tax_layout.addWidget(self.tax_rate_spin, 0, 1)
        
        # Remise par défaut
        label_discount = QLabel("Remise :")
        label_discount.setMinimumWidth(120)
        label_discount.setStyleSheet("font-weight: 500; color: #2c3e50;")
        
        self.discount_spin = QDoubleSpinBox()
        self.discount_spin.setRange(0, 100)
        self.discount_spin.setSuffix(" %")
        self.discount_spin.setDecimals(2)
        self.discount_spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.discount_spin.setMinimumHeight(32)
        self.discount_spin.setStyleSheet(self._get_spinbox_style())
        
        tax_layout.addWidget(label_discount, 1, 0)
        tax_layout.addWidget(self.discount_spin, 1, 1)
        
        main_layout.addWidget(tax_group)
        
        # Groupe Numérotation
        numbering_group = QGroupBox("Numérotation")
        numbering_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        numbering_group.setStyleSheet(self._get_group_box_style())
        
        numbering_layout = QGridLayout(numbering_group)
        numbering_layout.setSpacing(12)
        numbering_layout.setContentsMargins(20, 25, 20, 20)
        numbering_layout.setColumnStretch(0, 0)
        numbering_layout.setColumnStretch(1, 1)
        
        # Préfixe
        label_prefix = QLabel("Format facture :")
        label_prefix.setMinimumWidth(120)
        label_prefix.setStyleSheet("font-weight: 500; color: #2c3e50;")
        
        prefix_widget = QWidget()
        prefix_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        prefix_layout = QHBoxLayout(prefix_widget)
        prefix_layout.setContentsMargins(0, 0, 0, 0)
        prefix_layout.setSpacing(8)
        
        self.invoice_prefix_input = QLineEdit()
        self.invoice_prefix_input.setPlaceholderText("FAC")
        self.invoice_prefix_input.setMaxLength(5)
        self.invoice_prefix_input.setMinimumWidth(80)
        self.invoice_prefix_input.setMaximumWidth(100)
        self.invoice_prefix_input.setMinimumHeight(32)
        self.invoice_prefix_input.setStyleSheet(self._get_input_style())
        
        self.invoice_start_spin = QSpinBox()
        self.invoice_start_spin.setRange(1, 99999)
        self.invoice_start_spin.setValue(1)
        self.invoice_start_spin.setPrefix("N° ")
        self.invoice_start_spin.setMinimumWidth(100)
        self.invoice_start_spin.setMaximumWidth(150)
        self.invoice_start_spin.setMinimumHeight(32)
        self.invoice_start_spin.setStyleSheet(self._get_spinbox_style())
        
        prefix_layout.addWidget(self.invoice_prefix_input)
        prefix_layout.addWidget(QLabel("-2024-"))
        prefix_layout.addWidget(self.invoice_start_spin)
        prefix_layout.addStretch()
        
        numbering_layout.addWidget(label_prefix, 0, 0)
        numbering_layout.addWidget(prefix_widget, 0, 1)
        
        # Délai de paiement
        label_payment = QLabel("Délai paiement :")
        label_payment.setMinimumWidth(120)
        label_payment.setStyleSheet("font-weight: 500; color: #2c3e50;")
        
        self.payment_terms_spin = QSpinBox()
        self.payment_terms_spin.setRange(0, 90)
        self.payment_terms_spin.setSuffix(" jours")
        self.payment_terms_spin.setValue(30)
        self.payment_terms_spin.setSpecialValueText("À réception")
        self.payment_terms_spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.payment_terms_spin.setMinimumHeight(32)
        self.payment_terms_spin.setStyleSheet(self._get_spinbox_style())
        
        numbering_layout.addWidget(label_payment, 1, 0)
        numbering_layout.addWidget(self.payment_terms_spin, 1, 1)
        
        main_layout.addWidget(numbering_group)
        
        # Groupe Pied de page
        footer_group = QGroupBox("Pied de page")
        footer_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        footer_group.setStyleSheet(self._get_group_box_style())
        
        footer_inner_layout = QVBoxLayout(footer_group)
        footer_inner_layout.setContentsMargins(20, 25, 20, 20)
        footer_inner_layout.setSpacing(10)
        
        self.invoice_footer_input = QTextEdit()
        self.invoice_footer_input.setPlaceholderText(
            "Merci pour votre confiance.\n"
            "Conditions de paiement : 30 jours."
        )
        self.invoice_footer_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.invoice_footer_input.setMinimumHeight(80)
        self.invoice_footer_input.setMaximumHeight(120)
        self.invoice_footer_input.setStyleSheet("""
            QTextEdit {
                border: 2px solid #d0d0d0;
                border-radius: 6px;
                padding: 10px;
                font-size: 12px;
                background-color: white;
            }
            QTextEdit:focus {
                border-color: #3498db;
            }
        """)
        
        # Boutons templates
        template_widget = QWidget()
        template_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        template_layout = QHBoxLayout(template_widget)
        template_layout.setContentsMargins(0, 0, 0, 0)
        template_layout.setSpacing(10)
        
        templates = ["Standard", "Minimaliste", "Professionnel"]
        for template in templates:
            btn = QPushButton(template)
            btn.setMinimumHeight(30)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(lambda checked, t=template: self.load_footer_template(t))
            btn.setStyleSheet(self._get_button_style("#95a5a6", "#7f8c8d"))
            template_layout.addWidget(btn)
        
        footer_inner_layout.addWidget(self.invoice_footer_input)
        footer_inner_layout.addWidget(template_widget)
        
        main_layout.addWidget(footer_group)
        
        # Espacement flexible
        spacer = QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)
        main_layout.addSpacerItem(spacer)
        
        return tab
    
    def _get_group_box_style(self):
        """Retourne le style des group boxes"""
        return """
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                border: 2px solid #d0d0d0;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px;
                color: #2c3e50;
            }
        """
    
    def _get_input_style(self):
        """Retourne le style des champs de saisie"""
        return """
            QLineEdit {
                border: 2px solid #d0d0d0;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #3498db;
            }
            QLineEdit:hover {
                border-color: #a0a0a0;
            }
        """
    
    def _get_combo_style(self):
        """Retourne le style des combo boxes"""
        return """
            QComboBox {
                border: 2px solid #d0d0d0;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                background-color: white;
            }
            QComboBox:focus {
                border-color: #3498db;
            }
            QComboBox:hover {
                border-color: #a0a0a0;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #666;
                margin-right: 5px;
            }
        """
    
    def _get_spinbox_style(self):
        """Retourne le style des spin boxes"""
        return """
            QSpinBox, QDoubleSpinBox {
                border: 2px solid #d0d0d0;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                background-color: white;
            }
            QSpinBox:focus, QDoubleSpinBox:focus {
                border-color: #3498db;
            }
            QSpinBox:hover, QDoubleSpinBox:hover {
                border-color: #a0a0a0;
            }
            QSpinBox::up-button, QDoubleSpinBox::up-button,
            QSpinBox::down-button, QDoubleSpinBox::down-button {
                border: none;
                background: transparent;
                width: 20px;
            }
        """
    
    def _get_button_style(self, bg_color, hover_color):
        """Retourne le style des boutons"""
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:disabled {{
                background-color: #bdc3c7;
                color: #7f8c8d;
            }}
        """
    
    def _connect_signals(self):
        """Connecte les signaux pour détecter les changements"""
        # Entreprise
        self.company_name_input.textChanged.connect(self._on_settings_changed)
        self.company_address_input.textChanged.connect(self._on_settings_changed)
        self.company_po_box_input.textChanged.connect(self._on_settings_changed)
        self.company_phone_input.textChanged.connect(self._on_settings_changed)
        self.company_email_input.textChanged.connect(self._on_settings_changed)
        self.company_ifu_input.textChanged.connect(self._on_settings_changed)
        self.company_rccm_input.textChanged.connect(self._on_settings_changed)
        
        # Général
        self.language_combo.currentIndexChanged.connect(self._on_settings_changed)
        self.currency_combo.currentIndexChanged.connect(self._on_settings_changed)
        self.date_format_combo.currentIndexChanged.connect(self._on_settings_changed)
        self.animation_check.stateChanged.connect(self._on_settings_changed)
        
        # Facturation
        self.tax_rate_spin.valueChanged.connect(self._on_settings_changed)
        self.discount_spin.valueChanged.connect(self._on_settings_changed)
        self.invoice_prefix_input.textChanged.connect(self._on_settings_changed)
        self.invoice_start_spin.valueChanged.connect(self._on_settings_changed)
        self.payment_terms_spin.valueChanged.connect(self._on_settings_changed)
        self.invoice_footer_input.textChanged.connect(self._on_settings_changed)
    
    def _on_settings_changed(self):
        """Active/désactive les boutons en fonction des changements"""
        current_data = self._collect_form_data()
        has_changes = current_data != self.original_settings
        
        self.save_btn.setEnabled(has_changes)
        self.cancel_btn.setEnabled(has_changes)
        
        if has_changes:
            self.status_label.setText("⚠️ Modifications non sauvegardées")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #e67e22;
                    font-weight: bold;
                    padding: 5px 10px;
                    background-color: #fef9e7;
                    border-radius: 4px;
                }
            """)
        else:
            self.status_label.setText("✅ Aucune modification")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #27ae60;
                    font-weight: bold;
                    padding: 5px 10px;
                    background-color: #e8f5e9;
                    border-radius: 4px;
                }
            """)
    
    def _collect_form_data(self):
        """Collecte les données du formulaire"""
        return {
            "company_name": self.company_name_input.text().strip(),
            "company_address": self.company_address_input.text().strip(),
            "company_po_box": self.company_po_box_input.text().strip(),
            "company_phone": self.company_phone_input.text().strip(),
            "company_email": self.company_email_input.text().strip(),
            "company_ifu": self.company_ifu_input.text().strip(),
            "company_rccm": self.company_rccm_input.text().strip(),
            "company_logo": self.current_logo_path,
            "language": ["fr", "en"][self.language_combo.currentIndex()],
            "currency": self._get_currency_code(),
            "date_format": ["dd/MM/yyyy", "MM/dd/yyyy", "yyyy-MM-dd"][self.date_format_combo.currentIndex()],
            "animations": self.animation_check.isChecked(),
            "tax_rate": self.tax_rate_spin.value(),
            "discount": self.discount_spin.value(),
            "invoice_prefix": self.invoice_prefix_input.text().strip(),
            "invoice_start": self.invoice_start_spin.value(),
            "payment_terms": self.payment_terms_spin.value(),
            "invoice_footer": self.invoice_footer_input.toPlainText().strip()
        }
    
    def _get_currency_code(self):
        """Retourne le code devise basé sur la sélection"""
        text = self.currency_combo.currentText()
        if "USD" in text:
            return "USD"
        elif "XAF" in text:
            return "XAF"
        elif "XOF" in text:
            return "XOF"
        return "USD"
    
    def load_footer_template(self, template_name):
        """Charge un template de pied de page"""
        templates = {
            "Standard": "Merci pour votre confiance.\nVeuillez régler par virement bancaire.",
            "Minimaliste": "Merci pour votre confiance.",
            "Professionnel": "Société XYZ\nSIRET: 123 456 789\nRCS: Paris B\nIBAN: FR76 XXXX XXXX XXXX"
        }
        
        if template_name in templates:
            self.invoice_footer_input.setText(templates[template_name])
    
    def select_logo(self):
        """Sélectionne un logo"""
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        file_dialog.setNameFilter("Images (*.png *.jpg *.jpeg *.bmp)")
        file_dialog.setWindowTitle("Sélectionner un logo")
        
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                logo_path = selected_files[0]
                self.load_logo_preview(logo_path)
                self.current_logo_path = logo_path
                self.clear_logo_btn.setEnabled(True)
                self._on_settings_changed()
    
    def load_logo_preview(self, logo_path):
        """Charge la prévisualisation du logo"""
        try:
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    110, 110,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.logo_preview.setPixmap(scaled_pixmap)
                self.logo_preview.setText("")
            else:
                raise Exception("Image invalide")
        except Exception as e:
            print(f"Erreur logo: {e}")
            QMessageBox.warning(self, "Erreur", "Impossible de charger l'image.\nVérifiez que le fichier est une image valide.")
    
    def clear_logo(self):
        """Efface le logo"""
        self.logo_preview.clear()
        self.logo_preview.setText("📷 Aucun logo")
        self.current_logo_path = ""
        self.clear_logo_btn.setEnabled(False)
        self._on_settings_changed()
    
    def load_current_settings(self):
        """Charge les paramètres actuels"""
        settings = self.settings_manager.get_all_settings()
        
        # Sauvegarde des originaux
        self.original_settings = settings.copy()
        
        # Entreprise
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
            self.clear_logo()
        
        # Général
        language = settings.get("language", "fr")
        self.language_combo.setCurrentIndex(0 if language == "fr" else 1)
        
        # Devise
        currency = settings.get("currency", "USD")
        if currency == "USD":
            self.currency_combo.setCurrentIndex(0)
        elif currency == "XAF":
            self.currency_combo.setCurrentIndex(1)
        elif currency == "XOF":
            self.currency_combo.setCurrentIndex(2)
        
        # Format date
        date_format = settings.get("date_format", "dd/MM/yyyy")
        formats = ["dd/MM/yyyy", "MM/dd/yyyy", "yyyy-MM-dd"]
        try:
            index = formats.index(date_format)
            self.date_format_combo.setCurrentIndex(index)
        except:
            self.date_format_combo.setCurrentIndex(0)
        
        self.animation_check.setChecked(settings.get("animations", True))
        
        # Facturation
        self.tax_rate_spin.setValue(settings.get("tax_rate", 20.0))
        self.discount_spin.setValue(settings.get("discount", 0))
        self.invoice_prefix_input.setText(settings.get("invoice_prefix", "FAC"))
        self.invoice_start_spin.setValue(settings.get("invoice_start", 1))
        self.payment_terms_spin.setValue(settings.get("payment_terms", 30))
        self.invoice_footer_input.setText(settings.get("invoice_footer", ""))
        
        # Réinitialiser état
        self.save_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.status_label.setText("✅ Aucune modification")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #27ae60;
                font-weight: bold;
                padding: 5px 10px;
                background-color: #e8f5e9;
                border-radius: 4px;
            }
        """)
    
    def save_all_settings(self):
        """Sauvegarde tous les paramètres"""
        # Validation
        if not self.company_name_input.text().strip():
            QMessageBox.warning(self, "Champ requis", "Le nom de l'entreprise est obligatoire.")
            self.company_name_input.setFocus()
            return
        
        # Préparer données
        settings_to_save = self._collect_form_data()
        
        # Sauvegarder
        if self.settings_manager.save_settings(settings_to_save):
            QMessageBox.information(self, "✅ Succès", "Paramètres enregistrés avec succès!")
            
            # Émettre signal
            self.settings_changed.emit(settings_to_save)
            
            # Mettre à jour originaux
            self.original_settings = settings_to_save.copy()
            
            # Recharger
            self.load_current_settings()
        else:
            QMessageBox.critical(self, "❌ Erreur", "Erreur lors de l'enregistrement des paramètres.")
# ui/views/settings_view.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QGroupBox, QMessageBox, QFileDialog,
    QTextEdit, QDoubleSpinBox, QComboBox, QTabWidget, QFrame,
    QSpinBox, QCheckBox, QGridLayout, QSizePolicy, QScrollArea,
    QSpacerItem
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QFont, QIcon, QColor
import os
from utils.settings_manager import SettingsManager


class SettingsView(QWidget):
    """Vue des paramètres moderne et épurée"""
    
    settings_changed = Signal(dict)
    
    def __init__(self, user_data, settings_manager):
        super().__init__()
        self.user_data = user_data
        self.settings_manager = settings_manager
        self.current_logo_path = ""
        self.original_settings = {}
        
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setObjectName("settingsView")
        
        self._build_ui()
        self.load_current_settings()
        self._connect_signals()
        
    def _build_ui(self):
        """Construit l'interface utilisateur"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Contenu principal avec scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #f8fafc;
            }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94a3b8;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """)
        
        content = QWidget()
        content.setStyleSheet("background-color: #f8fafc;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(30, 15, 30, 30)
        content_layout.setSpacing(20)
        
        # Onglets
        self.tab_widget = self._create_tabs()
        content_layout.addWidget(self.tab_widget)
        
        # Pied de page
        footer = self._create_footer()
        content_layout.addWidget(footer)
        
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
    
    def _create_tabs(self):
        """Crée des onglets avec un style moderne"""
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                background-color: white;
                border: 1px solid #e8ecf1;
                border-radius: 12px;
                margin-top: 2px;
            }
            QTabBar::tab {
                background: transparent;
                color: #64748b;
                padding: 10px 22px;
                margin-right: 4px;
                border: none;
                border-bottom: 3px solid transparent;
                font-size: 13px;
                font-weight: 500;
                min-width: 80px;
            }
            QTabBar::tab:selected {
                color: #1e293b;
                border-bottom: 3px solid #3b82f6;
                background: rgba(59, 130, 246, 0.05);
                border-radius: 8px 8px 0 0;
            }
            QTabBar::tab:hover:!selected {
                color: #1e293b;
                background: rgba(59, 130, 246, 0.03);
                border-radius: 8px 8px 0 0;
            }
        """)
        
        # Création des onglets
        tabs.addTab(self._create_company_tab(), "🏢 Entreprise")
        tabs.addTab(self._create_general_tab(), "⚙️ Général")
        tabs.addTab(self._create_billing_tab(), "📄 Facturation")
        tabs.addTab(self._create_security_tab(), "🔒 Sécurité")
        
        return tabs
    
    def _create_card(self, title, content_widget):
        """Crée une carte avec ombre et bordure arrondie"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #e8ecf1;
            }
        """)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # En-tête de la carte
        if title:
            header = QWidget()
            header.setStyleSheet("""
                QWidget {
                    background-color: #fafbfc;
                    border-radius: 12px 12px 0 0;
                    border-bottom: 1px solid #e8ecf1;
                }
            """)
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(20, 12, 20, 12)
            
            title_label = QLabel(title)
            title_label.setStyleSheet("""
                font-size: 14px;
                font-weight: 600;
                color: #0f172a;
            """)
            header_layout.addWidget(title_label)
            
            layout.addWidget(header)
        
        # Contenu
        content_widget.setStyleSheet("background-color: white; border-radius: 0 0 12px 12px;")
        layout.addWidget(content_widget)
        
        return card
    
    def _create_company_tab(self):
        """Crée l'onglet Entreprise"""
        tab = QWidget()
        tab.setStyleSheet("background-color: #f8fafc;")
        tab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        main_layout = QVBoxLayout(tab)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(20)
        
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(20)
        container_layout.setContentsMargins(0, 0, 0, 0)
        
        # Carte 1: Informations de l'entreprise
        info_content = QWidget()
        info_layout = QGridLayout(info_content)
        info_layout.setSpacing(12)
        info_layout.setContentsMargins(25, 20, 25, 20)
        info_layout.setColumnStretch(0, 0)
        info_layout.setColumnStretch(1, 1)
        
        # Création des champs
        self.company_name_input = QLineEdit()
        self.company_address_input = QLineEdit()
        self.company_po_box_input = QLineEdit()
        self.company_phone_input = QLineEdit()
        self.company_email_input = QLineEdit()
        
        fields = [
            ("🏷️ Nom", self.company_name_input, 0),
            ("📍 Adresse", self.company_address_input, 1),
            ("📬 BP", self.company_po_box_input, 2),
            ("📞 Téléphone", self.company_phone_input, 3),
            ("✉️ Email", self.company_email_input, 4),
        ]
        
        for label_text, field, row in fields:
            label = QLabel(label_text)
            label.setStyleSheet("color: #475569; font-weight: 500; font-size: 13px;")
            label.setMinimumWidth(100)
            
            field.setPlaceholderText(f"Saisir {label_text.lower()}")
            field.setMinimumHeight(36)
            field.setStyleSheet(self._get_input_style())
            field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            info_layout.addWidget(label, row, 0)
            info_layout.addWidget(field, row, 1)
        
        info_card = self._create_card("Informations de l'entreprise", info_content)
        container_layout.addWidget(info_card)
        
        # Carte 2: Informations légales
        legal_content = QWidget()
        legal_layout = QGridLayout(legal_content)
        legal_layout.setSpacing(12)
        legal_layout.setContentsMargins(25, 20, 25, 20)
        legal_layout.setColumnStretch(0, 0)
        legal_layout.setColumnStretch(1, 1)
        
        # Création des champs légaux
        self.company_ifu_input = QLineEdit()
        self.company_rccm_input = QLineEdit()
        
        legal_fields = [
            ("📋 IFU", self.company_ifu_input, 0),
            ("📑 RCCM", self.company_rccm_input, 1),
        ]
        
        for label_text, field, row in legal_fields:
            label = QLabel(label_text)
            label.setStyleSheet("color: #475569; font-weight: 500; font-size: 13px;")
            label.setMinimumWidth(100)
            
            field.setPlaceholderText(f"Saisir {label_text.lower()}")
            field.setMinimumHeight(36)
            field.setStyleSheet(self._get_input_style())
            field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            legal_layout.addWidget(label, row, 0)
            legal_layout.addWidget(field, row, 1)
        
        legal_card = self._create_card("Informations légales", legal_content)
        container_layout.addWidget(legal_card)
        
        # Carte 3: Logo
        logo_content = QWidget()
        logo_layout = QHBoxLayout(logo_content)
        logo_layout.setSpacing(20)
        logo_layout.setContentsMargins(25, 20, 25, 20)
        
        # Prévisualisation du logo
        preview_container = QWidget()
        preview_container.setFixedSize(100, 100)
        preview_container.setStyleSheet("""
            QWidget {
                background-color: #f8fafc;
                border: 2px dashed #cbd5e1;
                border-radius: 12px;
            }
        """)
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setAlignment(Qt.AlignCenter)
        
        self.logo_preview = QLabel("📷")
        self.logo_preview.setAlignment(Qt.AlignCenter)
        self.logo_preview.setStyleSheet("font-size: 36px; color: #94a3b8;")
        self.logo_preview.setFixedSize(90, 90)
        
        preview_layout.addWidget(self.logo_preview)
        
        # Boutons
        buttons_widget = QWidget()
        buttons_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        buttons_layout = QVBoxLayout(buttons_widget)
        buttons_layout.setSpacing(8)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        
        self.select_logo_btn = QPushButton("📁 Choisir un logo")
        self.select_logo_btn.setMinimumHeight(36)
        self.select_logo_btn.clicked.connect(self.select_logo)
        self.select_logo_btn.setStyleSheet(self._get_primary_button_style())
        
        self.clear_logo_btn = QPushButton("🗑 Supprimer")
        self.clear_logo_btn.setMinimumHeight(36)
        self.clear_logo_btn.setEnabled(False)
        self.clear_logo_btn.clicked.connect(self.clear_logo)
        self.clear_logo_btn.setStyleSheet(self._get_danger_button_style())
        
        buttons_layout.addWidget(self.select_logo_btn)
        buttons_layout.addWidget(self.clear_logo_btn)
        
        logo_layout.addWidget(preview_container)
        logo_layout.addWidget(buttons_widget)
        logo_layout.addStretch()
        
        logo_card = self._create_card("Logo de l'entreprise", logo_content)
        container_layout.addWidget(logo_card)
        
        container_layout.addStretch()
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background-color: transparent;")
        scroll.setWidget(container)
        
        main_layout.addWidget(scroll)
        
        return tab
    
    def _create_general_tab(self):
        """Crée l'onglet Général"""
        tab = QWidget()
        tab.setStyleSheet("background-color: #f8fafc;")
        tab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        main_layout = QVBoxLayout(tab)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(20)
        
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(20)
        container_layout.setContentsMargins(0, 0, 0, 0)
        
        # Carte 1: Paramètres généraux
        general_content = QWidget()
        general_layout = QGridLayout(general_content)
        general_layout.setSpacing(12)
        general_layout.setContentsMargins(25, 20, 25, 20)
        general_layout.setColumnStretch(0, 0)
        general_layout.setColumnStretch(1, 1)
        
        # Création des champs
        self.language_combo = QComboBox()
        self.currency_combo = QComboBox()
        self.date_format_combo = QComboBox()
        
        # Langue
        label_lang = QLabel("🌐 Langue")
        label_lang.setStyleSheet("color: #475569; font-weight: 500; font-size: 13px;")
        label_lang.setMinimumWidth(120)
        
        self.language_combo.addItems(["🇫🇷 Français", "🇬🇧 English"])
        self.language_combo.setMinimumHeight(36)
        self.language_combo.setStyleSheet(self._get_combo_style())
        self.language_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        general_layout.addWidget(label_lang, 0, 0)
        general_layout.addWidget(self.language_combo, 0, 1)
        
        # Devise
        label_curr = QLabel("💰 Devise")
        label_curr.setStyleSheet("color: #475569; font-weight: 500; font-size: 13px;")
        label_curr.setMinimumWidth(120)
        
        self.currency_combo.addItems(["💵 USD", "💰 XAF", "💰 XOF"])
        self.currency_combo.setMinimumHeight(36)
        self.currency_combo.setStyleSheet(self._get_combo_style())
        self.currency_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        general_layout.addWidget(label_curr, 1, 0)
        general_layout.addWidget(self.currency_combo, 1, 1)
        
        # Format date
        label_date = QLabel("📅 Format date")
        label_date.setStyleSheet("color: #475569; font-weight: 500; font-size: 13px;")
        label_date.setMinimumWidth(120)
        
        self.date_format_combo.addItems(["jj/mm/aaaa", "mm/jj/aaaa", "aaaa-mm-jj"])
        self.date_format_combo.setMinimumHeight(36)
        self.date_format_combo.setStyleSheet(self._get_combo_style())
        self.date_format_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        general_layout.addWidget(label_date, 2, 0)
        general_layout.addWidget(self.date_format_combo, 2, 1)
        
        general_card = self._create_card("Préférences générales", general_content)
        container_layout.addWidget(general_card)
        
        # Carte 2: Affichage
        display_content = QWidget()
        display_layout = QVBoxLayout(display_content)
        display_layout.setContentsMargins(25, 16, 25, 16)
        
        self.animation_check = QCheckBox("🎨 Activer les animations")
        self.animation_check.setChecked(True)
        self.animation_check.setStyleSheet("""
            QCheckBox {
                color: #334155;
                font-size: 13px;
                font-weight: 500;
                spacing: 12px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 6px;
                border: 2px solid #cbd5e1;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                background-color: #3b82f6;
                border-color: #3b82f6;
            }
        """)
        
        display_layout.addWidget(self.animation_check)
        
        display_card = self._create_card("Affichage", display_content)
        container_layout.addWidget(display_card)
        
        container_layout.addStretch()
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background-color: transparent;")
        scroll.setWidget(container)
        
        main_layout.addWidget(scroll)
        
        return tab
    
    def _create_billing_tab(self):
        """Crée l'onglet Facturation"""
        tab = QWidget()
        tab.setStyleSheet("background-color: #f8fafc;")
        tab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        main_layout = QVBoxLayout(tab)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(20)
        
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(20)
        container_layout.setContentsMargins(0, 0, 0, 0)
        
        # Carte 1: Paramètres fiscaux
        tax_content = QWidget()
        tax_layout = QGridLayout(tax_content)
        tax_layout.setSpacing(12)
        tax_layout.setContentsMargins(25, 20, 25, 20)
        tax_layout.setColumnStretch(0, 0)
        tax_layout.setColumnStretch(1, 1)
        
        # Création des champs
        self.tax_rate_spin = QDoubleSpinBox()
        self.discount_spin = QDoubleSpinBox()
        
        # TVA
        label_tax = QLabel("💹 Taux TVA")
        label_tax.setStyleSheet("color: #475569; font-weight: 500; font-size: 13px;")
        label_tax.setMinimumWidth(120)
        
        self.tax_rate_spin.setRange(0, 100)
        self.tax_rate_spin.setSuffix(" %")
        self.tax_rate_spin.setDecimals(2)
        self.tax_rate_spin.setValue(20.0)
        self.tax_rate_spin.setMinimumHeight(36)
        self.tax_rate_spin.setStyleSheet(self._get_spinbox_style())
        self.tax_rate_spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        tax_layout.addWidget(label_tax, 0, 0)
        tax_layout.addWidget(self.tax_rate_spin, 0, 1)
        
        # Remise
        label_discount = QLabel("🏷️ Remise par défaut")
        label_discount.setStyleSheet("color: #475569; font-weight: 500; font-size: 13px;")
        label_discount.setMinimumWidth(120)
        
        self.discount_spin.setRange(0, 100)
        self.discount_spin.setSuffix(" %")
        self.discount_spin.setDecimals(2)
        self.discount_spin.setMinimumHeight(36)
        self.discount_spin.setStyleSheet(self._get_spinbox_style())
        self.discount_spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        tax_layout.addWidget(label_discount, 1, 0)
        tax_layout.addWidget(self.discount_spin, 1, 1)
        
        tax_card = self._create_card("Paramètres fiscaux", tax_content)
        container_layout.addWidget(tax_card)
        
        # Carte 2: Numérotation
        numbering_content = QWidget()
        numbering_layout = QGridLayout(numbering_content)
        numbering_layout.setSpacing(12)
        numbering_layout.setContentsMargins(25, 20, 25, 20)
        numbering_layout.setColumnStretch(0, 0)
        numbering_layout.setColumnStretch(1, 1)
        
        # Création des champs
        self.invoice_prefix_input = QLineEdit()
        self.invoice_start_spin = QSpinBox()
        self.payment_terms_spin = QSpinBox()
        
        # Préfixe
        label_prefix = QLabel("🔢 Préfixe facture")
        label_prefix.setStyleSheet("color: #475569; font-weight: 500; font-size: 13px;")
        label_prefix.setMinimumWidth(120)
        
        prefix_widget = QWidget()
        prefix_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        prefix_layout = QHBoxLayout(prefix_widget)
        prefix_layout.setContentsMargins(0, 0, 0, 0)
        prefix_layout.setSpacing(8)
        
        self.invoice_prefix_input.setPlaceholderText("FAC")
        self.invoice_prefix_input.setMaxLength(5)
        self.invoice_prefix_input.setMinimumWidth(80)
        self.invoice_prefix_input.setMaximumWidth(100)
        self.invoice_prefix_input.setMinimumHeight(36)
        self.invoice_prefix_input.setStyleSheet(self._get_input_style())
        
        label_sep = QLabel("-2024-")
        label_sep.setStyleSheet("color: #94a3b8; font-weight: 500; font-size: 13px;")
        
        self.invoice_start_spin.setRange(1, 99999)
        self.invoice_start_spin.setPrefix("N° ")
        self.invoice_start_spin.setMinimumWidth(100)
        self.invoice_start_spin.setMaximumWidth(150)
        self.invoice_start_spin.setMinimumHeight(36)
        self.invoice_start_spin.setStyleSheet(self._get_spinbox_style())
        
        prefix_layout.addWidget(self.invoice_prefix_input)
        prefix_layout.addWidget(label_sep)
        prefix_layout.addWidget(self.invoice_start_spin)
        prefix_layout.addStretch()
        
        numbering_layout.addWidget(label_prefix, 0, 0)
        numbering_layout.addWidget(prefix_widget, 0, 1)
        
        # Délai paiement
        label_payment = QLabel("📅 Délai paiement")
        label_payment.setStyleSheet("color: #475569; font-weight: 500; font-size: 13px;")
        label_payment.setMinimumWidth(120)
        
        self.payment_terms_spin.setRange(0, 90)
        self.payment_terms_spin.setSuffix(" jours")
        self.payment_terms_spin.setValue(30)
        self.payment_terms_spin.setSpecialValueText("À réception")
        self.payment_terms_spin.setMinimumHeight(36)
        self.payment_terms_spin.setStyleSheet(self._get_spinbox_style())
        self.payment_terms_spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        numbering_layout.addWidget(label_payment, 1, 0)
        numbering_layout.addWidget(self.payment_terms_spin, 1, 1)
        
        numbering_card = self._create_card("Numérotation", numbering_content)
        container_layout.addWidget(numbering_card)
        
        # Carte 3: Pied de page
        footer_content = QWidget()
        footer_content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        footer_content_layout = QVBoxLayout(footer_content)
        footer_content_layout.setSpacing(10)
        footer_content_layout.setContentsMargins(25, 16, 25, 16)
        
        self.invoice_footer_input = QTextEdit()
        self.invoice_footer_input.setPlaceholderText(
            "Merci pour votre confiance.\n"
            "Conditions de paiement : 30 jours nets."
        )
        self.invoice_footer_input.setMinimumHeight(70)
        self.invoice_footer_input.setMaximumHeight(110)
        self.invoice_footer_input.setStyleSheet("""
            QTextEdit {
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                padding: 10px 12px;
                font-size: 13px;
                background-color: white;
                color: #1e293b;
            }
            QTextEdit:focus {
                border-color: #3b82f6;
            }
        """)
        self.invoice_footer_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Boutons templates
        template_widget = QWidget()
        template_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        template_layout = QHBoxLayout(template_widget)
        template_layout.setContentsMargins(0, 0, 0, 0)
        template_layout.setSpacing(8)
        
        template_widget.setMaximumHeight(36)
        
        templates = ["📝 Standard", "✨ Minimaliste", "💼 Professionnel"]
        for template in templates:
            btn = QPushButton(template)
            btn.setMinimumHeight(32)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(lambda checked, t=template: self.load_footer_template(t))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #f1f5f9;
                    color: #475569;
                    border: 1px solid #e2e8f0;
                    border-radius: 6px;
                    padding: 4px 12px;
                    font-size: 12px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #e2e8f0;
                    border-color: #94a3b8;
                }
            """)
            template_layout.addWidget(btn)
        
        footer_content_layout.addWidget(self.invoice_footer_input)
        footer_content_layout.addWidget(template_widget)
        
        footer_card = self._create_card("Pied de page", footer_content)
        container_layout.addWidget(footer_card)
        
        container_layout.addStretch()
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background-color: transparent;")
        scroll.setWidget(container)
        
        main_layout.addWidget(scroll)
        
        return tab
    
    def _create_footer(self):
        """Crée un pied de page moderne"""
        footer = QFrame()
        footer.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #e8ecf1;
                padding: 12px 20px;
            }
        """)
        footer.setMaximumHeight(70)
        
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        # Statut
        self.status_label = QLabel("✅ Aucune modification")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #22c55e;
                font-weight: 500;
                padding: 4px 14px;
                background-color: #f0fdf4;
                border-radius: 16px;
                font-size: 12px;
            }
        """)
        self.status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        layout.addWidget(self.status_label)
        layout.addStretch()
        
        # Bouton Annuler
        self.cancel_btn = QPushButton("✖ Annuler")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setMinimumWidth(90)
        self.cancel_btn.setMinimumHeight(36)
        self.cancel_btn.clicked.connect(self.load_current_settings)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #475569;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 6px 18px;
                font-weight: 500;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
            }
            QPushButton:disabled {
                background-color: #f1f5f9;
                color: #94a3b8;
            }
        """)
        
        # Bouton Enregistrer
        self.save_btn = QPushButton("💾 Enregistrer")
        self.save_btn.setEnabled(False)
        self.save_btn.setMinimumWidth(110)
        self.save_btn.setMinimumHeight(36)
        self.save_btn.clicked.connect(self.save_all_settings)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 6px 22px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:disabled {
                background-color: #cbd5e1;
                color: #94a3b8;
            }
        """)
        
        layout.addWidget(self.cancel_btn)
        layout.addWidget(self.save_btn)
        
        return footer
    
    def _get_input_style(self):
        """Retourne le style des champs de saisie"""
        return """
            QLineEdit {
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 13px;
                background-color: white;
                color: #1e293b;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
                background-color: #f8fafc;
            }
            QLineEdit:hover {
                border-color: #94a3b8;
            }
            QLineEdit::placeholder {
                color: #94a3b8;
            }
        """
    
    def _get_combo_style(self):
        """Retourne le style des combo boxes"""
        return """
            QComboBox {
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 13px;
                background-color: white;
                color: #1e293b;
            }
            QComboBox:focus {
                border-color: #3b82f6;
                background-color: #f8fafc;
            }
            QComboBox:hover {
                border-color: #94a3b8;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #64748b;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 4px;
                background-color: white;
                selection-background-color: #e8ecf1;
                selection-color: #1e293b;
            }
        """
    
    def _get_spinbox_style(self):
        """Retourne le style des spin boxes"""
        return """
            QSpinBox, QDoubleSpinBox {
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 13px;
                background-color: white;
                color: #1e293b;
            }
            QSpinBox:focus, QDoubleSpinBox:focus {
                border-color: #3b82f6;
                background-color: #f8fafc;
            }
            QSpinBox:hover, QDoubleSpinBox:hover {
                border-color: #94a3b8;
            }
            QSpinBox::up-button, QDoubleSpinBox::up-button,
            QSpinBox::down-button, QDoubleSpinBox::down-button {
                border: none;
                background: transparent;
                width: 25px;
            }
            QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-bottom: 5px solid #64748b;
            }
            QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #64748b;
            }
        """
    
    def _create_security_tab(self):
        """Crée l'onglet Sécurité"""
        tab = QWidget()
        tab.setStyleSheet("background-color: #f8fafc;")
        
        main_layout = QVBoxLayout(tab)
        main_layout.setContentsMargins(30, 20, 30, 20)
        main_layout.setSpacing(20)
        
        # Carte 1: Modification du mot de passe
        password_card = self._create_card("Modifier le mot de passe", QWidget())
        password_content = password_card.findChild(QWidget)
        password_layout = QVBoxLayout(password_content)
        password_layout.setContentsMargins(25, 20, 25, 20)
        password_layout.setSpacing(12)
        
        # Mot de passe actuel
        current_pwd_layout = QHBoxLayout()
        current_pwd_layout.addWidget(QLabel("🔑 Mot de passe actuel:"))
        self.current_password_input = QLineEdit()
        self.current_password_input.setEchoMode(QLineEdit.Password)
        self.current_password_input.setMinimumHeight(36)
        self.current_password_input.setStyleSheet(self._get_input_style())
        current_pwd_layout.addWidget(self.current_password_input)
        password_layout.addLayout(current_pwd_layout)
        
        # Nouveau mot de passe
        new_pwd_layout = QHBoxLayout()
        new_pwd_layout.addWidget(QLabel("🆕 Nouveau mot de passe:"))
        self.new_password_input = QLineEdit()
        self.new_password_input.setEchoMode(QLineEdit.Password)
        self.new_password_input.setMinimumHeight(36)
        self.new_password_input.setStyleSheet(self._get_input_style())
        new_pwd_layout.addWidget(self.new_password_input)
        password_layout.addLayout(new_pwd_layout)
        
        # Confirmation
        confirm_pwd_layout = QHBoxLayout()
        confirm_pwd_layout.addWidget(QLabel("✅ Confirmer le mot de passe:"))
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        self.confirm_password_input.setMinimumHeight(36)
        self.confirm_password_input.setStyleSheet(self._get_input_style())
        confirm_pwd_layout.addWidget(self.confirm_password_input)
        password_layout.addLayout(confirm_pwd_layout)
        
        # Bouton de modification
        change_pwd_btn = QPushButton("🔒 Modifier le mot de passe")
        change_pwd_btn.setMinimumHeight(40)
        change_pwd_btn.clicked.connect(self.change_password)
        change_pwd_btn.setStyleSheet(self._get_primary_button_style())
        password_layout.addWidget(change_pwd_btn)
        
        main_layout.addWidget(password_card)
        
        # Carte 2: Informations de sécurité
        info_card = self._create_card("Informations de sécurité", QWidget())
        info_content = info_card.findChild(QWidget)
        info_layout = QVBoxLayout(info_content)
        info_layout.setContentsMargins(25, 20, 25, 20)
        
        username_label = QLabel(f"👤 Utilisateur: {self.user_data.get('username', 'N/A')}")
        role_label = QLabel(f"🔑 Rôle: {self.user_data.get('role', 'N/A')}")
        
        info_layout.addWidget(username_label)
        info_layout.addWidget(role_label)
        
        main_layout.addWidget(info_card)
        main_layout.addStretch()
        
        return tab
    
    def change_password(self):
        """Modifie le mot de passe de l'utilisateur"""
        current = self.current_password_input.text()
        new = self.new_password_input.text()
        confirm = self.confirm_password_input.text()
        
        if not current or not new or not confirm:
            QMessageBox.warning(self, "Erreur", "Veuillez remplir tous les champs.")
            return
        
        if new != confirm:
            QMessageBox.warning(self, "Erreur", "Les mots de passe ne correspondent pas.")
            return
        
        if len(new) < 6:
            QMessageBox.warning(self, "Erreur", "Le mot de passe doit contenir au moins 6 caractères.")
            return
        
        # Vérifier le mot de passe actuel
        from controllers.auth_controller import AuthController
        auth = AuthController()
        if not auth.verify_password(self.user_data.get('username'), current):
            QMessageBox.warning(self, "Erreur", "Mot de passe actuel incorrect.")
            return
        
        # Mettre à jour le mot de passe
        try:
            from core.database import SessionLocal
            from core.models.user import User
            import bcrypt
            
            db = SessionLocal()
            user = db.query(User).filter(User.username == self.user_data.get('username')).first()
            if user:
                user.password_hash = bcrypt.hashpw(new.encode(), bcrypt.gensalt()).decode()
                db.commit()
                QMessageBox.information(self, "Succès", "Mot de passe modifié avec succès!")
                
                # Vider les champs
                self.current_password_input.clear()
                self.new_password_input.clear()
                self.confirm_password_input.clear()
            db.close()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la modification: {str(e)}")
    
    def _get_primary_button_style(self):
        """Retourne le style des boutons primaires"""
        return """
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 6px 18px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:disabled {
                background-color: #cbd5e1;
                color: #94a3b8;
            }
        """
    
    def _get_danger_button_style(self):
        """Retourne le style des boutons danger"""
        return """
            QPushButton {
                background-color: #ef4444;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 6px 18px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
            QPushButton:disabled {
                background-color: #fca5a5;
                color: #fef2f2;
            }
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
                    color: #eab308;
                    font-weight: 500;
                    padding: 4px 14px;
                    background-color: #fef9c3;
                    border-radius: 16px;
                    font-size: 12px;
                }
            """)
        else:
            self.status_label.setText("✅ Aucune modification")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #22c55e;
                    font-weight: 500;
                    padding: 4px 14px;
                    background-color: #f0fdf4;
                    border-radius: 16px;
                    font-size: 12px;
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
            "📝 Standard": "Merci pour votre confiance.\nVeuillez régler par virement bancaire sous 30 jours.",
            "✨ Minimaliste": "Merci pour votre confiance.",
            "💼 Professionnel": "Société XYZ\nSIRET: 123 456 789\nRCS: Paris B\nIBAN: FR76 XXXX XXXX XXXX\n\nMerci pour votre confiance."
        }
        
        if template_name in templates:
            self.invoice_footer_input.setText(templates[template_name])
    
    def select_logo(self):
        """Sélectionne un logo"""
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        file_dialog.setNameFilter("Images (*.png *.jpg *.jpeg *.bmp *.svg)")
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
                    80, 80,
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
        self.logo_preview.setText("📷")
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
                color: #22c55e;
                font-weight: 500;
                padding: 4px 14px;
                background-color: #f0fdf4;
                border-radius: 16px;
                font-size: 12px;
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
            QMessageBox.information(
                self,
                "✅ Succès",
                "Paramètres enregistrés avec succès !",
                QMessageBox.Ok
            )
            
            # Émettre signal
            self.settings_changed.emit(settings_to_save)
            
            # Mettre à jour originaux
            self.original_settings = settings_to_save.copy()
            
            # Recharger
            self.load_current_settings()
        else:
            QMessageBox.critical(
                self,
                "❌ Erreur",
                "Erreur lors de l'enregistrement des paramètres."
            )
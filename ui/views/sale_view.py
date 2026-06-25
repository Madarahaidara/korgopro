from PySide6.QtCore import (
    Qt, Signal, QTimer, QDateTime, QDate, QThread, 
    QPropertyAnimation, QEasingCurve, QPoint, QSize,
    QParallelAnimationGroup
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QComboBox, QDoubleSpinBox,
    QFrame, QGroupBox, QRadioButton, QButtonGroup,
    QHeaderView, QMessageBox, QSizePolicy, QApplication,
    QSplitter, QScrollArea, QDialog, QDialogButtonBox,
    QSpinBox, QTextEdit, QCheckBox, QFormLayout,
    QGraphicsOpacityEffect, QCompleter, QScrollBar,
    QWidgetItem
)
from PySide6.QtGui import (
    QFont, QColor, QBrush, QIcon, QPixmap, QKeySequence, QShortcut,
    QPainter, QPen, QResizeEvent, QDoubleValidator
)
from sqlalchemy.orm import joinedload, Session
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
import logging
import os

# Ajout de l'import SettingsManager
from utils.settings_manager import SettingsManager
from utils.print_dialogs import PrintOptionsDialog, PrintHistoryDialog

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constantes
MAX_PRODUCTS_PER_PAGE = 50
ROLES = {
    "ADMIN": ["all"],
    "MANAGER": ["view_sales", "create_sales", "cancel_sales", "view_reports"],
    "CAISSIER": ["create_sales", "view_products", "manage_customers"],
    "STOCKIST": ["view_products", "view_stock"],
    "ACCOUNTANT": ["view_sales", "view_reports"]
}

# Import des modèles
from core.database import SessionLocal
from core.models.stock_models import Product, Supplier
from core.models.sale_models import Sale, SaleItem, Customer, Payment
from core.sale_log_manager import SaleLogManager


# ===== COMPOSANTS ET SERVICES EXTERNES =====
from ui.views.sale_widgets import (
    get_icon,
    get_stock_icon,
    ToastManager,
    ProductLoaderThread,
    OptimizedCartTableWidget,
    ProductTableWidget
)
from ui.views.sale_services import (
    SaleService,
    ProductService,
    CustomerService
)
from ui.views.sale_dialogs import (
    QuantityDialog,
    CustomerSelectionDialog,
    NewCustomerDialog
)


# ===== VUE PRINCIPALE AMÉLIORÉE AVEC JOURNALISATION =====
class SaleView(QWidget):
    """
    Vue de vente pour le module caisse de Korgo
    Version avec journalisation complète des ventes
    """
    
    sale_completed = Signal(dict)
    sale_cancelled = Signal()
    
    def __init__(self, user: Dict[str, Any]):
        super().__init__()
        self.user = user
        self.current_page = 1
        self.total_pages = 1
        self.filters = {}
        self.loader_thread = None
        
        # Responsivité
        self.is_compact_layout = False
        self.current_width = 0
        
        # Initialiser SettingsManager
        self.settings_manager = SettingsManager()
        
        # Paramètres dynamiques
        self.CURRENCY = self.settings_manager.get_setting("currency", "FCFA")
        self.DEFAULT_TAX_RATE = self.settings_manager.get_setting("tax_rate", 20.0) / 100
        
        # Timer pour mise à jour planifiée des totaux
        self._totals_update_timer = QTimer()
        self._totals_update_timer.setSingleShot(True)
        self._totals_update_timer.setInterval(50)
        self._totals_update_timer.timeout.connect(self._calculate_totals_optimized)
        
        # Timer pour gestion de la responsivité
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(150)
        self._resize_timer.timeout.connect(self._adapt_to_size)
        
        # Toast Manager
        self.toast = ToastManager(self)
        
        # Vérifier les permissions
        if not self.has_permission("create_sales"):
            QMessageBox.critical(
                self, "Permission refusée",
                "Vous n'avez pas la permission d'accéder à la caisse."
            )
            return
        
        # Initialisation
        self.cart_items: List[Dict] = []
        self.selected_customer: Optional[Customer] = None
        self.recent_products: List[int] = []
        
        # Services
        self.db_session = SessionLocal()
        self.sale_service = SaleService(self.db_session)
        self.product_service = ProductService(self.db_session)
        self.customer_service = CustomerService(self.db_session)
        self.sale_log_manager = SaleLogManager()
        
        # Configuration UI
        self.setup_ui()
        self.setup_shortcuts()
        self.setup_autocomplete()
        self.setup_connections()
        
        # Initialisation des données
        self.load_filters()
        self.load_customers()
        self.generate_sale_number()
        self.load_products_async()
        
        # Timer pour l'horloge
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        
        # Appliquer le thème
        self.apply_theme()
    
    # ===== PERMISSIONS =====
    def has_permission(self, permission: str) -> bool:
        user_role = self.user.get("role", "CAISSIER")
        if user_role == "ADMIN":
            return True
        allowed_permissions = ROLES.get(user_role, [])
        return permission in allowed_permissions
    
    # ===== SETUP UI =====
    def setup_ui(self):
        self.setObjectName("SaleView")
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)
        
        # En-tête amélioré
        header_layout = self.create_header()
        main_layout.addLayout(header_layout)
        
        # Corps principal avec splitter
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setObjectName("mainSplitter")
        
        # Panneau produits (gauche)
        left_panel = self.create_products_panel()
        main_splitter.addWidget(left_panel)
        
        # Panneau panier avec scrollbar (droite)
        right_panel = self.create_scrollable_cart_panel()
        main_splitter.addWidget(right_panel)
        
        # Ajuster les proportions
        main_splitter.setSizes([450, 550])
        main_layout.addWidget(main_splitter, 1)
        
        # Barre de raccourcis
        self.shortcuts_bar = self.create_shortcuts_bar()
        main_layout.addWidget(self.shortcuts_bar)
        
        # Enregistrer la largeur initiale
        self.current_width = self.width()
    
    def create_header(self) -> QHBoxLayout:
        header_layout = QHBoxLayout()
        
        title_label = QLabel("Caisse")
        title_label.setObjectName("headerTitle")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        
        info_layout = QHBoxLayout()
        
        self.sale_number_label = QLabel("#000000")
        self.sale_number_label.setStyleSheet("font-weight: bold; color: #3b82f6; font-size: 14px;")
        
        self.date_label = QLabel(QDateTime.currentDateTime().toString("dd/MM/yyyy"))
        self.time_label = QLabel(QDateTime.currentDateTime().toString("HH:mm:ss"))
        self.time_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        self.client_label = QLabel("Client général")
        self.client_label.setStyleSheet("color: #10b981; font-weight: bold;")
        
        info_layout.addWidget(QLabel("N°:"))
        info_layout.addWidget(self.sale_number_label)
        info_layout.addWidget(QLabel("|"))
        info_layout.addWidget(self.date_label)
        info_layout.addWidget(QLabel("|"))
        info_layout.addWidget(self.time_label)
        info_layout.addWidget(QLabel("|"))
        info_layout.addWidget(self.client_label)
        info_layout.addStretch()
        
        self.compact_mode_btn = QPushButton("Mode Compact")
        self.compact_mode_btn.setIcon(get_icon("settings", "#6b7280", 16))
        self.compact_mode_btn.setCheckable(True)
        self.compact_mode_btn.setFixedWidth(120)
        self.compact_mode_btn.clicked.connect(self.toggle_compact_mode)
        self.compact_mode_btn.setStyleSheet("""
            QPushButton {
                background-color: #f3f4f6;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 5px 10px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e5e7eb;
            }
            QPushButton:checked {
                background-color: #3b82f6;
                color: white;
                border-color: #2563eb;
            }
        """)
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addLayout(info_layout)
        header_layout.addWidget(self.compact_mode_btn)
        
        return header_layout
    
    def create_products_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(8)
        
        # Barre de recherche
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Rechercher un produit (code, nom, catégorie)...")
        self.search_input.setObjectName("searchInput")
        self.search_input.setMinimumHeight(35)
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #d1d5db;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
        """)
        
        search_btn = QPushButton()
        search_btn.setIcon(get_icon("search", "#ffffff", 18))
        search_btn.setObjectName("searchButton")
        search_btn.setFixedSize(40, 35)
        search_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        search_btn.clicked.connect(self.load_products_async)
        
        search_layout.addWidget(self.search_input, 3)
        search_layout.addWidget(search_btn)
        layout.addLayout(search_layout)
        
        # Filtres
        filter_row = QHBoxLayout()
        
        self.category_combo = QComboBox()
        self.category_combo.addItem("Toutes catégories")
        self.category_combo.currentTextChanged.connect(self.on_filter_changed)
        
        self.supplier_combo = QComboBox()
        self.supplier_combo.addItem("Tous fournisseurs")
        self.supplier_combo.currentTextChanged.connect(self.on_filter_changed)
        
        filter_row.addWidget(QLabel("Catégorie:"))
        filter_row.addWidget(self.category_combo)
        filter_row.addWidget(QLabel("Fournisseur:"))
        filter_row.addWidget(self.supplier_combo)
        filter_row.addStretch()
        layout.addLayout(filter_row)
        
        # Boutons rapides
        quick_actions = QHBoxLayout()
        
        self.recent_btn = QPushButton("Produits récents")
        self.recent_btn.setIcon(get_icon("clock", "#6b7280", 14))
        self.recent_btn.setToolTip("Afficher les 10 derniers produits")
        self.recent_btn.clicked.connect(self.show_recent_products)
        
        self.low_stock_btn = QPushButton("Stock bas")
        self.low_stock_btn.setIcon(get_icon("alert", "#f59e0b", 14))
        self.low_stock_btn.clicked.connect(self.show_low_stock_products)
        
        for btn in [self.recent_btn, self.low_stock_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #f3f4f6;
                    border: 1px solid #d1d5db;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #e5e7eb;
                }
            """)
        
        quick_actions.addWidget(self.recent_btn)
        quick_actions.addWidget(self.low_stock_btn)
        quick_actions.addStretch()
        layout.addLayout(quick_actions)
        
        # Table produits
        self.products_table = ProductTableWidget()
        self.products_table.product_selected.connect(self.on_product_selected)
        self.products_table.doubleClicked.connect(self.add_to_cart)
        layout.addWidget(self.products_table)
        
        # Pagination
        pagination_layout = QHBoxLayout()
        
        self.prev_btn = QPushButton("Précédent")
        self.prev_btn.setIcon(get_icon("minus", "#6b7280", 14))
        self.prev_btn.setEnabled(False)
        self.prev_btn.clicked.connect(self.previous_page)
        
        self.page_label = QLabel("Page 1/1")
        self.page_label.setAlignment(Qt.AlignCenter)
        
        self.next_btn = QPushButton("Suivant")
        self.next_btn.setIcon(get_icon("plus", "#6b7280", 14))
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self.next_page)
        
        pagination_layout.addWidget(self.prev_btn)
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.next_btn)
        layout.addLayout(pagination_layout)
        
        # Boutons actions
        action_layout = QHBoxLayout()
        action_layout.addStretch()
        
        self.add_to_cart_btn = QPushButton("Ajouter au Panier (Entrée)")
        self.add_to_cart_btn.setIcon(get_icon("plus", "#ffffff", 16))
        self.add_to_cart_btn.setEnabled(False)
        self.add_to_cart_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:disabled {
                background-color: #9ca3af;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        self.add_to_cart_btn.clicked.connect(self.add_to_cart)
        
        action_layout.addWidget(self.add_to_cart_btn)
        layout.addLayout(action_layout)
        
        return panel
    
    def create_scrollable_cart_panel(self) -> QWidget:
        """Crée un panneau de droite entièrement scrollable"""
        
        container = QWidget()
        container.setObjectName("cartContainer")
        
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.cart_scroll_area = QScrollArea()
        self.cart_scroll_area.setObjectName("cartScrollArea")
        self.cart_scroll_area.setWidgetResizable(True)
        self.cart_scroll_area.setFrameShape(QFrame.NoFrame)
        self.cart_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.cart_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        self.cart_scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #f3f4f6;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #cbd5e1;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #94a3b8;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        scroll_content = QWidget()
        scroll_content.setObjectName("cartScrollContent")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(12)
        
        # Sections
        cart_section = self.create_cart_section()
        scroll_layout.addWidget(cart_section)
        
        options_section = self.create_options_section()
        scroll_layout.addWidget(options_section)
        
        totals_section = self.create_totals_section()
        scroll_layout.addWidget(totals_section)
        
        actions_section = self.create_actions_section()
        scroll_layout.addWidget(actions_section)
        
        scroll_layout.addStretch()
        
        self.cart_scroll_area.setWidget(scroll_content)
        main_layout.addWidget(self.cart_scroll_area)
        
        return container
    
    def create_cart_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("cartSection")
        
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        header_layout = QHBoxLayout()
        
        title_label = QLabel("PANIER")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #1f2937;")
        
        self.cart_count_label = QLabel("0 article")
        self.cart_count_label.setStyleSheet("""
            background-color: #e5e7eb;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
        """)
        
        header_layout.addWidget(title_label)
        header_layout.addWidget(self.cart_count_label)
        header_layout.addStretch()
        
        self.clear_cart_compact_btn = QPushButton()
        self.clear_cart_compact_btn.setIcon(get_icon("trash", "#ef4444", 16))
        self.clear_cart_compact_btn.setFixedSize(32, 32)
        self.clear_cart_compact_btn.setToolTip("Vider le panier")
        self.clear_cart_compact_btn.setEnabled(False)
        self.clear_cart_compact_btn.clicked.connect(self.clear_cart)
        self.clear_cart_compact_btn.setStyleSheet("""
            QPushButton {
                background-color: #fee2e2;
                border: none;
                border-radius: 16px;
            }
            QPushButton:hover {
                background-color: #fecaca;
            }
            QPushButton:disabled {
                background-color: #f3f4f6;
            }
        """)
        header_layout.addWidget(self.clear_cart_compact_btn)
        
        layout.addLayout(header_layout)
        
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #e5e7eb; max-height: 1px;")
        layout.addWidget(sep)
        
        self.cart_table = OptimizedCartTableWidget()
        self.cart_table.quantity_changed.connect(self.update_cart_quantity)
        self.cart_table.discount_changed.connect(self.update_cart_discount)
        self.cart_table.item_removed.connect(self.on_cart_item_removed)
        
        self.cart_table.setMinimumHeight(150)
        self.cart_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        layout.addWidget(self.cart_table, 1)
        
        return section
    
    def create_options_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("optionsSection")
        
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        title_label = QLabel("OPTIONS")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #4b5563;")
        layout.addWidget(title_label)
        
        # Groupe Client
        client_group = QGroupBox("Client")
        client_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        client_layout = QVBoxLayout(client_group)
        client_layout.setSpacing(8)
        
        client_select_layout = QHBoxLayout()
        self.customer_combo = QComboBox()
        self.customer_combo.addItem("Client général")
        self.customer_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        client_select_layout.addWidget(self.customer_combo, 1)
        
        self.select_customer_btn = QPushButton()
        self.select_customer_btn.setIcon(get_icon("user", "#3b82f6", 18))
        self.select_customer_btn.setFixedSize(36, 36)
        self.select_customer_btn.setToolTip("Sélectionner un client")
        self.select_customer_btn.setStyleSheet("""
            QPushButton {
                background-color: #eff6ff;
                border: 1px solid #3b82f6;
                border-radius: 18px;
            }
            QPushButton:hover {
                background-color: #dbeafe;
            }
        """)
        self.select_customer_btn.clicked.connect(self.select_customer)
        client_select_layout.addWidget(self.select_customer_btn)
        
        client_layout.addLayout(client_select_layout)
        
        self.client_info_label = QLabel("Client: Général")
        self.client_info_label.setStyleSheet("color: #6b7280; font-size: 11px; padding: 4px 8px; background-color: #f9fafb; border-radius: 4px;")
        self.client_info_label.setWordWrap(True)
        client_layout.addWidget(self.client_info_label)
        
        layout.addWidget(client_group)
        
        # Groupe Paiement
        payment_group = QGroupBox("Paiement")
        payment_group.setStyleSheet(client_group.styleSheet())
        
        payment_layout = QGridLayout(payment_group)
        payment_layout.setVerticalSpacing(8)
        payment_layout.setHorizontalSpacing(10)
        
        payment_layout.addWidget(QLabel("Mode:"), 0, 0)
        self.payment_combo = QComboBox()
        self.payment_combo.addItems(["ESPÈCES", "CARTE", "MOBILE MONEY", "VIREMENT", "CRÉDIT"])
        self.payment_combo.currentTextChanged.connect(self.on_payment_method_changed)
        payment_layout.addWidget(self.payment_combo, 0, 1)
        
        payment_layout.addWidget(QLabel("Remise:"), 1, 0)
        
        discount_layout = QHBoxLayout()
        self.discount_type_combo = QComboBox()
        self.discount_type_combo.addItems(["%", "FCFA"])
        self.discount_type_combo.setFixedWidth(60)
        self.discount_type_combo.currentIndexChanged.connect(self.schedule_totals_update)
        discount_layout.addWidget(self.discount_type_combo)
        
        # Remplacer QDoubleSpinBox par QLineEdit
        self.discount_input_edit = QLineEdit()
        self.discount_input_edit.setText("0")
        self.discount_input_edit.setAlignment(Qt.AlignRight)
        self.discount_input_edit.setValidator(QDoubleValidator(0, 1000000, 2))
        self.discount_input_edit.setStyleSheet("""
            QLineEdit {
                border: 2px solid #e5e7eb;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
        """)
        self.discount_input_edit.textChanged.connect(self.schedule_totals_update)
        discount_layout.addWidget(self.discount_input_edit, 1)
        
        payment_layout.addLayout(discount_layout, 1, 1)
        
        layout.addWidget(payment_group)
        
        return section
    
    def create_totals_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("totalsSection")
        
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        title_label = QLabel("TOTAUX")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #4b5563;")
        layout.addWidget(title_label)
        
        totals_grid = QGridLayout()
        totals_grid.setVerticalSpacing(10)
        totals_grid.setHorizontalSpacing(15)
        
        totals_grid.addWidget(QLabel("Sous-total:"), 0, 0)
        self.subtotal_label = QLabel(f"0 {self.CURRENCY}")
        self.subtotal_label.setAlignment(Qt.AlignRight)
        self.subtotal_label.setStyleSheet("font-size: 13px; color: #6b7280;")
        totals_grid.addWidget(self.subtotal_label, 0, 1)
        
        totals_grid.addWidget(QLabel("Remise:"), 1, 0)
        self.discount_label = QLabel(f"-0 {self.CURRENCY}")
        self.discount_label.setAlignment(Qt.AlignRight)
        self.discount_label.setStyleSheet("font-size: 13px; color: #ef4444;")
        totals_grid.addWidget(self.discount_label, 1, 1)
        
        tax_rate_percent = self.settings_manager.get_setting("tax_rate", 20.0)
        totals_grid.addWidget(QLabel(f"TVA ({tax_rate_percent:.0f}%):"), 2, 0)
        self.tax_label = QLabel(f"0 {self.CURRENCY}")
        self.tax_label.setAlignment(Qt.AlignRight)
        self.tax_label.setStyleSheet("font-size: 13px; color: #f59e0b;")
        totals_grid.addWidget(self.tax_label, 2, 1)
        
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #d1d5db; max-height: 2px; margin: 5px 0;")
        totals_grid.addWidget(sep, 3, 0, 1, 2)
        
        totals_grid.addWidget(QLabel("TOTAL:"), 4, 0)
        self.total_label = QLabel(f"0 {self.CURRENCY}")
        self.total_label.setAlignment(Qt.AlignRight)
        self.total_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #3b82f6;")
        totals_grid.addWidget(self.total_label, 4, 1)
        
        totals_grid.addWidget(QLabel("Payé:"), 5, 0)
        
        # Remplacer QDoubleSpinBox par QLineEdit
        self.amount_paid_edit = QLineEdit()
        self.amount_paid_edit.setObjectName("amount_paid_input")
        self.amount_paid_edit.setText("0")
        self.amount_paid_edit.setAlignment(Qt.AlignRight)
        self.amount_paid_edit.setValidator(QDoubleValidator(0, 100000000, 2))
        self.amount_paid_edit.setEnabled(True)
        self.amount_paid_edit.setStyleSheet("""
            QLineEdit {
                font-size: 14px;
                font-weight: bold;
                padding: 6px 10px;
                border: 2px solid #e5e7eb;
                border-radius: 6px;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
        """)
        self.amount_paid_edit.textChanged.connect(self.calculate_change)
        totals_grid.addWidget(self.amount_paid_edit, 5, 1)
        
        totals_grid.addWidget(QLabel("À rendre:"), 6, 0)
        self.change_label = QLabel(f"0 {self.CURRENCY}")
        self.change_label.setAlignment(Qt.AlignRight)
        self.change_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #10b981;")
        totals_grid.addWidget(self.change_label, 6, 1)
        
        layout.addLayout(totals_grid)
        
        return section
    
    def create_actions_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("actionsSection")
        
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        buttons_grid = QGridLayout()
        buttons_grid.setSpacing(10)
        
        self.cancel_btn = QPushButton("Annuler")
        self.cancel_btn.setIcon(get_icon("x", "#ffffff", 16))
        self.cancel_btn.clicked.connect(self.cancel_sale)
        self.cancel_btn.setMinimumHeight(40)
        self.cancel_btn.setStyleSheet(self._get_button_style("#ef4444"))
        
        self.validate_btn = QPushButton("Valider")
        self.validate_btn.setIcon(get_icon("check", "#ffffff", 16))
        self.validate_btn.clicked.connect(self.validate_sale)
        self.validate_btn.setEnabled(False)
        self.validate_btn.setMinimumHeight(45)
        self.validate_btn.setStyleSheet(self._get_button_style("#10b981", True))
        
        buttons_grid.addWidget(self.cancel_btn, 0, 0)
        buttons_grid.addWidget(self.validate_btn, 1, 0, 1, 1)
        
        layout.addLayout(buttons_grid)
        
        return section
    
    def _get_button_style(self, color: str, bold: bool = False) -> str:
        font_weight = "bold" if bold else "normal"
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                font-weight: {font_weight};
                font-size: 14px;
                border: none;
                border-radius: 8px;
                padding: 8px 12px;
            }}
            QPushButton:hover {{
                background-color: {self._darken_color(color)};
            }}
            QPushButton:disabled {{
                background-color: #9ca3af;
            }}
        """
    
    def _darken_color(self, color: str) -> str:
        color_map = {
            "#ef4444": "#dc2626",
            "#f59e0b": "#d97706",
            "#10b981": "#059669",
        }
        return color_map.get(color, color)
    
    def create_shortcuts_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("shortcutsBar")
        bar.setMaximumHeight(28)
        bar.setStyleSheet("""
            #shortcutsBar {
                background-color: #f3f4f6;
                border-top: 1px solid #d1d5db;
                padding: 2px 10px;
            }
        """)
        
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 0, 10, 0)
        
        shortcuts = [
            ("F1", "Aide"),
            ("F2", "Quantité"),
            ("F4", "Recherche"),
            ("F8", "Valider"),
            ("Ctrl+N", "Nouveau"),
            ("Suppr", "Retirer"),
            ("+/-", "Qté +/-"),
            ("Entrée", "Ajouter"),
        ]
        
        for key, desc in shortcuts:
            key_label = QLabel(f"<b>{key}</b> {desc}")
            key_label.setStyleSheet("""
                QLabel {
                    color: #6b7280;
                    font-size: 10px;
                    padding: 2px 6px;
                    background-color: white;
                    border: 1px solid #d1d5db;
                    border-radius: 3px;
                    margin: 0 2px;
                }
            """)
            layout.addWidget(key_label)
        
        layout.addStretch()
        return bar
    
    # ===== RACCOURCIS CLAVIER =====
    def setup_shortcuts(self):
        shortcuts = {
            "F1": self.show_shortcuts_help,
            "F2": self.focus_first_cart_quantity,
            "F4": lambda: self.search_input.setFocus(),
            "F8": self.validate_sale,
            "Ctrl+N": self.reset_sale,
            "Escape": self.clear_selection,
            "Delete": self.remove_selected_cart_item,
            "Return": self.add_to_cart,
            "Ctrl+Return": self.validate_sale,
            "Ctrl++": self.increase_selected_quantity,
            "Ctrl+-": self.decrease_selected_quantity,
        }
        
        for key, callback in shortcuts.items():
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
    
    def show_shortcuts_help(self):
        help_text = """
        <h3>Raccourcis Caisse</h3>
        <table style='width:100%'>
        <tr><td><b>F1</b></td><td>Cette aide</td></tr>
        <tr><td><b>F2</b></td><td>Modifier quantité 1er article</td></tr>
        <tr><td><b>F4</b></td><td>Rechercher un produit</td></tr>
        <tr><td><b>F8</b></td><td>Valider la vente</td></tr>
        <tr><td><b>Ctrl+N</b></td><td>Nouvelle vente</td></tr>
        <tr><td><b>Entrée</b></td><td>Ajouter au panier</td></tr>
        <tr><td><b>Ctrl+Entrée</b></td><td>Valider</td></tr>
        <tr><td><b>Suppr</b></td><td>Retirer article sélectionné</td></tr>
        <tr><td><b>Ctrl++</b></td><td>Augmenter quantité</td></tr>
        <tr><td><b>Ctrl+-</b></td><td>Diminuer quantité</td></tr>
        </table>
        """
        QMessageBox.information(self, "Aide Raccourcis", help_text)
    
    def focus_first_cart_quantity(self):
        if self.cart_items and self.cart_table.rowCount() > 0:
            widget = self.cart_table.cellWidget(0, 2)
            if widget:
                widget.setFocus()
                widget.selectAll()
    
    def remove_selected_cart_item(self):
        current_row = self.cart_table.currentRow()
        if current_row >= 0 and current_row < len(self.cart_items):
            removed = self.cart_items.pop(current_row)
            self.update_cart_display()
            self.toast.show(f"{removed['product_name']} retiré", "warning")
    
    def increase_selected_quantity(self):
        current_row = self.cart_table.currentRow()
        if current_row >= 0 and current_row < len(self.cart_items):
            self.cart_items[current_row]['quantity'] += 1
            self.update_cart_display()
    
    def decrease_selected_quantity(self):
        current_row = self.cart_table.currentRow()
        if current_row >= 0 and current_row < len(self.cart_items):
            if self.cart_items[current_row]['quantity'] > 0.5:
                self.cart_items[current_row]['quantity'] -= 1
                self.update_cart_display()
    
    def reset_sale(self):
        if self.cart_items:
            reply = QMessageBox.question(self, "Nouvelle vente", 
                                        "Abandonner la vente en cours ?",
                                        QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return
        
        self.cart_items.clear()
        self.update_cart_display()
        self.generate_sale_number()
        self.amount_paid_edit.setText("0")
        self.selected_customer = None
        self.client_info_label.setText("Client: Général")
        self.client_info_label.setStyleSheet("color: #6b7280; font-size: 11px; padding: 4px 8px; background-color: #f9fafb; border-radius: 4px;")
        self.discount_input_edit.setText("0")
        self.toast.show("Nouvelle vente prête", "info")
    
    def clear_selection(self):
        self.products_table.clearSelection()
    
    # ===== AUTO-COMPLÉTION =====
    def setup_autocomplete(self):
        try:
            product_names = self.product_service.get_all_product_names()
            
            self.completer = QCompleter(product_names, self)
            self.completer.setCaseSensitivity(Qt.CaseInsensitive)
            self.completer.setFilterMode(Qt.MatchContains)
            self.completer.setCompletionMode(QCompleter.PopupCompletion)
            self.completer.setMaxVisibleItems(8)
            
            self.search_input.setCompleter(self.completer)
            
            self.completer.popup().setStyleSheet("""
                QAbstractItemView {
                    background-color: white;
                    border: 1px solid #3b82f6;
                    border-radius: 6px;
                    padding: 4px;
                    font-size: 13px;
                    selection-background-color: #eff6ff;
                    selection-color: #1e40af;
                }
                QAbstractItemView::item {
                    padding: 8px 12px;
                    border-radius: 4px;
                    min-height: 30px;
                }
                QAbstractItemView::item:hover {
                    background-color: #dbeafe;
                }
            """)
        except Exception as e:
            print(f"Erreur auto-complétion: {e}")
    
    # ===== MODE COMPACT =====
    def toggle_compact_mode(self):
        is_compact = self.compact_mode_btn.isChecked()
        
        if is_compact:
            self.compact_mode_btn.setText("Mode Étendu")
            self.category_combo.setVisible(False)
            self.supplier_combo.setVisible(False)
            self.recent_btn.setVisible(False)
            self.low_stock_btn.setVisible(False)
            self.products_table.setColumnHidden(4, True)
        else:
            self.compact_mode_btn.setText("Mode Compact")
            self.category_combo.setVisible(True)
            self.supplier_combo.setVisible(True)
            self.recent_btn.setVisible(True)
            self.low_stock_btn.setVisible(True)
            self.products_table.setColumnHidden(4, False)
    
    # ===== CONNEXIONS =====
    def setup_connections(self):
        self.search_input.returnPressed.connect(self.load_products_async)
    
    # ===== CHARGEMENT DONNÉES =====
    def load_filters(self):
        categories = self.product_service.get_product_categories()
        suppliers = self.product_service.get_suppliers()
        
        self.category_combo.clear()
        self.category_combo.addItem("Toutes catégories")
        for category in categories:
            self.category_combo.addItem(category)
        
        self.supplier_combo.clear()
        self.supplier_combo.addItem("Tous fournisseurs")
        for supplier in suppliers:
            self.supplier_combo.addItem(supplier)
    
    def load_customers(self):
        try:
            customers = self.customer_service.get_customers()
            self.customer_combo.clear()
            self.customer_combo.addItem("Client général", None)
            
            for customer in customers:
                text = f"{customer.first_name} {customer.last_name}"
                if customer.company:
                    text += f" ({customer.company})"
                self.customer_combo.addItem(text, customer.id)
        except Exception as e:
            logger.error(f"Erreur chargement clients: {e}")
    
    def load_products_async(self):
        self.filters = {
            "search": self.search_input.text(),
            "category": self.category_combo.currentText(),
            "supplier": self.supplier_combo.currentText()
        }
        
        self.products_table.setEnabled(False)
        self.add_to_cart_btn.setEnabled(False)
        
        if self.loader_thread and self.loader_thread.isRunning():
            self.loader_thread.stop()
        
        self.loader_thread = ProductLoaderThread(
            self.product_service,
            self.current_page,
            self.filters
        )
        self.loader_thread.products_loaded.connect(self.on_products_loaded)
        self.loader_thread.error_occurred.connect(self.on_load_error)
        self.loader_thread.start()
    
    def on_products_loaded(self, products: List[Product], total: int):
        self.products_table.display_products(products, self.CURRENCY)
        self.products_table.setEnabled(True)
        
        self.total_pages = max(1, (total + MAX_PRODUCTS_PER_PAGE - 1) // MAX_PRODUCTS_PER_PAGE)
        self.page_label.setText(f"Page {self.current_page}/{self.total_pages}")
        
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < self.total_pages)
    
    def on_load_error(self, error_msg: str):
        self.toast.show(error_msg, "error")
        self.products_table.setEnabled(True)
    
    # ===== NAVIGATION =====
    def previous_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_products_async()
    
    def next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.load_products_async()
    
    def on_filter_changed(self):
        self.current_page = 1
        self.load_products_async()
    
    def generate_sale_number(self):
        try:
            sale_number = self.sale_service.generate_sale_number()
            self.sale_number_label.setText(f"#{sale_number}")
        except Exception as e:
            logger.error(f"Erreur génération numéro: {e}")
    
    # ===== SÉLECTION PRODUIT =====
    def on_product_selected(self, product_id: int):
        self.add_to_cart_btn.setEnabled(True)
    
    # ===== GESTION PANIER OPTIMISÉE =====
    def add_to_cart(self):
        selected = self.products_table.selectedItems()
        if not selected:
            return
        
        row = selected[0].row()
        product_id = self.products_table.item(row, 0).data(Qt.UserRole)
        
        if not product_id:
            return
        
        product = self.db_session.query(Product).get(product_id)
        if not product:
            return
        
        if product.is_out_of_stock:
            self.toast.show(f"{product.name} - Rupture de stock!", "error")
            return
        
        existing = next((item for item in self.cart_items if item["product_id"] == product_id), None)
        
        if existing:
            existing["quantity"] += 1
            self.toast.show(f"{product.name} x{existing['quantity']}", "success", 1500)
        else:
            cart_item = {
                "product_id": product.id,
                "product_code": product.code or "",
                "product_name": product.name,
                "unit_price": product.sale_price,
                "quantity": 1.0,
                "discount_percent": 0.0,
                "discount_amount": 0.0,
                "line_total": product.sale_price
            }
            self.cart_items.append(cart_item)
            
            if product_id not in self.recent_products:
                self.recent_products.insert(0, product_id)
                if len(self.recent_products) > 10:
                    self.recent_products.pop()
            
            self.toast.show(f"{product.name} ajouté", "success", 1500)
        
        self.update_cart_display()
    
    def update_cart_display(self):
        scroll_bar = self.cart_scroll_area.verticalScrollBar()
        scroll_pos = scroll_bar.value() if scroll_bar else 0
        
        self.cart_table.display_cart_items(self.cart_items, self.CURRENCY)
        
        item_count = len(self.cart_items)
        self.cart_count_label.setText(f"{item_count} article{'s' if item_count > 1 else ''}")
        
        if scroll_bar:
            QTimer.singleShot(10, lambda: scroll_bar.setValue(min(scroll_pos, scroll_bar.maximum())))
        
        self.schedule_totals_update()
        self.update_cart_state()
        self._adjust_cart_table_height()
    
    def update_cart_quantity(self, row: int, quantity: float):
        if 0 <= row < len(self.cart_items):
            if abs(self.cart_items[row]["quantity"] - quantity) > 0.01:
                self.cart_items[row]["quantity"] = quantity
                self.schedule_totals_update()
    
    def update_cart_discount(self, row: int, discount: float):
        if 0 <= row < len(self.cart_items):
            if abs(self.cart_items[row].get("discount_percent", 0) - discount) > 0.01:
                self.cart_items[row]["discount_percent"] = discount
                self.schedule_totals_update()
    
    def on_cart_item_removed(self, row: int):
        if 0 <= row < len(self.cart_items):
            self.cart_items.pop(row)
            self.schedule_totals_update()
            self.update_cart_state()
    
    def clear_cart(self):
        if not self.cart_items:
            return
        
        reply = QMessageBox.question(self, "Vider", "Vider le panier?",
                                     QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.cart_items.clear()
            self.update_cart_display()
            self.toast.show("Panier vidé", "info")
    
    def select_customer(self):
        dialog = CustomerSelectionDialog(self.customer_service, self.CURRENCY, self)
        if dialog.exec() == QDialog.Accepted and dialog.selected_customer:
            self.selected_customer = dialog.selected_customer
            customer = self.selected_customer
            
            name = f"{customer.first_name} {customer.last_name}"
            info_text = f"Client: {name}"
            if customer.company:
                info_text += f" ({customer.company})"
            if customer.balance > 0:
                info_text += f" | Solde: {customer.balance:,.0f} {self.CURRENCY}"
            
            self.client_info_label.setText(info_text)
            self.client_info_label.setStyleSheet("color: #059669; font-size: 11px; padding: 4px 8px; background-color: #ecfdf5; border-radius: 4px;")
            
            index = self.customer_combo.findData(customer.id)
            if index >= 0:
                self.customer_combo.setCurrentIndex(index)
            else:
                text = f"{customer.first_name} {customer.last_name}"
                if customer.company:
                    text += f" ({customer.company})"
                self.customer_combo.addItem(text, customer.id)
                self.customer_combo.setCurrentIndex(self.customer_combo.count() - 1)
            
            self.toast.show(f"Client sélectionné: {name}", "success", 1500)
    
    # ===== CALCULS OPTIMISÉS =====
    def schedule_totals_update(self):
        if self._totals_update_timer.isActive():
            self._totals_update_timer.stop()
        self._totals_update_timer.start()
    
    def get_discount_value(self) -> float:
        """Récupère la valeur de la remise depuis le QLineEdit"""
        try:
            return float(self.discount_input_edit.text())
        except ValueError:
            return 0.0
    
    def get_amount_paid(self) -> float:
        """Récupère le montant payé depuis le QLineEdit"""
        try:
            return float(self.amount_paid_edit.text())
        except ValueError:
            return 0.0
    
    def _calculate_totals_optimized(self):
        if not self.cart_items:
            self.subtotal_label.setText(f"0 {self.CURRENCY}")
            self.discount_label.setText(f"0 {self.CURRENCY}")
            self.tax_label.setText(f"0 {self.CURRENCY}")
            self.total_label.setText(f"0 {self.CURRENCY}")
            self.calculate_change()
            return
        
        subtotal = 0.0
        for item in self.cart_items:
            line_subtotal = item["quantity"] * item["unit_price"]
            item_discount = line_subtotal * (item.get("discount_percent", 0) / 100)
            item["discount_amount"] = item_discount
            item["line_total"] = line_subtotal - item_discount
            subtotal += line_subtotal - item_discount
        
        discount_value = self.get_discount_value()
        is_percent = self.discount_type_combo.currentIndex() == 0
        
        if is_percent:
            global_discount = subtotal * (discount_value / 100)
        else:
            global_discount = discount_value
        
        global_discount = min(global_discount, subtotal)
        
        after_discount = subtotal - global_discount
        tax_amount = after_discount * self.DEFAULT_TAX_RATE
        total = after_discount + tax_amount
        
        self.subtotal_label.setText(f"{subtotal:,.0f} {self.CURRENCY}")
        self.discount_label.setText(f"-{global_discount:,.0f} {self.CURRENCY}")
        self.tax_label.setText(f"{tax_amount:,.0f} {self.CURRENCY}")
        self.total_label.setText(f"{total:,.0f} {self.CURRENCY}")
        
        self.calculate_change()
    
    def calculate_totals(self):
        self.schedule_totals_update()
    
    def calculate_change(self):
        total_text = self.total_label.text().replace(self.CURRENCY, "").replace(",", "").strip()
        try:
            total = float(total_text) if total_text else 0
        except:
            total = 0
        
        amount_paid = self.get_amount_paid()
        change = amount_paid - total
        
        if change >= 0:
            self.change_label.setText(f"{change:,.0f} {self.CURRENCY}")
            self.change_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #10b981;")
        else:
            self.change_label.setText(f"{-change:,.0f} {self.CURRENCY} à payer")
            self.change_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #ef4444;")
    
    def update_cart_state(self):
        has_items = len(self.cart_items) > 0
        self.clear_cart_compact_btn.setEnabled(has_items)
        self.validate_btn.setEnabled(has_items)
    
    # ===== GESTION DE LA RESPONSIVITÉ =====
    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        
        new_width = event.size().width()
        if abs(new_width - self.current_width) > 50:
            self.current_width = new_width
            if self._resize_timer.isActive():
                self._resize_timer.stop()
            self._resize_timer.start()
    
    def _adapt_to_size(self):
        width = self.width()
        
        if width < 1200:
            if not self.is_compact_layout:
                self._enable_compact_layout()
        else:
            if self.is_compact_layout:
                self._disable_compact_layout()
        
        self._adjust_cart_table_height()
        self.update_cart_display()
    
    def _enable_compact_layout(self):
        self.is_compact_layout = True
        
        self.cart_scroll_area.widget().layout().setContentsMargins(0, 0, 0, 0)
        
        self.validate_btn.setMinimumHeight(40)
        self.validate_btn.setStyleSheet(self._get_button_style("#10b981", True) + "font-size: 13px;")
        
        self.cart_table.setColumnWidth(2, 70)
        self.cart_table.setColumnWidth(4, 70)
        
        if self.width() < 1000:
            self.cart_table.setColumnHidden(0, True)
        else:
            self.cart_table.setColumnHidden(0, False)
    
    def _disable_compact_layout(self):
        self.is_compact_layout = False
        
        self.cart_scroll_area.widget().layout().setContentsMargins(0, 0, 0, 0)
        
        self.validate_btn.setMinimumHeight(45)
        self.validate_btn.setStyleSheet(self._get_button_style("#10b981", True))
        
        self.cart_table.setColumnWidth(2, 90)
        self.cart_table.setColumnWidth(4, 90)
        self.cart_table.setColumnHidden(0, False)
    
    def _adjust_cart_table_height(self):
        row_count = self.cart_table.rowCount()
        if row_count > 0:
            row_height = 45
            desired_height = min(row_count * row_height + 30, 400)
            self.cart_table.setMinimumHeight(min(desired_height, 350))
        else:
            self.cart_table.setMinimumHeight(120)
    
    def on_payment_method_changed(self, method: str):
        if method == "CRÉDIT":
            self.amount_paid_edit.setEnabled(False)
            self.amount_paid_edit.setText("0")
            self.change_label.setText(f"0 {self.CURRENCY}")
        else:
            self.amount_paid_edit.setEnabled(True)
            self.amount_paid_edit.setFocus()
    
    # ===== VALIDATION VENTE AVEC JOURNALISATION =====
    def ensure_cart_items_have_line_total(self):
        for item in self.cart_items:
            if "line_total" not in item:
                item["line_total"] = item["quantity"] * item["unit_price"] * (1 - item.get("discount_percent", 0) / 100)
    
    def validate_sale(self):
        if not self.cart_items:
            self.toast.show("Le panier est vide!", "warning")
            return
        
        total = float(self.total_label.text().replace(self.CURRENCY, "").replace(",", "").strip())
        amount_paid = self.get_amount_paid()
        payment_method = self.payment_combo.currentText()
        
        if payment_method != "CRÉDIT" and amount_paid < total:
            self.toast.show("Montant insuffisant!", "error")
            return
        
        for item in self.cart_items:
            product = self.db_session.query(Product).get(item["product_id"])
            if product and item["quantity"] > product.quantity:
                self.toast.show(f"Stock insuffisant: {product.name}", "error")
                return
        
        self.ensure_cart_items_have_line_total()
        
        company_info = self.settings_manager.get_company_info()
        
        # Préparer les infos utilisateur pour la journalisation
        user_info = {
            "id": self.user.get("id"),
            "username": self.user.get("username", "unknown"),
            "role": self.user.get("role", "CAISSIER")
        }
        
        sale_data = {
            "sale_number": self.sale_number_label.text().replace("#", ""),
            "customer_id": self.selected_customer.id if self.selected_customer else None,
            "cashier_id": self.user.get("id"),
            "subtotal": float(self.subtotal_label.text().replace(self.CURRENCY, "").replace(",", "").strip()),
            "discount_amount": abs(float(self.discount_label.text().replace(self.CURRENCY, "").replace("-", "").replace(",", "").strip())),
            "tax_amount": float(self.tax_label.text().replace(self.CURRENCY, "").replace(",", "").strip()),
            "total_amount": total,
            "amount_paid": amount_paid,
            "change_amount": max(0, amount_paid - total),
            "payment_method": payment_method,
            "payment_status": "PAID" if amount_paid >= total else "PARTIAL",
            "items": self.cart_items
        }
        
        # Appeler le service avec user_info pour la journalisation
        success, sale, message = self.sale_service.create_sale(sale_data, self.CURRENCY, user_info)
        
        if success:
            self.toast.show(f"Vente réussie! Total: {total:,.0f} {self.CURRENCY}", "success", 5000)
            
            reply = QMessageBox.question(
                self, "Succès",
                f"Vente créée avec succès!\nSouhaitez-vous imprimer la facture?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                print_data = {
                    'sale_id': sale.id,
                    'sale_number': sale.sale_number,
                    'date': sale.sale_date.strftime('%d/%m/%Y %H:%M'),
                    'total': sale.total_amount,
                    'customer': f"{sale.customer.first_name} {sale.customer.last_name}" if sale.customer else "Client général",
                    'company_name': company_info['name'],
                    'company_address': company_info['address'],
                    'company_phone': company_info['phone'],
                    'company_email': company_info['email'],
                    'currency': self.CURRENCY,
                    'tax_rate': self.settings_manager.get_setting("tax_rate", 20.0)
                }
                
                print_dialog = PrintOptionsDialog(print_data, self)
                print_dialog.exec()
            
            self.sale_completed.emit({
                "sale_id": sale.id,
                "sale_number": sale.sale_number,
                "total": sale.total_amount,
                "profit": sale.profit,
                "currency": self.CURRENCY
            })
            
            self.cart_items.clear()
            self.update_cart_display()
            self.generate_sale_number()
            self.amount_paid_edit.setText("0")
            self.selected_customer = None
            self.client_info_label.setText("Client: Général")
            self.client_info_label.setStyleSheet("color: #6b7280; font-size: 11px; padding: 4px 8px; background-color: #f9fafb; border-radius: 4px;")
            self.discount_input_edit.setText("0")
        else:
            self.toast.show(message, "error")
    
    def cancel_sale(self):
        if not self.cart_items:
            return
        
        reply = QMessageBox.question(self, "Annuler", "Annuler la vente?",
                                     QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.cart_items.clear()
            self.update_cart_display()
            self.sale_cancelled.emit()
            self.toast.show("Vente annulée", "warning")
    
    # ===== PRODUITS RÉCENTS / STOCK BAS =====
    def show_recent_products(self):
        if self.recent_products:
            products = self.db_session.query(Product)\
                .filter(Product.id.in_(self.recent_products), Product.active == True)\
                .all()
            if products:
                self.products_table.display_products(products, self.CURRENCY)
                self.toast.show(f"{len(products)} produits récents", "info")
            else:
                self.load_products_async()
        else:
            self.toast.show("Aucun produit récent", "info")
    
    def show_low_stock_products(self):
        products = self.db_session.query(Product)\
            .filter(Product.quantity <= Product.min_stock, Product.active == True)\
            .all()
        if products:
            self.products_table.display_products(products, self.CURRENCY)
            self.toast.show(f"{len(products)} produits en stock bas", "warning")
        else:
            self.toast.show("Aucun produit en stock bas", "success")
    
    # ===== UTILITAIRES =====
    def update_time(self):
        self.time_label.setText(QDateTime.currentDateTime().toString("HH:mm:ss"))
    
    def on_settings_changed(self, settings: dict):
        old_currency = self.CURRENCY
        self.CURRENCY = settings.get("currency", "FCFA")
        self.DEFAULT_TAX_RATE = settings.get("tax_rate", 20.0) / 100
        
        if old_currency != self.CURRENCY:
            self.amount_paid_edit.setPrefix(f"{self.CURRENCY} ")
            self.calculate_totals()
            self.calculate_change()
        
        if self.cart_items:
            self.update_cart_display()
    
    def apply_theme(self):
        possible_paths = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "themes", "sale_view.qss"),
        ]
        
        for path in possible_paths:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.setStyleSheet(f.read())
                    return
            except FileNotFoundError:
                continue
    
    def closeEvent(self, event):
        self._cleanup_resources()
        super().closeEvent(event)
    
    def _cleanup_resources(self):
        """Nettoie toutes les ressources pour éviter les fuites mémoire"""
        if self.loader_thread and self.loader_thread.isRunning():
            self.loader_thread.stop()
            self.loader_thread.wait(2000)
        
        if hasattr(self, 'timer') and self.timer.isActive():
            self.timer.stop()
        
        if hasattr(self, '_totals_update_timer'):
            self._totals_update_timer.stop()
        
        if hasattr(self, '_resize_timer'):
            self._resize_timer.stop()
        
        if hasattr(self, 'db_session'):
            try:
                self.db_session.close()
                logger.debug("Session DB de SaleView fermée")
            except Exception as e:
                logger.warning(f"Erreur fermeture session SaleView: {e}")
    
    def destroy(self, destroyWindow=True, destroySubWindows=True):
        """Override de destroy pour garantir le nettoyage"""
        self._cleanup_resources()
        super().destroy(destroyWindow, destroySubWindows)
        
    def __del__(self):
        """Destructeur de sécurité (ne pas compter uniquement sur closeEvent)"""
        try:
            if hasattr(self, 'db_session'):
                self.db_session.close()
        except:
            pass

# ui/views/proforma_invoice_view.py
"""
Vue principale pour la gestion des factures Pro Forma et Factures Définitives
Workflow: Brouillon → Pro Forma → Validation → Facture Définitive → Paiement
"""

from enum import Enum
from PySide6.QtCore import Qt, Signal, QTimer, QDateTime, QDate
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QComboBox, QFrame, QGroupBox, QMessageBox,
    QTextEdit, QHeaderView, QTabWidget, QDialog, QDialogButtonBox,
    QDateEdit, QAbstractItemView, QScrollArea, QSplitter, QMenu,
    QFormLayout, QSizePolicy, QInputDialog, QApplication
)
from PySide6.QtGui import QFont, QColor, QBrush, QAction, QTextDocument, QIcon, QPixmap, QShortcut, QKeySequence
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
import logging

from core.database import SessionLocal
from core.models.sale_models import ProformaInvoice, ProformaInvoiceItem, Sale, SaleItem
from core.models.stock_models import Product
from core.models.customer import Customer
from core.proforma_invoice_manager import ProformaInvoiceManager
from utils.settings_manager import SettingsManager

logger = logging.getLogger(__name__)


# ============= CONFIGURATION =============
class ProformaConfig:
    """Configuration de la proforma"""
    
    COMPANY_INFO = {
        "name": "MON ENTREPRISE",
        "address": "Ouagadougou",
        "phone": "+226 XX XX XX XX",
        "email": "contact@entreprise.com"
    }
    
    DEFAULTS = {
        "tax_percent": 18,
        "validity_days": 30,
        "currency": "FCFA",
        "footer_text": "Merci de votre confiance",
        "manager_signature": "Le Gérant"
    }
    
    PIECES_KEYWORDS = ['disque', 'huile', 'bougie', 'transmission', 'caoutchouc', 
                       'batterie', 'carburant', 'pièce', 'moteur', 'pneu']


class InvoiceStatus(Enum):
    """Statuts des proformas"""
    BROUILLON = ("Brouillon", "#fef3c7", "#92400e")
    EN_ATTENTE = ("En attente", "#fef3c7", "#92400e")
    ENVOYEE = ("Envoyé", "#dbeafe", "#1e40af")
    ACCEPTEE = ("Accepté", "#d1fae5", "#065f46")
    REFUSEE = ("Refusé", "#fee2e2", "#991b1b")
    EXPIREE = ("Expiré", "#f3f4f6", "#4b5563")
    CONVERTIE = ("Converti", "#e0e7ff", "#3730a3")
    
    def __init__(self, label, bg_color, fg_color):
        self.label = label
        self.bg_color = bg_color
        self.fg_color = fg_color


class FactureStatus(Enum):
    """Statuts des factures définitives"""
    BROUILLON = ("Brouillon", "#fef3c7", "#92400e")
    EMISE = ("Émise", "#dbeafe", "#1e40af")
    PARTIELLEMENT_PAYEE = ("Partiellement payée", "#fef3c7", "#92400e")
    PAYEE = ("Payée", "#d1fae5", "#065f46")
    EN_RETARD = ("En retard", "#fee2e2", "#991b1b")
    ANNULEE = ("Annulée", "#f3f4f6", "#4b5563")
    
    def __init__(self, label, bg_color, fg_color):
        self.label = label
        self.bg_color = bg_color
        self.fg_color = fg_color


# ============= SERVICES =============
class ProformaService:
    """Service pour la gestion des proformas"""
    
    def __init__(self, db_session: SessionLocal):
        self.db_session = db_session
        self.manager = ProformaInvoiceManager(db_session)
        self.settings_manager = SettingsManager()
    
    def create_proforma(self, data: Dict[str, Any], user_id: int) -> Tuple[bool, Optional[ProformaInvoice], str]:
        """Crée une nouvelle proforma"""
        try:
            proforma = self.manager.create_proforma(
                customer_id=data.get("customer_id"),
                created_by_id=user_id,
                items=data.get("items", []),
                discount_percent=data.get("discount_percent", 0),
                tax_percent=data.get("tax_percent", ProformaConfig.DEFAULTS["tax_percent"]),
                notes=data.get("notes", ""),
                terms_and_conditions=data.get("subject", ""),
                valid_until=data.get("valid_until")
            )
            return True, proforma, "Proforma créée avec succès"
        except Exception as e:
            logger.error(f"Erreur création proforma: {e}")
            return False, None, str(e)
    
    def update_proforma(self, proforma_id: int, data: Dict[str, Any]) -> Tuple[bool, Optional[ProformaInvoice], str]:
        """Met à jour une proforma existante"""
        try:
            proforma = self.manager.update_proforma(
                proforma_id,
                customer_id=data.get("customer_id"),
                items=data.get("items", []),
                discount_percent=data.get("discount_percent", 0),
                tax_percent=data.get("tax_percent", ProformaConfig.DEFAULTS["tax_percent"]),
                notes=data.get("notes", ""),
                terms_and_conditions=data.get("subject", ""),
                valid_until=data.get("valid_until")
            )
            return True, proforma, "Proforma mise à jour avec succès"
        except Exception as e:
            logger.error(f"Erreur mise à jour proforma: {e}")
            return False, None, str(e)
    
    def get_proforma(self, proforma_id: int) -> Optional[ProformaInvoice]:
        return self.manager.get_proforma(proforma_id)
    
    def get_proforma_by_number(self, number: str) -> Optional[ProformaInvoice]:
        try:
            return self.db_session.query(ProformaInvoice).filter(
                ProformaInvoice.proforma_number == number
            ).first()
        except Exception as e:
            logger.error(f"Erreur recherche proforma par numéro: {e}")
            return None
    
    def convert_to_sale(self, proforma_id: int, user_id: int) -> Tuple[bool, Optional[Sale], str]:
        """Convertit une proforma en vente"""
        try:
            sale = self.manager.convert_to_sale(proforma_id, user_id)
            return True, sale, f"Proforma convertie en facture {sale.sale_number}"
        except Exception as e:
            logger.error(f"Erreur conversion proforma: {e}")
            return False, None, str(e)
    
    def list_proformas(self, filters: Dict = None) -> List[ProformaInvoice]:
        proformas = self.manager.list_proformas()
        
        if filters:
            if filters.get("status") and filters["status"] != "ALL":
                proformas = [p for p in proformas if p.status == filters["status"]]
            
            if filters.get("search"):
                search = filters["search"].lower()
                proformas = [p for p in proformas if 
                            search in p.proforma_number.lower() or 
                            (p.customer and search in p.customer.full_name.lower())]
            
            if filters.get("date_filter"):
                today = datetime.now().date()
                if filters["date_filter"] == "today":
                    proformas = [p for p in proformas if p.created_date.date() == today]
                elif filters["date_filter"] == "week":
                    week_start = today - timedelta(days=today.weekday())
                    proformas = [p for p in proformas if p.created_date.date() >= week_start]
                elif filters["date_filter"] == "month":
                    proformas = [p for p in proformas if p.created_date.month == today.month]
        
        return proformas
    
    def generate_proforma_number(self) -> str:
        today = datetime.now()
        count = self.db_session.query(ProformaInvoice).filter(
            ProformaInvoice.created_date >= today.date()
        ).count()
        return f"PF-{today.year}-{count + 1:06d}"


class CustomerService:
    """Service pour la gestion des clients"""
    
    def __init__(self, db_session: SessionLocal):
        self.db_session = db_session
    
    def get_customers(self, search: str = "") -> List[Customer]:
        try:
            query = self.db_session.query(Customer).filter(Customer.active == True)
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    (Customer.first_name.ilike(search_term)) |
                    (Customer.last_name.ilike(search_term)) |
                    (Customer.company.ilike(search_term)) |
                    (Customer.phone.ilike(search_term))
                )
            return query.order_by(Customer.last_name).all()
        except Exception as e:
            logger.error(f"Erreur chargement clients: {e}")
            return []
    
    def create_customer(self, data: Dict[str, Any]) -> Tuple[bool, Optional[Customer], str]:
        try:
            if data.get("email"):
                existing = self.db_session.query(Customer).filter(Customer.email == data["email"]).first()
                if existing:
                    return False, None, "Un client avec cet email existe déjà"
            
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            code = f"CUST{timestamp[-6:]}"
            
            customer = Customer(
                code=code,
                first_name=data["first_name"],
                last_name=data["last_name"],
                company=data.get("company"),
                email=data.get("email"),
                phone=data.get("phone"),
                mobile=data.get("mobile"),
                address=data.get("address"),
                city=data.get("city"),
                country=data.get("country"),
                customer_type=data.get("customer_type", "RETAIL"),
                notes=data.get("notes"),
                active=True
            )
            self.db_session.add(customer)
            self.db_session.commit()
            return True, customer, f"Client créé (Code: {code})"
        except Exception as e:
            self.db_session.rollback()
            return False, None, str(e)


class ProductService:
    """Service pour la gestion des produits"""
    
    def __init__(self, db_session: SessionLocal):
        self.db_session = db_session
    
    def search_products(self, search: str = "") -> List[Product]:
        try:
            query = self.db_session.query(Product).filter(Product.active == True)
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    (Product.name.ilike(search_term)) |
                    (Product.code.ilike(search_term))
                )
            return query.limit(50).all()
        except Exception as e:
            logger.error(f"Erreur recherche produits: {e}")
            return []
    
    def get_all_products(self) -> List[Product]:
        try:
            return self.db_session.query(Product).filter(Product.active == True).order_by(Product.name).all()
        except Exception as e:
            logger.error(f"Erreur chargement produits: {e}")
            return []


# ============= DIALOGUES =============
class CustomerDialog(QDialog):
    """Dialogue de sélection/création de client"""
    
    customer_selected = Signal(object)
    
    def __init__(self, customer_service: CustomerService, parent=None):
        super().__init__(parent)
        self.customer_service = customer_service
        self.selected_customer = None
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("Gestion des clients")
        self.setModal(True)
        self.setMinimumSize(600, 450)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        self.tab_widget = QTabWidget()
        
        # Onglet sélection
        self.selection_tab = QWidget()
        self.setup_selection_tab()
        self.tab_widget.addTab(self.selection_tab, "Sélectionner")
        
        # Onglet création
        self.creation_tab = QWidget()
        self.setup_creation_tab()
        self.tab_widget.addTab(self.creation_tab, "Nouveau client")
        
        layout.addWidget(self.tab_widget)
        
        btn_layout = QHBoxLayout()
        self.select_btn = QPushButton("Sélectionner")
        self.select_btn.clicked.connect(self.select_customer)
        self.cancel_btn = QPushButton("Annuler")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.select_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)
        
        self.load_customers()
    
    def setup_selection_tab(self):
        layout = QVBoxLayout(self.selection_tab)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Rechercher...")
        self.search_input.textChanged.connect(self.filter_customers)
        layout.addWidget(self.search_input)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Nom", "Téléphone", "Email"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.doubleClicked.connect(self.on_double_click)
        layout.addWidget(self.table)
    
    def setup_creation_tab(self):
        layout = QVBoxLayout(self.creation_tab)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        
        self.first_name = QLineEdit()
        self.last_name = QLineEdit()
        self.company = QLineEdit()
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.address = QTextEdit()
        self.address.setMaximumHeight(80)
        
        form_layout.addRow("Prénom *:", self.first_name)
        form_layout.addRow("Nom *:", self.last_name)
        form_layout.addRow("Société:", self.company)
        form_layout.addRow("Téléphone:", self.phone)
        form_layout.addRow("Email:", self.email)
        form_layout.addRow("Adresse:", self.address)
        
        scroll.setWidget(form_widget)
        layout.addWidget(scroll)
        
        create_btn = QPushButton("Créer le client")
        create_btn.clicked.connect(self.create_customer)
        layout.addWidget(create_btn)
    
    def load_customers(self):
        self.filter_customers()
    
    def filter_customers(self):
        customers = self.customer_service.get_customers(self.search_input.text())
        self.display_customers(customers)
    
    def display_customers(self, customers: List[Customer]):
        self.table.setRowCount(len(customers))
        for row, c in enumerate(customers):
            self.table.setItem(row, 0, QTableWidgetItem(str(c.id)))
            self.table.setItem(row, 1, QTableWidgetItem(f"{c.first_name} {c.last_name}"))
            self.table.setItem(row, 2, QTableWidgetItem(c.phone or ""))
            self.table.setItem(row, 3, QTableWidgetItem(c.email or ""))
        self.table.resizeColumnsToContents()
    
    def get_selected(self) -> Optional[Customer]:
        selected = self.table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        customer_id = int(self.table.item(row, 0).text())
        return self.customer_service.db_session.query(Customer).get(customer_id)
    
    def on_double_click(self):
        self.select_customer()
    
    def select_customer(self):
        customer = self.get_selected()
        if customer:
            self.selected_customer = customer
            self.customer_selected.emit(customer)
            self.accept()
        else:
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un client")
    
    def create_customer(self):
        if not self.first_name.text().strip() or not self.last_name.text().strip():
            QMessageBox.warning(self, "Erreur", "Prénom et nom requis")
            return
        
        data = {
            "first_name": self.first_name.text().strip(),
            "last_name": self.last_name.text().strip(),
            "company": self.company.text().strip() or None,
            "phone": self.phone.text().strip() or None,
            "email": self.email.text().strip() or None,
            "address": self.address.toPlainText().strip() or None
        }
        
        success, customer, message = self.customer_service.create_customer(data)
        if success:
            QMessageBox.information(self, "Succès", message)
            self.selected_customer = customer
            self.customer_selected.emit(customer)
            self.accept()
        else:
            QMessageBox.critical(self, "Erreur", message)


# ============= WIDGET APERÇU =============
class ProformaPreviewWidget(QWidget):
    """Widget d'aperçu avec rendu A4"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_proforma = None
        self.settings_manager = SettingsManager()
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Barre d'outils compacte
        toolbar = QHBoxLayout()
        self.zoom_combo = QComboBox()
        for zoom in ["50%", "60%", "70%", "80%", "90%", "100%", "125%", "150%"]:
            self.zoom_combo.addItem(zoom)
        self.zoom_combo.setCurrentText("70%")  # Zoom par défaut réduit
        self.zoom_combo.currentTextChanged.connect(self.change_zoom)
        
        self.print_btn = QPushButton("🖨️ Imprimer")
        self.print_btn.clicked.connect(self.print_preview)
        self.print_btn.setMaximumHeight(30)
        
        self.page_size_label = QLabel("📄 Format: A4")
        self.page_size_label.setStyleSheet("color: #6b7280; font-size: 9px;")
        
        toolbar.addWidget(QLabel("Zoom:"))
        toolbar.addWidget(self.zoom_combo)
        toolbar.addStretch()
        toolbar.addWidget(self.page_size_label)
        toolbar.addWidget(self.print_btn)
        layout.addLayout(toolbar)
        
        # Zone d'aperçu avec fond gris pour simuler le papier
        preview_container = QWidget()
        preview_container.setStyleSheet("background-color: #e5e7eb; padding: 10px;")
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setAlignment(Qt.AlignCenter)
        preview_layout.setContentsMargins(5, 5, 5, 5)
        
        # Widget qui simule la page A4 - taille réduite pour l'écran
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #9ca3af;
                border-radius: 3px;
                padding: 10px;
            }
        """)
        # Taille réduite (environ 55% de A4)
        self.preview.setMinimumSize(500, 700)
        self.preview.setMaximumSize(500, 700)
        
        preview_layout.addWidget(self.preview)
        
        layout.addWidget(preview_container)
    
    def number_to_french_words(self, n: int) -> str:
        """Convertit un nombre en lettres (français)"""
        if n == 0:
            return "ZÉRO"
        
        units = ["", "UN", "DEUX", "TROIS", "QUATRE", "CINQ", "SIX", "SEPT", "HUIT", "NEUF", "DIX", 
                 "ONZE", "DOUZE", "TREIZE", "QUATORZE", "QUINZE", "SEIZE", "DIX-SEPT", "DIX-HUIT", "DIX-NEUF"]
        tens = ["", "DIX", "VINGT", "TRENTE", "QUARANTE", "CINQUANTE", "SOIXANTE", "SOIXANTE-DIX", "QUATRE-VINGT", "QUATRE-VINGT-DIX"]
        
        def convert_hundreds(num):
            if num == 0:
                return ""
            if num < 20:
                return units[num]
            if num < 100:
                if num < 70:
                    return tens[num // 10] + ("-" + units[num % 10] if num % 10 else "")
                elif num < 80:
                    return "SOIXANTE" + ("-DIX" if num % 10 == 0 else "-" + units[10 + num % 10])
                elif num < 90:
                    return "QUATRE-VINGT" + ("S" if num == 80 else "")
                else:
                    return "QUATRE-VINGT-DIX" + ("-" + units[num % 10] if num % 10 else "")
            if num == 100:
                return "CENT"
            return ("CENT" if num // 100 == 1 else units[num // 100] + "-CENT") + ("" if num % 100 == 0 else "-" + convert_hundreds(num % 100))
        
        if n < 1000:
            return convert_hundreds(n)
        
        result = []
        if n >= 1000000:
            millions = n // 1000000
            n %= 1000000
            if millions == 1:
                result.append("UN MILLION")
            else:
                result.append(convert_hundreds(millions) + " MILLIONS")
        
        if n >= 1000:
            thousands = n // 1000
            n %= 1000
            if thousands == 1:
                result.append("MILLE")
            else:
                result.append(convert_hundreds(thousands) + " MILLE")
        
        if n > 0:
            result.append(convert_hundreds(n))
        
        return " ".join(result)
    
    def generate_html(self, proforma: ProformaInvoice) -> str:
        """Génère une facture proforma format A4 avec filigrane et mentions comptables"""
        company_info = self.settings_manager.get_company_info_for_invoice()

        logo_path = company_info.get("company_logo", "")
        logo_html = f'<img src="{logo_path}" style="height:80px;">' if logo_path else '<div style="font-size:48px;font-weight:bold;color:#1a5490;">LOGO</div>'

        date_str = proforma.created_date.strftime("%d/%m/%Y")

        customer_name = proforma.customer.full_name if proforma.customer else "Client"
        customer_address = ""
        customer_phone = ""
        customer_email = ""
        if proforma.customer:
            customer_address = getattr(proforma.customer, "address", "") or ""
            customer_phone = getattr(proforma.customer, "phone", "") or ""
            customer_email = getattr(proforma.customer, "email", "") or ""

        subject = proforma.terms_and_conditions or ""

        total_general = 0
        items_html = ""

        for idx, item in enumerate(proforma.items, start=1):
            total_general += item.line_total
            items_html += f"""
            <tr>
                <td style="font-size:10pt;padding:6px 4px;text-align:center;">{idx}</td>
                <td style="font-size:10pt;padding:6px 4px;">{item.description}</td>
                <td style="font-size:10pt;padding:6px 4px;text-align:center;">{int(item.quantity)}</td>
                <td style="font-size:10pt;padding:6px 4px;text-align:right;">{item.unit_price:,.0f}</td>
                <td style="font-size:10pt;padding:6px 4px;text-align:right;">{item.line_total:,.0f}</td>
            </tr>
            """

        # Conversion du total en lettres
        total_letters = self.number_to_french_words(int(total_general))

        return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
    @page {{
        size: A4;
        margin: 15mm 15mm 15mm 15mm;
    }}
    body {{
        font-family: 'Times New Roman', Times, serif;
        font-size: 10pt;
        margin: 0;
        padding: 0;
        color: #1a1a1a;
        line-height: 1.4;
    }}
    .header-table {{
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 15px;
    }}
    .header-table td {{
        padding: 5px 0;
        vertical-align: top;
    }}
    .title {{
        font-size: 18pt;
        font-weight: bold;
        text-decoration: underline;
        color: #1a5490;
    }}
    .company-name {{
        font-size: 22pt;
        font-weight: bold;
        color: #1a5490;
    }}
    .info-block {{
        margin-bottom: 10px;
        padding: 8px 0;
    }}
    .info-block b {{
        font-weight: 600;
    }}
    .main-table {{
        width: 100%;
        border-collapse: collapse;
        margin: 15px 0;
    }}
    .main-table th {{
        background-color: #f3f4f6;
        font-weight: bold;
        font-size: 9pt;
        text-align: center;
        border: 1px solid #000;
        padding: 6px 4px;
        text-transform: uppercase;
    }}
    .main-table td {{
        border: 1px solid #000;
        padding: 5px 4px;
        font-size: 10pt;
    }}
    .main-table tr:nth-child(even) {{
        background-color: #fafafa;
    }}
    .total-row td {{
        border: none;
        padding: 8px 4px;
    }}
    .total-amount {{
        font-size: 14pt;
        font-weight: bold;
        color: #1a5490;
    }}
    .total-label {{
        font-size: 11pt;
        font-weight: bold;
    }}
    .signature-block {{
        margin-top: 40px;
        text-align: right;
    }}
    .signature-line {{
        margin-top: 30px;
        padding-top: 10px;
        border-top: 1px solid #000;
        display: inline-block;
        min-width: 200px;
    }}
    .footer {{
        margin-top: 30px;
        font-size: 9pt;
        color: #6b7280;
        text-align: center;
        border-top: 1px solid #e5e7eb;
        padding-top: 15px;
    }}
    .letters {{
        font-size: 10pt;
        font-style: italic;
        margin: 10px 0;
        padding: 8px;
        background-color: #f9fafb;
        border-left: 3px solid #1a5490;
    }}
    .watermark {{
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%) rotate(-45deg);
        font-size: 72pt;
        font-weight: bold;
        color: rgba(239, 68, 68, 0.15);
        border: 8px solid rgba(239, 68, 68, 0.3);
        padding: 20px 60px;
        z-index: 1000;
        pointer-events: none;
    }}
    .no-accounting {{
        background-color: #fef3c7;
        border: 2px solid #f59e0b;
        padding: 10px;
        text-align: center;
        font-weight: bold;
        color: #92400e;
        margin: 15px 0;
    }}
    .customer-info {{
        margin: 8px 0;
        font-size: 10pt;
    }}
    .customer-info .label {{
        font-weight: 600;
        color: #4b5563;
    }}
</style>
</head>
<body>

<!-- Filigrane PRO FORMA -->
<div class="watermark">PRO FORMA</div>

<!-- En-tête -->
<table class="header-table">
<tr>
    <td width="45%">
        <div class="company-name">{company_info.get("name", "MON ENTREPRISE")}</div>
        <div style="font-size:8pt;color:#4b5563;">
            {company_info.get("address", "Ouagadougou")}<br>
            Tél: {company_info.get("phone", "+226 XX XX XX XX")}<br>
            Email: {company_info.get("email", "contact@entreprise.com")}
        </div>
    </td>
    <td width="55%" style="text-align:right;">
        <div style="font-size:10pt;color:#4b5563;">Ouagadougou, le {date_str}</div>
        <br>
        <div class="title">FACTURE PRO FORMA</div>
        <div style="font-size:12pt;font-weight:bold;color:#1a5490;margin-top:5px;">
            N° {proforma.proforma_number}
        </div>
    </td>
</tr>
</table>

<!-- Mention document sans valeur comptable -->
<div class="no-accounting">
    ⚠️ DOCUMENT SANS VALEUR COMPTABLE - Ce document ne peut être utilisé pour des déclarations fiscales
</div>

<!-- Informations client -->
<div class="info-block">
    <table style="width:100%;">
        <tr>
            <td style="width:50%;vertical-align:top;">
                <b><u>DOIT :</u></b><br>
                <span style="font-size:11pt;font-weight:bold;">{customer_name}</span><br>
                <span style="font-size:9pt;color:#4b5563;">{customer_address}</span>
            </td>
            <td style="width:50%;vertical-align:top;text-align:right;">
                <span style="font-size:9pt;color:#4b5563;">
                    {f"Tél: {customer_phone}" if customer_phone else ""}<br>
                    {f"Email: {customer_email}" if customer_email else ""}
                </span>
            </td>
        </tr>
    </table>
</div>

<!-- Objet -->
<div class="info-block">
    <b><u>Objet :</u></b> <span style="font-size:10pt;">{subject}</span>
</div>

<!-- Tableau des articles -->
<table class="main-table">
    <thead>
        <tr>
            <th style="width:8%;">N°</th>
            <th style="width:52%;">DÉSIGNATION</th>
            <th style="width:10%;">QTÉ</th>
            <th style="width:15%;">PRIX UNIT.</th>
            <th style="width:15%;">TOTAL</th>
        </tr>
    </thead>
    <tbody>
        {items_html}
    </tbody>
    <tfoot>
        <tr>
            <td colspan="4" style="border:none;padding:10px 4px;text-align:right;">
                <span class="total-label">Total net :</span>
            </td>
            <td style="border:none;padding:10px 4px;text-align:right;font-weight:bold;font-size:12pt;">
                {total_general:,.0f} FCFA
            </td>
        </tr>
    </tfoot>
</table>

<!-- Montant en lettres -->
<div class="letters">
    <b>Arrêté à la somme de :</b> {total_letters} ({total_general:,.0f}) francs CFA
</div>

<!-- Signature -->
<div class="signature-block">
    <div style="font-size:10pt;font-weight:bold;">Le Gérant</div>
    <div class="signature-line">
        <span style="font-size:10pt;">TIENDREBEOGO François</span>
    </div>
</div>

<!-- Pied de page -->
<div class="footer">
    {ProformaConfig.DEFAULTS.get("footer_text", "Merci de votre confiance")}
</div>

</body>
</html>
"""

    def display_proforma(self, proforma: ProformaInvoice):
        self.current_proforma = proforma
        html = self.generate_html(proforma)
        self.preview.setHtml(html)
        self.preview.setStyleSheet("font-size: 10pt; line-height: 1.4;")
    
    def change_zoom(self, value: str):
        """Change le zoom de l'aperçu"""
        zoom = int(value.replace("%", ""))
        # Taille de base réduite
        base_width = 500
        base_height = 700
        new_width = int(base_width * zoom / 100)
        new_height = int(base_height * zoom / 100)
        
        # Limiter la taille maximale
        max_width = 700
        max_height = 980
        new_width = min(new_width, max_width)
        new_height = min(new_height, max_height)
        
        self.preview.setMinimumSize(new_width, new_height)
        self.preview.setMaximumSize(new_width, new_height)
        
        # Ajuster la taille de police pour le zoom
        font_size = int(10 * zoom / 100)
        self.preview.setStyleSheet(f"""
            QTextEdit {{
                background-color: white;
                border: 1px solid #9ca3af;
                border-radius: 3px;
                padding: 10px;
                font-size: {max(7, font_size)}pt;
            }}
        """)
        # Recharger le contenu pour appliquer le zoom
        if self.current_proforma:
            self.preview.setHtml(self.generate_html(self.current_proforma))
    
    def print_preview(self):
        if not self.current_proforma:
            QMessageBox.warning(self, "Erreur", "Aucune proforma à imprimer")
            return
        
        printer = QPrinter(QPrinter.HighResolution)
        from PySide6.QtGui import QPageSize
        page_size = QPageSize(QPageSize.A4)
        printer.setPageSize(page_size)
        printer.setFullPage(False)
        
        preview = QPrintPreviewDialog(printer, self)
        preview.paintRequested.connect(self.print_document)
        preview.exec()
    
    def print_document(self, printer: QPrinter):
        """Imprime le document en A4"""
        document = QTextDocument()
        document.setDocumentMargin(0)
        html = self.generate_html(self.current_proforma)
        document.setHtml(html)
        
        from PySide6.QtGui import QFont
        font = QFont("Times New Roman", 10)
        document.setDefaultFont(font)
        
        document.print_(printer)


# ============= WIDGET PRODUITS =============
class ProductsWidget(QWidget):
    """Widget dédié à la sélection et gestion des produits"""
    
    product_added = Signal(dict)
    
    def __init__(self, product_service: ProductService, parent=None):
        super().__init__(parent)
        self.product_service = product_service
        self.current_page = 1
        self.all_products = []
        self.filtered_products = []
        self.products_per_page = 20
        self.setup_ui()
        self.load_products()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Barre de recherche
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Rechercher un produit par nom ou code...")
        self.search_input.setMinimumHeight(30)
        self.search_input.textChanged.connect(self.filter_products)
        search_layout.addWidget(self.search_input, 1)
        
        self.search_btn = QPushButton("Rechercher")
        self.search_btn.clicked.connect(self.filter_products)
        search_layout.addWidget(self.search_btn)
        
        # Bouton rafraîchir
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setFixedSize(30, 30)
        self.refresh_btn.setToolTip("Rafraîchir la liste")
        self.refresh_btn.clicked.connect(self.refresh)
        search_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(search_layout)
        
        # Liste des produits
        self.products_list = QTableWidget()
        self.products_list.setColumnCount(4)
        self.products_list.setHorizontalHeaderLabels(["Code", "Nom", "Prix", "Stock"])
        self.products_list.setColumnWidth(0, 80)
        self.products_list.setColumnWidth(1, 280)
        self.products_list.setColumnWidth(2, 90)
        self.products_list.setColumnWidth(3, 70)
        self.products_list.setSelectionBehavior(QTableWidget.SelectRows)
        self.products_list.setAlternatingRowColors(True)
        
        # Connecter le double-clic pour ajouter
        self.products_list.doubleClicked.connect(self.add_selected_product)
        self.products_list.setToolTip("Double-cliquer sur un produit pour l'ajouter au panier")
        
        layout.addWidget(self.products_list)
        
        # Pagination
        pagination_layout = QHBoxLayout()
        self.prev_btn = QPushButton("◀ Précédent")
        self.prev_btn.clicked.connect(self.previous_page)
        self.next_btn = QPushButton("Suivant ▶")
        self.next_btn.clicked.connect(self.next_page)
        self.page_label = QLabel("Page 1/1")
        self.page_label.setAlignment(Qt.AlignCenter)
        
        pagination_layout.addWidget(self.prev_btn)
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.next_btn)
        layout.addLayout(pagination_layout)
        
        # Info stock faible et indication double-clic
        info_layout = QHBoxLayout()
        self.stock_info = QLabel("")
        self.stock_info.setStyleSheet("color: #f59e0b; font-size: 10px;")
        
        self.double_click_info = QLabel("💡 Double-cliquez pour ajouter")
        self.double_click_info.setStyleSheet("color: #6b7280; font-size: 10px; font-style: italic;")
        
        info_layout.addWidget(self.stock_info)
        info_layout.addStretch()
        info_layout.addWidget(self.double_click_info)
        layout.addLayout(info_layout)
    
    def load_products(self):
        self.all_products = self.product_service.get_all_products()
        self.filtered_products = self.all_products.copy()
        self.current_page = 1
        self.display_products()
        self.update_stock_info()
    
    def filter_products(self):
        search = self.search_input.text().lower()
        if search:
            self.filtered_products = [p for p in self.all_products 
                                      if search in p.name.lower() or 
                                      (p.code and search in p.code.lower())]
        else:
            self.filtered_products = self.all_products.copy()
        self.current_page = 1
        self.display_products()
    
    def display_products(self):
        start = (self.current_page - 1) * self.products_per_page
        end = start + self.products_per_page
        page_products = self.filtered_products[start:end]
        
        self.products_list.setRowCount(len(page_products))
        self.products_list.setUpdatesEnabled(False)
        
        for row, product in enumerate(page_products):
            # Code
            code_item = QTableWidgetItem(product.code or "")
            code_item.setData(Qt.UserRole, product.id)
            self.products_list.setItem(row, 0, code_item)
            
            # Nom
            name_item = QTableWidgetItem(product.name)
            self.products_list.setItem(row, 1, name_item)
            
            # Prix
            price_item = QTableWidgetItem(f"{product.sale_price:,.0f}")
            price_item.setTextAlignment(Qt.AlignRight)
            self.products_list.setItem(row, 2, price_item)
            
            # Stock
            stock_text = f"{int(product.quantity)}"
            stock_item = QTableWidgetItem(stock_text)
            stock_item.setTextAlignment(Qt.AlignCenter)
            if product.quantity <= 0:
                stock_item.setForeground(QColor("#ef4444"))
                stock_item.setToolTip("Rupture de stock - Impossible d'ajouter")
                for col in range(4):
                    item = self.products_list.item(row, col)
                    if item:
                        item.setForeground(QColor("#9ca3af"))
            elif product.quantity <= product.min_stock:
                stock_item.setForeground(QColor("#f59e0b"))
                stock_item.setToolTip(f"Stock bas (min: {product.min_stock})")
            else:
                stock_item.setForeground(QColor("#10b981"))
                stock_item.setToolTip("Stock OK")
            self.products_list.setItem(row, 3, stock_item)
        
        self.products_list.setUpdatesEnabled(True)
        
        # Mettre à jour la pagination
        total_pages = max(1, (len(self.filtered_products) + self.products_per_page - 1) // self.products_per_page)
        self.page_label.setText(f"Page {self.current_page}/{total_pages}")
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < total_pages)
    
    def update_stock_info(self):
        low_stock_count = len([p for p in self.all_products if 0 < p.quantity <= p.min_stock])
        out_stock_count = len([p for p in self.all_products if p.quantity <= 0])
        
        if out_stock_count > 0:
            self.stock_info.setText(f"⚠️ {out_stock_count} ruptures, {low_stock_count} bas")
            self.stock_info.setStyleSheet("color: #ef4444; font-size: 10px;")
        elif low_stock_count > 0:
            self.stock_info.setText(f"⚠️ {low_stock_count} produit(s) en stock bas")
            self.stock_info.setStyleSheet("color: #f59e0b; font-size: 10px;")
        else:
            self.stock_info.setText("✅ Stock OK")
            self.stock_info.setStyleSheet("color: #10b981; font-size: 10px;")
    
    def add_product(self, product: Product):
        """Ajoute un produit avec demande de quantité"""
        if product.quantity <= 0:
            QMessageBox.warning(self, "Stock insuffisant", 
                               f"Le produit {product.name} est en rupture de stock et ne peut pas être ajouté")
            return
        
        max_qty = int(product.quantity)
        quantity, ok = QInputDialog.getInt(
            self, 
            "Ajouter au panier", 
            f"Produit: {product.name}\nPrix unitaire: {product.sale_price:,.0f} FCFA\nStock disponible: {max_qty}\n\nQuantité:",
            1, 1, max_qty, 1
        )
        
        if ok and quantity > 0:
            item_data = {
                "product_id": product.id,
                "product_name": product.name,
                "description": product.name,
                "quantity": quantity,
                "unit_price": product.sale_price,
                "discount_percent": 0
            }
            self.product_added.emit(item_data)
            self.show_temp_message(f"✓ {product.name} x{quantity} ajouté")
    
    def show_temp_message(self, message: str):
        """Affiche un message temporaire"""
        original_text = self.stock_info.text()
        original_style = self.stock_info.styleSheet()
        self.stock_info.setText(message)
        self.stock_info.setStyleSheet("color: #10b981; font-size: 10px; font-weight: bold;")
        QTimer.singleShot(2000, lambda: self.restore_stock_info(original_text, original_style))
    
    def restore_stock_info(self, original_text: str, original_style: str):
        """Restaure l'information de stock"""
        self.stock_info.setText(original_text)
        self.stock_info.setStyleSheet(original_style)
    
    def add_selected_product(self):
        """Ajoute le produit sélectionné (appelé par double-clic)"""
        selected = self.products_list.selectedItems()
        if not selected:
            QMessageBox.information(self, "Information", "Veuillez sélectionner un produit")
            return
        
        row = selected[0].row()
        product_id = self.products_list.item(row, 0).data(Qt.UserRole)
        
        if product_id:
            product = self.product_service.db_session.query(Product).get(product_id)
            if product:
                self.add_product(product)
            else:
                QMessageBox.warning(self, "Erreur", "Produit non trouvé")
    
    def previous_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.display_products()
    
    def next_page(self):
        total_pages = max(1, (len(self.filtered_products) + self.products_per_page - 1) // self.products_per_page)
        if self.current_page < total_pages:
            self.current_page += 1
            self.display_products()
    
    def refresh(self):
        self.load_products()


# ============= WIDGET PANIER =============
class CartWidget(QWidget):
    """Widget dédié au panier d'articles"""
    
    cart_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # En-tête
        header_layout = QHBoxLayout()
        title = QLabel("🛒 Panier")
        title.setStyleSheet("font-size: 13px; font-weight: bold;")
        self.count_label = QLabel("0 article")
        self.count_label.setStyleSheet("color: #6b7280; background-color: #f3f4f6; padding: 2px 8px; border-radius: 10px; font-size: 10px;")
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.count_label)
        layout.addLayout(header_layout)
        
        # Tableau
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Produit", "Désignation", "Qté", "Prix U.", "Remise %", "Total"])
        self.table.setColumnWidth(0, 100)
        self.table.setColumnWidth(1, 200)
        self.table.setColumnWidth(2, 60)
        self.table.setColumnWidth(3, 80)
        self.table.setColumnWidth(4, 60)
        self.table.setColumnWidth(5, 100)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        
        # Boutons gestion
        btn_layout = QHBoxLayout()
        self.modify_btn = QPushButton("✏️ Quantité")
        self.modify_btn.clicked.connect(self.modify_quantity)
        self.remove_btn = QPushButton("🗑️ Supprimer")
        self.remove_btn.clicked.connect(self.remove_selected)
        self.clear_btn = QPushButton("🧹 Vider")
        self.clear_btn.clicked.connect(self.clear_all)
        
        btn_layout.addWidget(self.modify_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # Indication
        info_label = QLabel("💡 Sélectionnez une ligne puis Modifier pour changer la quantité")
        info_label.setStyleSheet("color: #6b7280; font-size: 9px; font-style: italic;")
        layout.addWidget(info_label)
    
    def update_display(self):
        self.table.setRowCount(len(self.items))
        
        for row, item in enumerate(self.items):
            # Produit
            self.table.setItem(row, 0, QTableWidgetItem(item.get("product_name", "")))
            
            # Désignation
            self.table.setItem(row, 1, QTableWidgetItem(item.get("description", "")))
            
            # Qté
            qty_item = QTableWidgetItem(str(item.get("quantity", 1)))
            qty_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, qty_item)
            
            # Prix U.
            price_item = QTableWidgetItem(f"{item.get('unit_price', 0):,.0f}")
            price_item.setTextAlignment(Qt.AlignRight)
            self.table.setItem(row, 3, price_item)
            
            # Remise
            discount_item = QTableWidgetItem(f"{item.get('discount_percent', 0)}%")
            discount_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, discount_item)
            
            # Total
            line_total = item.get('quantity', 1) * item.get('unit_price', 0) * (1 - item.get('discount_percent', 0) / 100)
            total_item = QTableWidgetItem(f"{line_total:,.0f}")
            total_item.setTextAlignment(Qt.AlignRight)
            total_item.setForeground(QColor("#1a5490"))
            self.table.setItem(row, 5, total_item)
        
        self.count_label.setText(f"{len(self.items)} article(s)")
        self.cart_changed.emit()
    
    def add_item(self, item: dict):
        # Vérifier si le produit existe déjà
        for existing in self.items:
            if existing.get("product_id") == item.get("product_id") and existing.get("product_id") is not None:
                reply = QMessageBox.question(self, "Produit existant", 
                                            f"{item.get('product_name')} est déjà dans le panier.\nVoulez-vous cumuler les quantités ?",
                                            QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    existing["quantity"] += item.get("quantity", 1)
                    self.update_display()
                return
        
        self.items.append(item)
        self.update_display()
    
    def modify_quantity(self):
        selected = self.table.selectedItems()
        if selected:
            row = selected[0].row()
            if 0 <= row < len(self.items):
                current_qty = self.items[row].get("quantity", 1)
                new_qty, ok = QInputDialog.getInt(
                    self, "Modifier quantité", 
                    f"Nouvelle quantité pour {self.items[row].get('product_name', '')}:",
                    current_qty, 1, 9999, 1
                )
                if ok and new_qty > 0:
                    self.items[row]["quantity"] = new_qty
                    self.update_display()
    
    def remove_selected(self):
        selected = self.table.selectedItems()
        if selected:
            row = selected[0].row()
            if 0 <= row < len(self.items):
                self.items.pop(row)
                self.update_display()
    
    def clear_all(self):
        if self.items:
            reply = QMessageBox.question(self, "Confirmation", 
                                        "Vider tous les articles ?",
                                        QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.items.clear()
                self.update_display()
    
    def get_items(self) -> List[Dict]:
        return self.items
    
    def set_items(self, items: List[Dict]):
        self.items = items.copy()
        self.update_display()


# ============= WIDGET INFORMATIONS PROFORMA =============
class ProformaInfoWidget(QWidget):
    """Widget pour les informations générales de la proforma"""
    
    info_changed = Signal()
    
    def __init__(self, customer_service: CustomerService, parent=None):
        super().__init__(parent)
        self.customer_service = customer_service
        self.selected_customer = None
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Section Client
        client_group = QGroupBox("Informations client")
        client_layout = QVBoxLayout(client_group)
        client_layout.setSpacing(8)
        
        # Sélection client
        select_layout = QHBoxLayout()
        self.customer_combo = QComboBox()
        self.customer_combo.setMinimumHeight(30)
        self.customer_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        self.select_customer_btn = QPushButton("Sélectionner/Créer")
        self.select_customer_btn.clicked.connect(self.open_customer_dialog)
        
        select_layout.addWidget(QLabel("Client:"))
        select_layout.addWidget(self.customer_combo, 1)
        select_layout.addWidget(self.select_customer_btn)
        client_layout.addLayout(select_layout)
        
        # Info client
        self.client_info = QLabel("Aucun client sélectionné")
        self.client_info.setStyleSheet("color: #6b7280; padding: 4px; background-color: #f9fafb; border-radius: 4px; font-size: 10px;")
        self.client_info.setWordWrap(True)
        client_layout.addWidget(self.client_info)
        
        layout.addWidget(client_group)
        
        # Section Informations facture
        info_group = QGroupBox("Informations facture")
        info_layout = QGridLayout(info_group)
        info_layout.setSpacing(8)
        
        # Numéro
        info_layout.addWidget(QLabel("N° Proforma:"), 0, 0)
        self.number_label = QLabel("")
        self.number_label.setStyleSheet("font-weight: bold; color: #1a5490;")
        info_layout.addWidget(self.number_label, 0, 1)
        
        # Date
        info_layout.addWidget(QLabel("Date:"), 0, 2)
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setMaximumWidth(120)
        info_layout.addWidget(self.date_edit, 0, 3)
        
        # Validité
        info_layout.addWidget(QLabel("Valide jusqu'au:"), 1, 2)
        self.valid_until = QDateEdit()
        self.valid_until.setDate(QDate.currentDate().addDays(30))
        self.valid_until.setCalendarPopup(True)
        self.valid_until.setMaximumWidth(120)
        info_layout.addWidget(self.valid_until, 1, 3)
        
        # Objet
        info_layout.addWidget(QLabel("Objet:"), 1, 0)
        self.subject = QLineEdit()
        self.subject.setPlaceholderText("Ex: Achat et réparation de moto")
        info_layout.addWidget(self.subject, 1, 1)
        
        layout.addWidget(info_group)
        
        # Section Totaux
        totals_group = QGroupBox("Totaux")
        totals_layout = QGridLayout(totals_group)
        totals_layout.setSpacing(8)
        
        # TVA
        totals_layout.addWidget(QLabel("TVA (%):"), 0, 0)
        self.tax_input = QLineEdit("18")
        self.tax_input.setMaximumWidth(70)
        self.tax_input.textChanged.connect(self.info_changed.emit)
        totals_layout.addWidget(self.tax_input, 0, 1)
        
        # Remise
        totals_layout.addWidget(QLabel("Remise (%):"), 0, 2)
        self.discount_input = QLineEdit("0")
        self.discount_input.setMaximumWidth(70)
        self.discount_input.textChanged.connect(self.info_changed.emit)
        totals_layout.addWidget(self.discount_input, 0, 3)
        
        # Total
        totals_layout.addWidget(QLabel("Total TTC:"), 1, 2)
        self.total_label = QLabel("0 FCFA")
        self.total_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #1a5490;")
        self.total_label.setAlignment(Qt.AlignRight)
        totals_layout.addWidget(self.total_label, 1, 3)
        
        layout.addWidget(totals_group)
        
        # Section Notes
        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout(notes_group)
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        notes_layout.addWidget(self.notes)
        layout.addWidget(notes_group)
    
    def load_customers(self):
        self.customer_combo.clear()
        self.customer_combo.addItem("-- Sélectionner --", None)
        
        for customer in self.customer_service.get_customers():
            name = f"{customer.first_name} {customer.last_name}"
            if customer.company:
                name += f" ({customer.company})"
            self.customer_combo.addItem(name, customer.id)
    
    def open_customer_dialog(self):
        dialog = CustomerDialog(self.customer_service, self)
        dialog.customer_selected.connect(self.on_customer_selected)
        dialog.exec()
    
    def on_customer_selected(self, customer: Customer):
        self.selected_customer = customer
        index = self.customer_combo.findData(customer.id)
        if index >= 0:
            self.customer_combo.setCurrentIndex(index)
        else:
            name = f"{customer.first_name} {customer.last_name}"
            if customer.company:
                name += f" ({customer.company})"
            self.customer_combo.addItem(name, customer.id)
            self.customer_combo.setCurrentIndex(self.customer_combo.count() - 1)
        
        info_text = f"{customer.first_name} {customer.last_name}"
        if customer.company:
            info_text += f" - {customer.company}"
        if customer.phone:
            info_text += f" | Tél: {customer.phone}"
        if customer.email:
            info_text += f" | Email: {customer.email}"
        self.client_info.setText(info_text)
        self.client_info.setStyleSheet("color: #059669; padding: 4px; background-color: #ecfdf5; border-radius: 4px; font-size: 10px;")
    
    def set_proforma_number(self, number: str):
        self.number_label.setText(number)
    
    def get_customer_id(self) -> Optional[int]:
        return self.customer_combo.currentData()
    
    def get_info_data(self) -> Dict:
        return {
            "customer_id": self.get_customer_id(),
            "subject": self.subject.text(),
            "notes": self.notes.toPlainText(),
            "tax_percent": float(self.tax_input.text() or 18),
            "discount_percent": float(self.discount_input.text() or 0),
            "valid_until": self.valid_until.date().toPython()
        }
    
    def set_info_data(self, data: Dict):
        if data.get("customer_id"):
            index = self.customer_combo.findData(data["customer_id"])
            if index >= 0:
                self.customer_combo.setCurrentIndex(index)
        self.subject.setText(data.get("subject", ""))
        self.notes.setText(data.get("notes", ""))
        self.tax_input.setText(str(data.get("tax_percent", 18)))
        self.discount_input.setText(str(data.get("discount_percent", 0)))
        if data.get("valid_until"):
            self.valid_until.setDate(data["valid_until"].date())
    
    def update_totals(self, total: float):
        self.total_label.setText(f"{total:,.0f} FCFA")


# ============= DIALOGUE PRINCIPAL =============
class ProformaDialog(QDialog):
    """Dialogue principal avec onglets séparés"""
    
    def __init__(self, user_id: int = None, proforma_id: int = None, parent=None):
        super().__init__(parent)
        self.user_id = user_id
        self.proforma_id = proforma_id
        self.session = SessionLocal()
        self.proforma_service = ProformaService(self.session)
        self.customer_service = CustomerService(self.session)
        self.product_service = ProductService(self.session)
        
        self.setup_ui()
        self.setup_connections()
        
        if proforma_id:
            self.load_proforma(proforma_id)
        else:
            self.generate_number()
        
        self.load_initial_data()
    
    def setup_ui(self):
        self.setWindowTitle("Facture Proforma")
        
        # Récupérer la taille de l'écran
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            max_height = screen_geometry.height() - 80
            max_width = screen_geometry.width() - 80
        else:
            max_height = 700
            max_width = 1200
        
        # Définir une taille adaptée (70% de l'écran)
        width = min(1300, max_width)
        height = min(750, max_height)
        self.resize(width, height)
        
        # Permettre le redimensionnement avec des limites minimales
        self.setMinimumSize(900, 550)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Layout principal
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)
        
        # Barre d'outils
        toolbar = QHBoxLayout()
        self.save_btn = QPushButton("💾 Enregistrer")
        self.save_btn.setMinimumHeight(32)
        self.save_btn.setStyleSheet("background-color: #1a5490; color: white; font-weight: bold; border-radius: 6px; padding: 6px 16px;")
        self.print_btn = QPushButton("🖨️ Imprimer")
        self.print_btn.setMinimumHeight(32)
        self.print_btn.setEnabled(False)
        self.print_btn.setStyleSheet("padding: 6px 16px;")
        
        toolbar.addWidget(self.save_btn)
        toolbar.addWidget(self.print_btn)
        toolbar.addStretch()
        main_layout.addLayout(toolbar)
        
        # Onglets principaux
        self.tab_widget = QTabWidget()
        self.tab_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Onglet 1: Produits
        self.products_tab = QWidget()
        self.setup_products_tab()
        self.tab_widget.addTab(self.products_tab, "📦 Produits")
        
        # Onglet 2: Informations
        self.info_widget = ProformaInfoWidget(self.customer_service)
        self.tab_widget.addTab(self.info_widget, "ℹ️ Informations")
        
        # Onglet 3: Aperçu
        self.preview_widget = ProformaPreviewWidget()
        self.tab_widget.addTab(self.preview_widget, "👁️ Aperçu")
        
        main_layout.addWidget(self.tab_widget)
        
        # Boutons
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self.save)
        btn_box.rejected.connect(self.reject)
        main_layout.addWidget(btn_box)
        
        # Ajuster la taille de l'aperçu en fonction de la taille de la fenêtre
        QTimer.singleShot(100, self.adjust_preview_size)
        
        self.apply_styles()
    
    def adjust_preview_size(self):
        """Ajuste la taille de l'aperçu en fonction de la taille de la fenêtre"""
        # Récupérer la hauteur disponible pour l'aperçu
        tab_height = self.tab_widget.height()
        if tab_height > 0:
            # L'aperçu prend environ 65% de la hauteur des onglets
            preview_height = int(tab_height * 0.65)
            preview_width = int(preview_height * 0.707)  # Ratio A4 (1/√2)
            
            # Limiter les dimensions
            max_width = 700
            max_height = 990
            min_width = 400
            min_height = 560
            
            preview_width = max(min_width, min(preview_width, max_width))
            preview_height = max(min_height, min(preview_height, max_height))
            
            # Appliquer à l'aperçu si accessible
            if hasattr(self, 'preview_widget') and self.preview_widget:
                preview = self.preview_widget.preview
                if preview:
                    preview.setMinimumSize(preview_width, preview_height)
                    preview.setMaximumSize(preview_width, preview_height)
    
    def resizeEvent(self, event):
        """Appelé quand la fenêtre est redimensionnée"""
        super().resizeEvent(event)
        # Réajuster la taille de l'aperçu après un délai
        QTimer.singleShot(50, self.adjust_preview_size)
    
    def setup_products_tab(self):
        """Onglet dédié aux produits"""
        layout = QVBoxLayout(self.products_tab)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Splitter pour séparer liste produits et panier
        splitter = QSplitter(Qt.Horizontal)
        
        # Widget produits (gauche)
        self.products_widget = ProductsWidget(self.product_service)
        splitter.addWidget(self.products_widget)
        
        # Widget panier (droite)
        self.cart_widget = CartWidget()
        splitter.addWidget(self.cart_widget)
        
        # Proportions avec des tailles adaptées
        splitter.setSizes([550, 450])
        
        layout.addWidget(splitter)
    
    def setup_connections(self):
        self.products_widget.product_added.connect(self.cart_widget.add_item)
        self.cart_widget.cart_changed.connect(self.calculate_totals)
        self.info_widget.info_changed.connect(self.calculate_totals)
        self.save_btn.clicked.connect(self.save)
        self.print_btn.clicked.connect(self.print_proforma)
    
    def load_initial_data(self):
        self.info_widget.load_customers()
    
    def generate_number(self):
        number = self.proforma_service.generate_proforma_number()
        self.info_widget.set_proforma_number(number)
    
    def calculate_totals(self):
        items = self.cart_widget.get_items()
        
        if not items:
            self.info_widget.update_totals(0)
            return
        
        subtotal = 0
        for item in items:
            line_total = item.get("quantity", 1) * item.get("unit_price", 0) * (1 - item.get("discount_percent", 0) / 100)
            subtotal += line_total
        
        # Remise globale
        discount_pct = self.info_widget.get_info_data().get("discount_percent", 0)
        after_discount = subtotal * (1 - discount_pct / 100)
        
        # TVA
        tax_pct = self.info_widget.get_info_data().get("tax_percent", 18)
        tax_amount = after_discount * (tax_pct / 100)
        total = after_discount + tax_amount
        
        self.info_widget.update_totals(total)
    
    def load_proforma(self, proforma_id: int):
        proforma = self.proforma_service.get_proforma(proforma_id)
        if proforma:
            self.info_widget.set_proforma_number(proforma.proforma_number)
            
            # Charger les articles
            items = []
            for item in proforma.items:
                items.append({
                    "product_id": item.product_id,
                    "product_name": item.product.name if item.product else "",
                    "description": item.description,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "discount_percent": item.discount_percent
                })
            self.cart_widget.set_items(items)
            
            # Charger les infos
            info_data = {
                "customer_id": proforma.customer_id,
                "subject": proforma.terms_and_conditions or "",
                "notes": proforma.notes or "",
                "tax_percent": proforma.tax_percent,
                "discount_percent": proforma.discount_percent,
                "valid_until": proforma.valid_until
            }
            self.info_widget.set_info_data(info_data)
            
            self.calculate_totals()
            self.preview_widget.display_proforma(proforma)
            self.print_btn.setEnabled(True)
    
    def save(self):
        try:
            items = self.cart_widget.get_items()
            if not items:
                QMessageBox.warning(self, "Erreur", "Ajoutez au moins un article")
                return
            
            customer_id = self.info_widget.get_customer_id()
            if not customer_id:
                QMessageBox.warning(self, "Erreur", "Sélectionnez un client (onglet Informations)")
                return
            
            info_data = self.info_widget.get_info_data()
            
            # Préparer les articles
            items_data = []
            for item in items:
                items_data.append({
                    "product_id": item.get("product_id"),
                    "description": item.get("description", ""),
                    "quantity": item.get("quantity", 1),
                    "unit_price": item.get("unit_price", 0),
                    "discount_percent": item.get("discount_percent", 0)
                })
            
            data = {
                "customer_id": customer_id,
                "items": items_data,
                "discount_percent": info_data["discount_percent"],
                "tax_percent": info_data["tax_percent"],
                "notes": info_data["notes"],
                "subject": info_data["subject"],
                "valid_until": info_data["valid_until"]
            }
            
            if self.proforma_id:
                success, proforma, message = self.proforma_service.update_proforma(self.proforma_id, data)
            else:
                success, proforma, message = self.proforma_service.create_proforma(data, self.user_id)
            
            if success:
                self.preview_widget.display_proforma(proforma)
                self.print_btn.setEnabled(True)
                self.proforma_id = proforma.id
                self.info_widget.set_proforma_number(proforma.proforma_number)
                QMessageBox.information(self, "Succès", message)
                self.accept()
            else:
                QMessageBox.critical(self, "Erreur", message)
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde: {e}")
            QMessageBox.critical(self, "Erreur", str(e))
    
    def print_proforma(self):
        if self.proforma_id:
            proforma = self.proforma_service.get_proforma(self.proforma_id)
            if proforma:
                self.preview_widget.display_proforma(proforma)
                self.tab_widget.setCurrentIndex(2)
                self.preview_widget.print_preview()
    
    def apply_styles(self):
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                padding: 6px 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QTableWidget::item:selected {
                background-color: #1a5490;
                color: white;
            }
            QLineEdit, QComboBox, QDateEdit, QTextEdit {
                padding: 5px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTextEdit:focus {
                border-color: #1a5490;
            }
            QTabWidget::pane {
                border: 1px solid #ddd;
                border-radius: 5px;
            }
            QTabBar::tab {
                padding: 8px 16px;
                background-color: #f5f5f5;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #1a5490;
                color: white;
            }
        """)
    
    def closeEvent(self, event):
        if hasattr(self, 'session'):
            self.session.close()
        super().closeEvent(event)


# ============= VUE PRINCIPALE =============
class EnhancedProformaInvoiceView(QWidget):
    """Vue principale des proformas"""
    
    def __init__(self, current_user_id: int = None):
        super().__init__()
        self.current_user_id = current_user_id
        self.session = SessionLocal()
        self.service = ProformaService(self.session)
        
        self.current_filters = {"status": "ALL", "search": "", "date_filter": "all"}
        
        self.setup_ui()
        self.load_proformas()
    
    def closeEvent(self, event):
        """Ferme la session DB lors de la fermeture de la vue"""
        if hasattr(self, 'session'):
            try:
                self.session.close()
                logger.debug("Session DB de ProformaInvoiceView fermée")
            except Exception as e:
                logger.warning(f"Erreur fermeture session ProformaInvoiceView: {e}")
        super().closeEvent(event)
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Header
        header = QLabel("Factures Pro Forma")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a5490;")
        layout.addWidget(header)
        
        # Dashboard KPI
        self.setup_dashboard()
        layout.addWidget(self.dashboard)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Rechercher...")
        self.search_input.textChanged.connect(self.apply_filters)
        
        self.status_filter = QComboBox()
        self.status_filter.addItem("Tous", "ALL")
        for status in InvoiceStatus:
            self.status_filter.addItem(status.label, status.name)
        self.status_filter.currentIndexChanged.connect(self.apply_filters)
        
        self.date_filter = QComboBox()
        self.date_filter.addItems(["Toutes", "Aujourd'hui", "Cette semaine", "Ce mois"])
        self.date_filter.currentIndexChanged.connect(self.apply_filters)
        
        new_btn = QPushButton("Nouvelle Proforma")
        new_btn.clicked.connect(self.create_new)
        
        refresh_btn = QPushButton("Rafraîchir")
        refresh_btn.clicked.connect(self.load_proformas)
        
        toolbar.addWidget(self.search_input, 2)
        toolbar.addWidget(QLabel("Statut:"))
        toolbar.addWidget(self.status_filter)
        toolbar.addWidget(QLabel("Période:"))
        toolbar.addWidget(self.date_filter)
        toolbar.addStretch()
        toolbar.addWidget(new_btn)
        toolbar.addWidget(refresh_btn)
        
        layout.addLayout(toolbar)
        
        # Tableau
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["N°", "Client", "Date", "Échéance", "Montant", "Statut"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.doubleClicked.connect(self.edit_proforma)
        
        # Activer le menu contextuel
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        # Définir les largeurs de colonnes
        self.table.setColumnWidth(0, 100)
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(4, 100)
        self.table.setColumnWidth(5, 100)
        
        layout.addWidget(self.table)
        
        # Status
        self.status_label = QLabel("Prêt")
        layout.addWidget(self.status_label)
    
    def setup_dashboard(self):
        self.dashboard = QFrame()
        self.dashboard.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                padding: 10px;
            }
        """)
        
        layout = QHBoxLayout(self.dashboard)
        
        self.total_label = QLabel("Total: 0")
        self.total_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        
        self.draft_label = QLabel("Brouillons: 0")
        self.accepted_label = QLabel("Acceptées: 0")
        self.amount_label = QLabel("Montant: 0 FCFA")
        
        layout.addWidget(self.total_label)
        layout.addWidget(self.draft_label)
        layout.addWidget(self.accepted_label)
        layout.addWidget(self.amount_label)
        layout.addStretch()
    
    def apply_filters(self):
        date_map = {0: "all", 1: "today", 2: "week", 3: "month"}
        
        self.current_filters = {
            "status": self.status_filter.currentData(),
            "search": self.search_input.text(),
            "date_filter": date_map.get(self.date_filter.currentIndex(), "all")
        }
        self.load_proformas()
    
    def load_proformas(self):
        proformas = self.service.list_proformas(self.current_filters)
        
        # Dashboard
        total_count = len(proformas)
        draft_count = len([p for p in proformas if p.status == "BROUILLON"])
        accepted_count = len([p for p in proformas if p.status == "ACCEPTEE"])
        total_amount = sum(p.total_amount for p in proformas)
        
        # Update dashboard
        self.total_label.setText(f"Total: {total_count}")
        self.draft_label.setText(f"Brouillons: {draft_count}")
        self.accepted_label.setText(f"Acceptées: {accepted_count}")
        self.amount_label.setText(f"Montant: {total_amount:,.0f} FCFA")
        
        # Update table
        self.table.setRowCount(len(proformas))
        
        for row, p in enumerate(proformas):
            # N°
            num_item = QTableWidgetItem(p.proforma_number)
            self.table.setItem(row, 0, num_item)
            
            # Client
            customer_name = p.customer.full_name if p.customer else "N/A"
            self.table.setItem(row, 1, QTableWidgetItem(customer_name))
            
            # Date
            date_str = p.created_date.strftime("%d/%m/%Y") if p.created_date else ""
            self.table.setItem(row, 2, QTableWidgetItem(date_str))
            
            # Échéance
            valid_str = p.valid_until.strftime("%d/%m/%Y") if p.valid_until else ""
            self.table.setItem(row, 3, QTableWidgetItem(valid_str))
            
            # Montant
            amount_item = QTableWidgetItem(f"{p.total_amount:,.0f}")
            amount_item.setTextAlignment(Qt.AlignRight)
            self.table.setItem(row, 4, amount_item)
            
            # Statut
            status_item = QTableWidgetItem(p.status)
            self.table.setItem(row, 5, status_item)
        
        self.table.resizeColumnsToContents()
        self.status_label.setText(f"{len(proformas)} proforma(s)")
    
    def create_new(self):
        dialog = ProformaDialog(user_id=self.current_user_id, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.load_proformas()
    
    def edit_proforma(self):
        row = self.table.currentRow()
        if row < 0:
            return
        
        proforma_number = self.table.item(row, 0).text()
        proforma = self.service.get_proforma_by_number(proforma_number)
        
        if proforma:
            self.edit_proforma_by_id(proforma.id)
    
    def edit_proforma_by_id(self, proforma_id: int):
        dialog = ProformaDialog(user_id=self.current_user_id, proforma_id=proforma_id, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.load_proformas()
    
    def show_context_menu(self, position):
        row = self.table.currentRow()
        if row < 0:
            return
        
        proforma_number = self.table.item(row, 0).text()
        proforma = self.service.get_proforma_by_number(proforma_number)
        
        if not proforma:
            return
        
        menu = QMenu()
        
        # Actions selon le statut
        if proforma.status == "BROUILLON":
            edit_action = QAction("✏️ Modifier", self)
            edit_action.triggered.connect(lambda: self.edit_proforma_by_id(proforma.id))
            menu.addAction(edit_action)
            
            delete_action = QAction("🗑️ Supprimer", self)
            delete_action.triggered.connect(lambda: self.delete_proforma(proforma.id))
            menu.addAction(delete_action)
        
        if proforma.status in ["BROUILLON", "EN_ATTENTE", "ENVOYEE"]:
            send_action = QAction("📧 Envoyer", self)
            send_action.triggered.connect(lambda: self.change_status(proforma.id, "ENVOYEE"))
            menu.addAction(send_action)
        
        if proforma.status in ["ENVOYEE"]:
            accept_action = QAction("✅ Accepter", self)
            accept_action.triggered.connect(lambda: self.change_status(proforma.id, "ACCEPTEE"))
            menu.addAction(accept_action)
            
            reject_action = QAction("❌ Refuser", self)
            reject_action.triggered.connect(lambda: self.change_status(proforma.id, "REFUSEE"))
            menu.addAction(reject_action)
        
        if proforma.status == "ACCEPTEE":
            convert_action = QAction("💰 Convertir en facture", self)
            convert_action.triggered.connect(lambda: self.convert_to_sale(proforma.id))
            menu.addAction(convert_action)
        
        print_action = QAction("🖨️ Imprimer", self)
        print_action.triggered.connect(lambda: self.print_proforma(proforma.id))
        menu.addAction(print_action)
        
        menu.exec(self.table.viewport().mapToGlobal(position))
    
    def change_status(self, proforma_id: int, new_status: str):
        try:
            self.service.manager.change_proforma_status(proforma_id, new_status)
            self.load_proformas()
            QMessageBox.information(self, "Succès", f"Statut changé à {new_status}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))
    
    def delete_proforma(self, proforma_id: int):
        try:
            self.service.manager.delete_proforma(proforma_id)
            self.load_proformas()
            QMessageBox.information(self, "Succès", "Proforma supprimée")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))
    
    def convert_to_sale(self, proforma_id: int):
        try:
            reply = QMessageBox.question(
                self, "Confirmation",
                "Convertir cette proforma en facture définitive ?\n"
                "Cette action est irréversible.",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                success, sale, message = self.service.convert_to_sale(proforma_id, self.current_user_id)
                if success:
                    QMessageBox.information(self, "Succès", message)
                    self.load_proformas()
                else:
                    QMessageBox.critical(self, "Erreur", message)
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))
    
    def print_proforma(self, proforma_id: int):
        try:
            proforma = self.service.get_proforma(proforma_id)
            if proforma:
                dialog = ProformaDialog(user_id=self.current_user_id, proforma_id=proforma_id, parent=self)
                dialog.print_proforma()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))
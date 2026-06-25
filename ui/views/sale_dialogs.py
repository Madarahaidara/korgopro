from typing import Optional, List, Any
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QDialogButtonBox,
    QTableWidget, QTableWidgetItem, QPushButton, QHeaderView, QMessageBox,
    QTextEdit, QComboBox, QFormLayout
)
from PySide6.QtGui import QColor, QDoubleValidator

from core.models.stock_models import Product
from core.models.sale_models import Customer
from ui.views.sale_widgets import get_icon


class QuantityDialog(QDialog):
    def __init__(self, product: Product, currency: str = "FCFA", parent=None):
        super().__init__(parent)
        self.product = product
        self.currency = currency
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle(f"Ajouter {self.product.name}")
        self.setModal(True)
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)

        info_label = QLabel(
            f"<b>{self.product.name}</b><br>"
            f"Code: {self.product.code}<br>"
            f"Prix: {self.product.sale_price:,.0f} {self.currency}<br>"
            f"Stock disponible: {self.product.quantity}"
        )
        layout.addWidget(info_label)

        quantity_layout = QHBoxLayout()
        quantity_layout.addWidget(QLabel("Quantité:"))

        self.quantity_edit = QLineEdit()
        self.quantity_edit.setText("1")
        self.quantity_edit.setAlignment(Qt.AlignRight)
        self.quantity_edit.setValidator(QDoubleValidator(0.1, self.product.quantity, 2))
        self.quantity_edit.setStyleSheet("""
            QLineEdit {
                border: 2px solid #d1d5db;
                border-radius: 4px;
                padding: 6px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
        """)
        self.quantity_edit.textChanged.connect(self.update_total)

        quantity_layout.addWidget(self.quantity_edit)
        quantity_layout.addStretch()
        layout.addLayout(quantity_layout)

        self.total_label = QLabel(f"Total: {self.product.sale_price:,.0f} {self.currency}")
        layout.addWidget(self.total_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def update_total(self, text: str):
        try:
            value = float(text) if text else 0
            if value < 0.1:
                value = 0.1
                self.quantity_edit.setText(f"{value:.2f}")
            total = value * self.product.sale_price
            self.total_label.setText(f"Total: {total:,.0f} {self.currency}")
        except ValueError:
            self.quantity_edit.setText("1")
            self.update_total("1")

    @property
    def quantity(self) -> float:
        try:
            return float(self.quantity_edit.text())
        except ValueError:
            return 1.0


class CustomerSelectionDialog(QDialog):
    customer_selected = Signal(object)

    def __init__(self, customer_service: Any, currency: str = "FCFA", parent=None):
        super().__init__(parent)
        self.customer_service = customer_service
        self.currency = currency
        self.selected_customer: Optional[Customer] = None
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Sélectionner un client")
        self.setModal(True)
        self.setMinimumSize(600, 400)

        layout = QVBoxLayout(self)

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Rechercher par nom, prénom, société, téléphone...")
        self.search_input.textChanged.connect(self.filter_customers)
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #d1d5db;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
        """)

        self.new_customer_btn = QPushButton("+ Nouveau client")
        self.new_customer_btn.setIcon(get_icon("plus", "#10b981", 16))
        self.new_customer_btn.clicked.connect(self.create_new_customer)
        self.new_customer_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)

        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(self.new_customer_btn)
        layout.addLayout(search_layout)

        self.customers_table = QTableWidget()
        self.customers_table.setColumnCount(6)
        self.customers_table.setHorizontalHeaderLabels([
            "ID", "Code", "Nom complet", "Société", "Téléphone", "Solde"
        ])

        header = self.customers_table.horizontalHeader()
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        self.customers_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.customers_table.setSelectionMode(QTableWidget.SingleSelection)
        self.customers_table.doubleClicked.connect(self.on_customer_double_clicked)
        self.customers_table.setStyleSheet("""
            QTableWidget::item:selected {
                background-color: #dbeafe;
                color: #1e40af;
            }
        """)

        layout.addWidget(self.customers_table)

        button_layout = QHBoxLayout()
        self.select_btn = QPushButton("Sélectionner")
        self.select_btn.setIcon(get_icon("check", "#10b981", 16))
        self.select_btn.clicked.connect(self.on_accept)
        self.select_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)

        self.cancel_btn = QPushButton("Annuler")
        self.cancel_btn.setIcon(get_icon("x", "#ef4444", 16))
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)

        button_layout.addStretch()
        button_layout.addWidget(self.select_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

        self.filter_customers()

    def filter_customers(self):
        search_text = self.search_input.text()
        customers = self.customer_service.get_customers(search_text)
        self.display_customers(customers)

    def display_customers(self, customers: List[Customer]):
        self.customers_table.setRowCount(len(customers))

        for row, customer in enumerate(customers):
            id_item = QTableWidgetItem(str(customer.id))
            id_item.setData(Qt.UserRole, customer.id)
            self.customers_table.setItem(row, 0, id_item)

            code_item = QTableWidgetItem(customer.code or "")
            self.customers_table.setItem(row, 1, code_item)

            name_item = QTableWidgetItem(f"{customer.first_name} {customer.last_name}")
            self.customers_table.setItem(row, 2, name_item)

            company_item = QTableWidgetItem(customer.company or "")
            self.customers_table.setItem(row, 3, company_item)

            phone_item = QTableWidgetItem(customer.phone or "")
            self.customers_table.setItem(row, 4, phone_item)

            balance_item = QTableWidgetItem(f"{customer.balance:,.0f} {self.currency}")
            balance_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if customer.balance > 0:
                balance_item.setForeground(QColor("#ef4444"))
            elif customer.balance < 0:
                balance_item.setForeground(QColor("#10b981"))
            self.customers_table.setItem(row, 5, balance_item)

        self.customers_table.resizeColumnsToContents()

    def get_selected_customer(self) -> Optional[Customer]:
        selected = self.customers_table.selectedItems()
        if not selected:
            return None

        row = selected[0].row()
        customer_id = self.customers_table.item(row, 0).data(Qt.UserRole)
        if customer_id:
            return self.customer_service.db_session.query(Customer).get(customer_id)
        return None

    def on_customer_double_clicked(self, index):
        customer = self.get_selected_customer()
        if customer:
            self.selected_customer = customer
            self.accept()

    def on_accept(self):
        customer = self.get_selected_customer()
        if customer:
            self.selected_customer = customer
            self.accept()
        else:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner un client")

    def create_new_customer(self):
        dialog = NewCustomerDialog(self.customer_service, self)
        if dialog.exec() and dialog.customer:
            self.filter_customers()
            self.search_input.setText("")
            for row in range(self.customers_table.rowCount()):
                customer_id = self.customers_table.item(row, 0).data(Qt.UserRole)
                if customer_id == dialog.customer.id:
                    self.customers_table.selectRow(row)
                    break

    def get_selected_customer_id(self) -> Optional[int]:
        return self.selected_customer.id if self.selected_customer else None


class NewCustomerDialog(QDialog):
    def __init__(self, customer_service: Any, parent=None):
        super().__init__(parent)
        self.customer_service = customer_service
        self.customer = None
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Nouveau client")
        self.setModal(True)
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        self.first_name_input = QLineEdit()
        self.first_name_input.setPlaceholderText("Prénom")
        self.first_name_input.setStyleSheet("padding: 8px; border: 1px solid #d1d5db; border-radius: 4px;")
        form_layout.addRow("Prénom *:", self.first_name_input)

        self.last_name_input = QLineEdit()
        self.last_name_input.setPlaceholderText("Nom")
        self.last_name_input.setStyleSheet("padding: 8px; border: 1px solid #d1d5db; border-radius: 4px;")
        form_layout.addRow("Nom *:", self.last_name_input)

        self.company_input = QLineEdit()
        self.company_input.setPlaceholderText("Société")
        self.company_input.setStyleSheet("padding: 8px; border: 1px solid #d1d5db; border-radius: 4px;")
        form_layout.addRow("Société:", self.company_input)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("email@exemple.com")
        self.email_input.setStyleSheet("padding: 8px; border: 1px solid #d1d5db; border-radius: 4px;")
        form_layout.addRow("Email:", self.email_input)

        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("Téléphone")
        self.phone_input.setStyleSheet("padding: 8px; border: 1px solid #d1d5db; border-radius: 4px;")
        form_layout.addRow("Téléphone:", self.phone_input)

        self.address_input = QTextEdit()
        self.address_input.setPlaceholderText("Adresse complète")
        self.address_input.setMaximumHeight(80)
        self.address_input.setStyleSheet("padding: 8px; border: 1px solid #d1d5db; border-radius: 4px;")
        form_layout.addRow("Adresse:", self.address_input)

        self.customer_type_combo = QComboBox()
        self.customer_type_combo.addItems(["RETAIL", "WHOLESALE", "VIP"])
        self.customer_type_combo.setStyleSheet("padding: 8px; border: 1px solid #d1d5db; border-radius: 4px;")
        form_layout.addRow("Type:", self.customer_type_combo)

        layout.addLayout(form_layout)

        buttons = QDialogButtonBox()
        buttons.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.create_customer)
        buttons.rejected.connect(self.reject)

        ok_btn = buttons.button(QDialogButtonBox.Ok)
        if ok_btn:
            ok_btn.setText("Créer")
            ok_btn.setStyleSheet("background-color: #10b981; color: white; padding: 8px 16px; border-radius: 4px;")

        cancel_btn = buttons.button(QDialogButtonBox.Cancel)
        if cancel_btn:
            cancel_btn.setStyleSheet("background-color: #ef4444; color: white; padding: 8px 16px; border-radius: 4px;")

        layout.addWidget(buttons)

    def create_customer(self):
        if not self.first_name_input.text() or not self.last_name_input.text():
            QMessageBox.warning(self, "Erreur", "Le prénom et le nom sont requis")
            return

        customer_data = {
            "first_name": self.first_name_input.text().strip(),
            "last_name": self.last_name_input.text().strip(),
            "company": self.company_input.text().strip() or None,
            "email": self.email_input.text().strip() or None,
            "phone": self.phone_input.text().strip() or None,
            "address": self.address_input.toPlainText().strip() or None,
            "customer_type": self.customer_type_combo.currentText()
        }

        success, customer, message = self.customer_service.create_customer(customer_data)

        if success:
            self.customer = customer
            QMessageBox.information(self, "Succès", message)
            self.accept()
        else:
            QMessageBox.critical(self, "Erreur", message)

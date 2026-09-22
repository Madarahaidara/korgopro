# ui/views/invoice_register_view.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QComboBox, QLabel, QHeaderView, QMessageBox,
    QDialog, QFormLayout, QDoubleSpinBox, QDialogButtonBox, QGroupBox,
)
from PySide6.QtCore import Qt
from core.invoice_register_manager import InvoiceRegisterManager

STATUS_LABELS = {
    "ALL": "Tous les statuts",
    "PAID": "Payées",
    "PARTIAL": "Partiellement payées",
    "PENDING": "Impayées",
}


class PaymentDialog(QDialog):
    """Boîte de dialogue d'encaissement d'une facture."""

    def __init__(self, due, accounts, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Encaisser un paiement")
        self.setMinimumWidth(380)
        self.account_id = None
        self.amount = 0.0

        layout = QFormLayout(self)
        self.lbl_due = QLabel("Reste dû : {:,.0f} FCFA".format(due).replace(",", " "))
        layout.addRow(self.lbl_due)

        self.spin_amount = QDoubleSpinBox()
        self.spin_amount.setRange(0.0, max(due, 0.0))
        self.spin_amount.setDecimals(2)
        self.spin_amount.setValue(max(due, 0.0))
        self.spin_amount.setSuffix(" FCFA")
        layout.addRow("Montant encaissé :", self.spin_amount)

        self.combo_account = QComboBox()
        for a in accounts:
            self.combo_account.addItem(
                "{} ({})".format(a.name, a.account_type), a.id)
        layout.addRow("Compte à créditer :", self.combo_account)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def accept(self):
        self.amount = self.spin_amount.value()
        self.account_id = self.combo_account.currentData()
        if self.amount <= 0:
            QMessageBox.warning(self, "Montant invalide",
                                "Le montant doit être positif.")
            return
        super().accept()


class InvoiceRegisterView(QWidget):
    """Registre des factures clients : liste, statuts, encaissements."""

    def __init__(self, user_data=None):
        super().__init__()
        self.user_data = user_data or {}
        self.manager = InvoiceRegisterManager()
        self.setup_ui()
        self.refresh()

    def setup_ui(self):
        self.setObjectName("InvoiceRegisterView")
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ===== Cartes de synthèse =====
        cards = QHBoxLayout()
        self.card_count = QLabel("0")
        self.card_total = QLabel("0 FCFA")
        self.card_paid = QLabel("0 FCFA")
        self.card_due = QLabel("0 FCFA")
        for title, widget in (
                ("Factures", self.card_count),
                ("Montant total", self.card_total),
                ("Encaissé", self.card_paid),
                ("Reste dû", self.card_due)):
            box = QGroupBox(title)
            v = QVBoxLayout(box)
            widget.setStyleSheet("font-size: 16px; font-weight: bold;")
            v.addWidget(widget)
            cards.addWidget(box)
        layout.addLayout(cards)

        # ===== Filtres =====
        filters = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText(
            "Rechercher (n° facture, client...)")
        self.txt_search.textChanged.connect(self.refresh)
        filters.addWidget(self.txt_search, 2)

        self.combo_status = QComboBox()
        for key, label in STATUS_LABELS.items():
            self.combo_status.addItem(label, key)
        self.combo_status.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.combo_status, 1)
        layout.addLayout(filters)

        # ===== Table =====
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "N° Facture", "Client", "Date", "Total", "Payé", "Reste dû",
            "Statut"])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table, 1)

        # ===== Actions =====
        actions = QHBoxLayout()
        self.btn_refresh = QPushButton("🔄 Rafraîchir")
        self.btn_refresh.clicked.connect(self.refresh)
        actions.addWidget(self.btn_refresh)
        actions.addStretch()
        self.btn_pay = QPushButton("💰 Encaisser un paiement")
        self.btn_pay.clicked.connect(self._on_receive_payment)
        actions.addWidget(self.btn_pay)
        layout.addLayout(actions)

    def refresh(self):
        result = self.manager.list_invoices(
            status=self.combo_status.currentData() or "ALL",
            search=self.txt_search.text().strip() or None,
        )
        invoices = result.get("invoices", []) if result.get("success") else []

        summary = self.manager.get_register_summary()
        if summary.get("success"):
            self.card_count.setText(str(summary["count"]))
            self.card_total.setText(
                "{:,.0f} FCFA".format(summary["total"]).replace(",", " "))
            self.card_paid.setText(
                "{:,.0f} FCFA".format(summary["paid"]).replace(",", " "))
            self.card_due.setText(
                "{:,.0f} FCFA".format(summary["due"]).replace(",", " "))

        self.table.setRowCount(0)
        for inv in invoices:
            row = self.table.rowCount()
            self.table.insertRow(row)
            due = (inv.total_amount or 0) - (inv.amount_paid or 0)
            customer = inv.customer.full_name if inv.customer else "—"
            values = [
                inv.sale_number,
                customer,
                inv.sale_date.strftime("%d/%m/%Y %H:%M")
                if inv.sale_date else "—",
                "{:,.0f}".format(inv.total_amount or 0).replace(",", " "),
                "{:,.0f}".format(inv.amount_paid or 0).replace(",", " "),
                "{:,.0f}".format(max(due, 0)).replace(",", " "),
                inv.payment_status or "—",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col >= 3:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row, col, item)

    def _on_receive_payment(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(
                self, "Aucune sélection",
                "Sélectionnez d'abord une facture dans la liste.")
            return
        sale_number = self.table.item(row, 0).text()
        result = self.manager.list_invoices(search=sale_number)
        invoices = [i for i in result.get("invoices", [])
                    if i.sale_number == sale_number]
        if not invoices:
            QMessageBox.warning(self, "Introuvable",
                                "Facture introuvable : " + sale_number)
            return
        inv = invoices[0]
        due = (inv.total_amount or 0) - (inv.amount_paid or 0)
        if due <= 0:
            QMessageBox.information(
                self, "Déjà payée",
                "Cette facture est déjà entièrement payée.")
            return
        accounts = self.manager._treasury.get_accounts().get("accounts", [])
        if not accounts:
            QMessageBox.warning(
                self, "Aucun compte",
                "Créez d'abord un compte dans la vue Trésorerie.")
            return
        dialog = PaymentDialog(due, accounts, self)
        if dialog.exec() != QDialog.Accepted:
            return
        result = self.manager.receive_payment(
            sale_id=inv.id,
            amount=dialog.amount,
            account_id=dialog.account_id,
            user_id=self.user_data.get("id"),
        )
        if result.get("success"):
            QMessageBox.information(
                self, "Encaissement réussi",
                "Montant encaissé sur {}.\nLa trésorerie a été mise à jour."
                .format(sale_number))
            self.refresh()
        else:
            QMessageBox.critical(self, "Erreur",
                                 result.get("error", "Erreur inconnue"))

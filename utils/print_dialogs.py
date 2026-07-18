"""
Dialogues pour l'impression dans l'application Korgo
"""

from PySide6.QtCore import Qt, Signal, QMarginsF
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QComboBox, QSpinBox, QCheckBox,
    QGroupBox, QFormLayout, QDateEdit, QMessageBox,
    QHeaderView, QDialogButtonBox, QRadioButton,
    QButtonGroup, QProgressDialog, QFileDialog,
    QInputDialog, QTextEdit
)
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtGui import QTextDocument
from PySide6.QtGui import QPageSize, QPageLayout
from datetime import datetime, timedelta
from typing import List, Optional
import logging

from PySide6.QtGui import QPageSize, QPageLayout, QPainter

from core.database import SessionLocal
from core.models.sale_models import Sale, Customer
from utils.print_service import InvoicePrinter

logger = logging.getLogger(__name__)
CURRENCY = "FCFA"


class PrintOptionsDialog(QDialog):
    """Dialogue pour choisir les options d'impression"""
    
    def __init__(self, sale_data: dict, parent=None):
        super().__init__(parent)
        self.sale_data = sale_data
        self.db_session = SessionLocal()
        self.printer_service = InvoicePrinter(self.db_session)
        self.setup_ui()
    
    def setup_ui(self):
        """Configure l'interface"""
        self.setWindowTitle("Options d'impression")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout(self)
        
        # Informations vente
        info_group = QGroupBox("Informations de la vente")
        info_layout = QGridLayout(info_group)
        
        info_layout.addWidget(QLabel("Numéro:"), 0, 0)
        info_layout.addWidget(QLabel(f"<b>{self.sale_data.get('sale_number', '')}</b>"), 0, 1)
        
        info_layout.addWidget(QLabel("Date:"), 1, 0)
        info_layout.addWidget(QLabel(f"<b>{self.sale_data.get('date', '')}</b>"), 1, 1)
        
        info_layout.addWidget(QLabel("Total:"), 2, 0)
        info_layout.addWidget(QLabel(f"<b>{self.sale_data.get('total', 0):,.0f} {CURRENCY}</b>"), 2, 1)
        
        if self.sale_data.get('customer'):
            info_layout.addWidget(QLabel("Client:"), 3, 0)
            info_layout.addWidget(QLabel(f"<b>{self.sale_data['customer']}</b>"), 3, 1)
        
        layout.addWidget(info_group)
        
        # Options d'impression
        options_group = QGroupBox("Options d'impression")
        options_layout = QVBoxLayout(options_group)
        
        # Type de document
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Type de document:"))
        
        self.doc_type_group = QButtonGroup(self)
        self.invoice_radio = QRadioButton("Facture détaillée")
        self.receipt_radio = QRadioButton("Ticket de caisse")
        self.both_radio = QRadioButton("Les deux")
        
        self.invoice_radio.setChecked(True)
        
        self.doc_type_group.addButton(self.invoice_radio)
        self.doc_type_group.addButton(self.receipt_radio)
        self.doc_type_group.addButton(self.both_radio)
        
        type_layout.addWidget(self.invoice_radio)
        type_layout.addWidget(self.receipt_radio)
        type_layout.addWidget(self.both_radio)
        type_layout.addStretch()
        
        options_layout.addLayout(type_layout)
        
        # Copies
        copies_layout = QHBoxLayout()
        copies_layout.addWidget(QLabel("Nombre de copies:"))
        
        self.copies_spinbox = QSpinBox()
        self.copies_spinbox.setMinimum(1)
        self.copies_spinbox.setMaximum(10)
        self.copies_spinbox.setValue(1)
        
        copies_layout.addWidget(self.copies_spinbox)
        copies_layout.addStretch()
        options_layout.addLayout(copies_layout)
        
        # Options supplémentaires
        self.open_after_check = QCheckBox("Ouvrir le document après génération")
        self.open_after_check.setChecked(True)
        options_layout.addWidget(self.open_after_check)
        
        self.print_after_check = QCheckBox("Imprimer directement")
        options_layout.addWidget(self.print_after_check)
        
        layout.addWidget(options_group)
        
        # Boutons
        buttons = QDialogButtonBox()
        
        self.preview_btn = QPushButton("👁 Aperçu")
        self.preview_btn.clicked.connect(self.preview)
        buttons.addButton(self.preview_btn, QDialogButtonBox.ActionRole)
        
        self.generate_btn = QPushButton("💾 Générer PDF")
        self.generate_btn.setDefault(True)
        self.generate_btn.clicked.connect(self.generate)
        buttons.addButton(self.generate_btn, QDialogButtonBox.ActionRole)
        
        self.print_btn = QPushButton("🖨️ Imprimer")
        self.print_btn.clicked.connect(self.print_directly)
        buttons.addButton(self.print_btn, QDialogButtonBox.ActionRole)
        
        cancel_btn = QPushButton("Annuler")
        cancel_btn.clicked.connect(self.reject)
        buttons.addButton(cancel_btn, QDialogButtonBox.RejectRole)
        
        layout.addWidget(buttons)
    
    def get_document_type(self) -> str:
        """Récupère le type de document sélectionné"""
        if self.invoice_radio.isChecked():
            return "invoice"
        elif self.receipt_radio.isChecked():
            return "receipt"
        else:
            return "both"
    
    def preview(self):
        """Affiche un aperçu"""
        try:
            success, html, message = self.printer_service.generate_html_invoice(
                self.sale_data['sale_id']
            )
            
            if success:
                preview_dialog = PrintPreviewDialog(html, self)
                preview_dialog.exec()
            else:
                QMessageBox.warning(self, "Erreur", message)
                
        except Exception as e:
            logger.error(f"Erreur aperçu: {e}")
            QMessageBox.critical(self, "Erreur", f"Erreur: {str(e)}")
    
    def generate(self):
        """Génère le PDF"""
        doc_type = self.get_document_type()
        copies = self.copies_spinbox.value()
        
        try:
            files = []
            
            if doc_type in ["invoice", "both"]:
                success, message, file_path = self.printer_service.generate_invoice(
                    self.sale_data['sale_id']
                )
                
                if success:
                    files.append(("Facture", file_path))
                else:
                    QMessageBox.warning(self, "Erreur", message)
                    return
            
            if doc_type in ["receipt", "both"]:
                success, message, file_path = self.printer_service.generate_receipt(
                    self.sale_data['sale_id']
                )
                
                if success:
                    files.append(("Ticket", file_path))
                else:
                    QMessageBox.warning(self, "Erreur", message)
                    return
            
            # Ouvrir les fichiers si demandé
            if self.open_after_check.isChecked():
                for doc_name, file_path in files:
                    self.printer_service.open_file(file_path)
            
            # Message de confirmation
            if len(files) == 1:
                msg = f"{files[0][0]} généré avec succès"
            else:
                msg = f"{len(files)} documents générés avec succès"
            
            QMessageBox.information(self, "Succès", msg)
            
            # Fermer le dialogue si tout est OK
            self.accept()
            
        except Exception as e:
            logger.error(f"Erreur génération: {e}")
            QMessageBox.critical(self, "Erreur", f"Erreur: {str(e)}")
    
    def adjust_html_for_printing(self, html):
        """Ajuste le HTML pour optimiser l'impression sur page A4"""
        # Ajouter des styles CSS pour l'impression
        css = """
        <style>
            @page {
                margin: 0.5cm;
                size: A4 portrait;
            }
            body {
                margin: 0;
                padding: 0;
                width: 100%;
                font-family: 'Arial', sans-serif;
                font-size: 10pt;
            }
            .page-container {
                width: 100%;
                max-width: 100%;
                padding: 10px;
                box-sizing: border-box;
            }
            table {
                width: 100%;
                max-width: 100%;
                border-collapse: collapse;
                table-layout: fixed;
                font-size: 9pt;
            }
            th, td {
                padding: 6px 4px;
                border: 1px solid #333;
                word-wrap: break-word;
                overflow-wrap: break-word;
            }
            .header, .footer {
                width: 100%;
                text-align: center;
            }
            .totals-table {
                width: 100%;
                margin-top: 15px;
            }
            .company-info {
                width: 100%;
                text-align: center;
                margin-bottom: 15px;
                font-weight: bold;
                font-size: 11pt;
            }
            .invoice-title {
                width: 100%;
                text-align: center;
                font-size: 12pt;
                font-weight: bold;
                margin: 10px 0;
            }
        </style>
        """
        
        # Insérer le CSS dans le HTML
        if '<head>' in html:
            html = html.replace('<head>', f'<head>{css}')
        else:
            html = f'<html><head>{css}</head><body><div class="page-container">{html}</div></body></html>'
        
        return html
    
    def print_directly(self):
        """Fonction supprimée - utiliser 'Générer PDF' à la place"""
        QMessageBox.information(self, "Impression directe désactivée", 
            "Veuillez utiliser le bouton '💾 Générer PDF' pour créer le fichier,\n"
            "puis l'ouvrir pour imprimer.")
        return

    
    def closeEvent(self, event):
        """Fermeture propre"""
        if hasattr(self, 'db_session'):
            self.db_session.close()
        super().closeEvent(event)


class PrintHistoryDialog(QDialog):
    """Dialogue pour imprimer des ventes passées"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_session = SessionLocal()
        self.printer_service = InvoicePrinter(self.db_session)
        self.setup_ui()
        self.load_sales()
    
    def setup_ui(self):
        """Configure l'interface"""
        self.setWindowTitle("Imprimer des ventes")
        self.setModal(True)
        self.setMinimumSize(900, 600)
        
        layout = QVBoxLayout(self)
        
        # Filtres
        filter_group = QGroupBox("Filtres")
        filter_layout = QGridLayout(filter_group)
        
        # Dates
        self.date_from = QDateEdit()
        self.date_from.setDate(datetime.now().date() - timedelta(days=30))
        self.date_from.setCalendarPopup(True)
        self.date_from.dateChanged.connect(self.filter_sales)
        
        self.date_to = QDateEdit()
        self.date_to.setDate(datetime.now().date())
        self.date_to.setCalendarPopup(True)
        self.date_to.dateChanged.connect(self.filter_sales)
        
        # Recherche
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Rechercher par numéro, client...")
        self.search_input.textChanged.connect(self.filter_sales)
        
        # Bouton actualiser
        refresh_btn = QPushButton("🔄 Actualiser")
        refresh_btn.clicked.connect(self.load_sales)
        
        filter_layout.addWidget(QLabel("Du:"), 0, 0)
        filter_layout.addWidget(self.date_from, 0, 1)
        filter_layout.addWidget(QLabel("Au:"), 0, 2)
        filter_layout.addWidget(self.date_to, 0, 3)
        filter_layout.addWidget(QLabel("Recherche:"), 1, 0)
        filter_layout.addWidget(self.search_input, 1, 1, 1, 3)
        filter_layout.addWidget(refresh_btn, 1, 4)
        
        layout.addWidget(filter_group)
        
        # Table des ventes
        self.sales_table = QTableWidget()
        self.sales_table.setColumnCount(7)
        self.sales_table.setHorizontalHeaderLabels([
            "", "Numéro", "Date", "Client", "Total", "Paiement", "Statut"
        ])
        
        self.sales_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.sales_table.setSelectionMode(QTableWidget.ExtendedSelection)
        
        header = self.sales_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Checkbox
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Numéro
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Date
        header.setSectionResizeMode(3, QHeaderView.Stretch)          # Client
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Total
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Paiement
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Statut
        
        layout.addWidget(self.sales_table)
        
        # Boutons de sélection
        selection_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("✓ Tout sélectionner")
        self.select_all_btn.clicked.connect(self.select_all)
        
        self.deselect_all_btn = QPushButton("✗ Tout désélectionner")
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        
        selection_layout.addWidget(self.select_all_btn)
        selection_layout.addWidget(self.deselect_all_btn)
        selection_layout.addStretch()
        
        layout.addLayout(selection_layout)
        
        # Boutons d'action
        action_layout = QHBoxLayout()
        
        self.export_btn = QPushButton("📤 Exporter CSV")
        self.export_btn.clicked.connect(self.export_csv)
        
        self.print_selected_btn = QPushButton("🖨️ Imprimer sélection")
        self.print_selected_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
            }
        """)
        self.print_selected_btn.clicked.connect(self.print_selected)
        
        close_btn = QPushButton("Fermer")
        close_btn.clicked.connect(self.reject)
        
        action_layout.addWidget(self.export_btn)
        action_layout.addStretch()
        action_layout.addWidget(self.print_selected_btn)
        action_layout.addWidget(close_btn)
        
        layout.addLayout(action_layout)
    
    def load_sales(self):
        """Charge les ventes"""
        try:
            date_from = self.date_from.date().toPython()
            date_to = self.date_to.date().addDays(1).toPython()
            search_text = self.search_input.text()
            
            # Requête de base
            query = self.db_session.query(Sale)\
                .options(Sale.customer)\
                .filter(
                    Sale.sale_date >= date_from,
                    Sale.sale_date <= date_to,
                    Sale.sale_status == "COMPLETED"
                )
            
            # Filtre de recherche
            if search_text:
                query = query.join(Customer)\
                    .filter(
                        (Sale.sale_number.ilike(f"%{search_text}%")) |
                        (Customer.first_name.ilike(f"%{search_text}%")) |
                        (Customer.last_name.ilike(f"%{search_text}%")) |
                        (Customer.company.ilike(f"%{search_text}%"))
                    )
            
            sales = query.order_by(Sale.sale_date.desc()).all()
            
            self.display_sales(sales)
            
        except Exception as e:
            logger.error(f"Erreur chargement ventes: {e}")
            QMessageBox.critical(self, "Erreur", f"Erreur: {str(e)}")
    
    def display_sales(self, sales):
        """Affiche les ventes dans le tableau"""
        self.sales_table.setRowCount(len(sales))
        
        for row, sale in enumerate(sales):
            # Checkbox
            checkbox_item = QTableWidgetItem()
            checkbox_item.setCheckState(Qt.Unchecked)
            checkbox_item.setData(Qt.UserRole, sale.id)
            self.sales_table.setItem(row, 0, checkbox_item)
            
            # Numéro
            num_item = QTableWidgetItem(sale.sale_number)
            self.sales_table.setItem(row, 1, num_item)
            
            # Date
            date_item = QTableWidgetItem(sale.sale_date.strftime('%d/%m/%Y %H:%M'))
            self.sales_table.setItem(row, 2, date_item)
            
            # Client
            if sale.customer:
                client_name = f"{sale.customer.first_name} {sale.customer.last_name}"
                if sale.customer.company:
                    client_name += f" ({sale.customer.company})"
            else:
                client_name = "Client général"
            self.sales_table.setItem(row, 3, QTableWidgetItem(client_name))
            
            # Total
            total_item = QTableWidgetItem(f"{sale.total_amount:,.0f} {CURRENCY}")
            total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.sales_table.setItem(row, 4, total_item)
            
            # Paiement
            payment_item = QTableWidgetItem(sale.payment_method)
            self.sales_table.setItem(row, 5, payment_item)
            
            # Statut
            status_item = QTableWidgetItem(sale.payment_status)
            if sale.payment_status == "PAID":
                status_item.setForeground(QColor("#10b981"))
            elif sale.payment_status == "PARTIAL":
                status_item.setForeground(QColor("#f59e0b"))
            else:
                status_item.setForeground(QColor("#ef4444"))
            self.sales_table.setItem(row, 6, status_item)
    
    def filter_sales(self):
        """Filtre les ventes affichées"""
        search_text = self.search_input.text().lower()
        
        for row in range(self.sales_table.rowCount()):
            match = False
            
            # Vérifier chaque colonne (sauf la checkbox)
            for col in range(1, self.sales_table.columnCount()):
                item = self.sales_table.item(row, col)
                if item and search_text in item.text().lower():
                    match = True
                    break
            
            self.sales_table.setRowHidden(row, not match)
    
    def get_selected_sales(self) -> List[int]:
        """Récupère les IDs des ventes sélectionnées"""
        selected_ids = []
        
        for row in range(self.sales_table.rowCount()):
            checkbox = self.sales_table.item(row, 0)
            if checkbox and checkbox.checkState() == Qt.Checked:
                sale_id = checkbox.data(Qt.UserRole)
                if sale_id:
                    selected_ids.append(sale_id)
        
        return selected_ids
    
    def select_all(self):
        """Sélectionne toutes les ventes"""
        for row in range(self.sales_table.rowCount()):
            checkbox = self.sales_table.item(row, 0)
            if checkbox:
                checkbox.setCheckState(Qt.Checked)
    
    def deselect_all(self):
        """Désélectionne toutes les ventes"""
        for row in range(self.sales_table.rowCount()):
            checkbox = self.sales_table.item(row, 0)
            if checkbox:
                checkbox.setCheckState(Qt.Unchecked)
    
    def export_csv(self):
        """Exporte les ventes sélectionnées en CSV"""
        selected_ids = self.get_selected_sales()
        
        if not selected_ids:
            QMessageBox.warning(self, "Export", "Veuillez sélectionner au moins une vente")
            return
        
        # Demander le fichier de destination
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Exporter CSV", "", "CSV Files (*.csv)"
        )
        
        if not file_path:
            return
        
        try:
            import csv
            
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile, delimiter=';')
                
                # En-têtes
                writer.writerow([
                    'Numéro', 'Date', 'Client', 'Sous-total', 'Remise',
                    'TVA', 'Total', 'Paiement', 'Statut'
                ])
                
                # Données
                for sale_id in selected_ids:
                    sale = self.db_session.query(Sale).get(sale_id)
                    if sale:
                        client_name = "Client général"
                        if sale.customer:
                            client_name = f"{sale.customer.first_name} {sale.customer.last_name}"
                        
                        writer.writerow([
                            sale.sale_number,
                            sale.sale_date.strftime('%d/%m/%Y %H:%M'),
                            client_name,
                            sale.subtotal,
                            sale.discount_amount,
                            sale.tax_amount,
                            sale.total_amount,
                            sale.payment_method,
                            sale.payment_status
                        ])
            
            QMessageBox.information(
                self, "Export réussi",
                f"{len(selected_ids)} vente(s) exportée(s) avec succès"
            )
            
        except Exception as e:
            logger.error(f"Erreur export CSV: {e}")
            QMessageBox.critical(self, "Erreur", f"Erreur: {str(e)}")
    
    def print_selected(self):
        """Imprime les ventes sélectionnées"""
        selected_ids = self.get_selected_sales()
        
        if not selected_ids:
            QMessageBox.warning(self, "Impression", "Veuillez sélectionner au moins une vente")
            return
        
        # Demander le type de document
        doc_type, ok = QInputDialog.getItem(
            self, "Type de document",
            "Choisissez le type de document à générer:",
            ["Facture détaillée", "Ticket de caisse", "Les deux"],
            0, False
        )
        
        if not ok:
            return
        
        # Demander le dossier de destination
        output_dir = QFileDialog.getExistingDirectory(
            self, "Sélectionner le dossier de destination"
        )
        
        if not output_dir:
            return
        
        # Créer une boîte de dialogue de progression
        progress = QProgressDialog(
            "Génération des documents...",
            "Annuler",
            0,
            len(selected_ids),
            self
        )
        progress.setWindowTitle("Génération en cours")
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        
        try:
            results = self.printer_service.generate_batch_invoices(selected_ids, output_dir)
            
            # Compter les succès/échecs
            success_count = 0
            error_count = 0
            
            for i, sale_id in enumerate(selected_ids):
                progress.setValue(i + 1)
                
                if progress.wasCanceled():
                    break
                
                if sale_id in results:
                    success, message, _ = results[sale_id]
                    if success:
                        success_count += 1
                    else:
                        error_count += 1
            
            progress.close()
            
            # Afficher le résultat
            if error_count == 0:
                QMessageBox.information(
                    self, "Succès",
                    f"{success_count} document(s) généré(s) avec succès dans:\n{output_dir}"
                )
            else:
                QMessageBox.warning(
                    self, "Résultat partiel",
                    f"{success_count} document(s) généré(s) avec succès\n"
                    f"{error_count} erreur(s)"
                )
            
        except Exception as e:
            progress.close()
            logger.error(f"Erreur impression batch: {e}")
            QMessageBox.critical(self, "Erreur", f"Erreur: {str(e)}")
    
    def closeEvent(self, event):
        """Fermeture propre"""
        if hasattr(self, 'db_session'):
            self.db_session.close()
        super().closeEvent(event)


class PrintPreviewDialog(QDialog):
    """Dialogue d'aperçu avant impression"""
    
    def __init__(self, html_content: str, parent=None):
        super().__init__(parent)
        self.html_content = html_content
        self.setup_ui()
    
    def setup_ui(self):
        """Configure l'interface"""
        self.setWindowTitle("Aperçu avant impression")
        self.setModal(True)
        self.setMinimumSize(800, 600)
        
        layout = QVBoxLayout(self)
        
        # Éditeur HTML pour l'aperçu
        self.preview_editor = QTextEdit()
        self.preview_editor.setReadOnly(True)
        
        # Ajuster le HTML pour l'affichage
        adjusted_html = self.adjust_html_for_display(self.html_content)
        self.preview_editor.setHtml(adjusted_html)
        
        layout.addWidget(self.preview_editor)
        
        # Boutons
        buttons = QDialogButtonBox()
        
        print_btn = QPushButton("🖨️ Imprimer")
        print_btn.clicked.connect(self.print_document)
        buttons.addButton(print_btn, QDialogButtonBox.ActionRole)
        
        close_btn = QPushButton("Fermer")
        close_btn.clicked.connect(self.accept)
        buttons.addButton(close_btn, QDialogButtonBox.AcceptRole)
        
        layout.addWidget(buttons)
    

    # Au début du fichier, ajouter les imports nécessaires


# Puis dans la méthode print_document :

    def print_document(self, printer):
        """Imprimer le document"""
        try:
            painter = QPainter(printer)
            
            # CORRECTION : Utiliser QPageSize pour définir la taille A4
            a4_size = QPageSize(QPageSize.A4)
            printer.setPageSize(a4_size)
            
            # Configuration de la qualité d'impression
            printer.setResolution(300)
            
            # CORRECTION : Utiliser QPageLayout pour les marges
            printer.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Millimeter)
            
            # Calculer la zone d'impression
            page_rect = printer.pageRect(QPrinter.DevicePixel)
            width = page_rect.width()
            height = page_rect.height()
            
            # Définir la police
            font = QFont()
            font.setFamily("Segoe UI")
            font.setPointSize(10)
            painter.setFont(font)
            
            # Coordonnées de départ
            x = 50
            y = 50
            line_height = 20
            
            # En-tête
            header_font = QFont()
            header_font.setFamily("Segoe UI")
            header_font.setPointSize(14)
            header_font.setBold(True)
            painter.setFont(header_font)
            
            painter.drawText(x, y, "FACTURE / RECU DE VENTE")
            y += line_height + 10
            
            # Informations de la vente
            font.setPointSize(10)
            font.setBold(False)
            painter.setFont(font)
            
            painter.drawText(x, y, f"N° Vente: {self.sale_data['sale_number']}")
            y += line_height
            
            painter.drawText(x, y, f"Date: {self.sale_data['date']}")
            y += line_height
            
            painter.drawText(x, y, f"Client: {self.sale_data['customer']}")
            y += line_height
            
            painter.drawText(x, y, f"Caissier: {self.sale_data['cashier']}")
            y += line_height * 2
            
            # Ligne séparatrice
            painter.drawLine(x, y, width - 50, y)
            y += line_height
            
            # Articles
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(x, y, "Articles")
            painter.drawText(width - 200, y, "Quantité")
            painter.drawText(width - 100, y, "Prix")
            y += line_height
            
            font.setBold(False)
            painter.setFont(font)
            
            # Ici vous devriez récupérer les articles de la vente depuis la base de données
            # Pour l'exemple, on affiche juste un résumé
            painter.drawText(x, y, f"{self.sale_data['items_count']} article(s)")
            painter.drawText(width - 100, y, f"{self.sale_data['total']:,.2f} FCFA")
            y += line_height * 2
            
            # Total
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(x, y, "TOTAL:")
            painter.drawText(width - 100, y, f"{self.sale_data['total']:,.2f} FCFA")
            y += line_height * 2
            
            # Pied de page
            font.setPointSize(8)
            font.setBold(False)
            painter.setFont(font)
            painter.drawText(x, y, "Merci pour votre achat !")
            y += line_height
            painter.drawText(x, y, f"Imprimé le: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
            
            painter.end()
            
            QMessageBox.information(self, "Impression", "Document envoyé à l'imprimante!")
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur d'impression", f"Erreur: {str(e)}")
            print(f"Erreur d'impression: {e}")
            import traceback
            traceback.print_exc()

    def adjust_html_for_display(self, html):
        """Ajuste le HTML pour l'affichage dans le preview"""
        css = """
        <style>
            body {
                font-family: 'Arial', sans-serif;
                font-size: 10pt;
                margin: 20px;
                padding: 20px;
                background-color: white;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                font-size: 9pt;
            }
            th, td {
                padding: 6px 4px;
                border: 1px solid #333;
            }
            .company-info {
                text-align: center;
                font-weight: bold;
                font-size: 11pt;
                margin-bottom: 15px;
            }
            .invoice-title {
                text-align: center;
                font-size: 12pt;
                font-weight: bold;
                margin: 10px 0;
            }
        </style>
        """
        
        if '<head>' in html:
            html = html.replace('<head>', f'<head>{css}')
        else:
            html = f'<html><head>{css}</head><body>{html}</body></html>'
        
        return html
    
    def adjust_html_for_printing(self, html):
        """Ajuste le HTML pour optimiser l'impression sur page A4"""
        css = """
        <style>
            @page {
                margin: 0.5cm;
                size: A4 portrait;
            }
            body {
                margin: 0;
                padding: 0;
                width: 100%;
                font-family: 'Arial', sans-serif;
                font-size: 10pt;
            }
            .page-container {
                width: 100%;
                max-width: 100%;
                padding: 10px;
                box-sizing: border-box;
            }
            table {
                width: 100%;
                max-width: 100%;
                border-collapse: collapse;
                table-layout: fixed;
                font-size: 9pt;
            }
            th, td {
                padding: 6px 4px;
                border: 1px solid #333;
                word-wrap: break-word;
                overflow-wrap: break-word;
            }
            .header, .footer {
                width: 100%;
                text-align: center;
            }
            .totals-table {
                width: 100%;
                margin-top: 15px;
            }
            .company-info {
                width: 100%;
                text-align: center;
                margin-bottom: 15px;
                font-weight: bold;
                font-size: 11pt;
            }
            .invoice-title {
                width: 100%;
                text-align: center;
                font-size: 12pt;
                font-weight: bold;
                margin: 10px 0;
            }
        </style>
        """
        
        if '<head>' in html:
            html = html.replace('<head>', f'<head>{css}')
        else:
            html = f'<html><head>{css}</head><body><div class="page-container">{html}</div></body></html>'
        
        return html
    
    def print_document(self):
        """Imprimer le document"""
        try:
            # Configuration de l'imprimante
            printer = QPrinter(QPrinter.HighResolution)
            
            # Définir le format A4
            page_size = QPageSize(QPageSize.A4)
            printer.setPageSize(page_size)
            
            # Définir les marges
            margins = QMarginsF(5, 5, 5, 5)  # 5mm de marge de chaque côté
            printer.setPageMargins(margins, QPageLayout.Millimeter)
            
            # CORRECTION : Définir l'orientation portrait avec QPageLayout
            printer.setPageOrientation(QPageLayout.Portrait)
            
            # Ajuster le HTML pour l'impression
            adjusted_html = self.adjust_html_for_printing(self.html_content)
            
            # Afficher le dialogue d'impression
            print_dialog = QPrintDialog(printer, self)
            if print_dialog.exec() == QPrintDialog.Accepted:
                # Créer le document
                doc = QTextDocument()
                doc.setHtml(adjusted_html)
                
                # Ajuster la largeur du texte à la largeur de la page
                page_width = printer.pageRect(QPrinter.DevicePixel).width()
                doc.setTextWidth(page_width)
                
                # Imprimer
                doc.print_(printer)
                
                QMessageBox.information(self, "Impression", "Impression lancée")
            
        except Exception as e:
            logger.error(f"Erreur impression: {e}")
            QMessageBox.critical(self, "Erreur", f"Erreur: {str(e)}")


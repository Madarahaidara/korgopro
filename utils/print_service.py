"""
Module d'impression pour l'application Korgo
Génération de PDF et impression de factures/tickets
"""

from __future__ import annotations

import os
import tempfile
import platform
import subprocess
import time
import html
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Callable
import logging
import threading

# ReportLab pour génération PDF
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter, portrait
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm, inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

# SQLAlchemy
from sqlalchemy.orm import Session, joinedload

# Modèles (imports avec TYPE_CHECKING pour éviter les imports circulaires)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.models.sale_models import Sale, SaleItem
    from core.models.stock_models import Product
    from core.models.customer import Customer

# Configuration
logger = logging.getLogger(__name__)

# Import conditionnel pour les boîtes de dialogue
tk = None
filedialog = None
simpledialog = None
ttk = None
try:
    import tkinter as tk
    from tkinter import filedialog, simpledialog, ttk
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False
    logger.warning("Tkinter non disponible, les boîtes de dialogue seront désactivées")

# Try PyQt6 first, fallback to PyQt5
QT_AVAILABLE = False
QT_VERSION = None
try:
    from PyQt6.QtWidgets import (QApplication, QFileDialog, QProgressDialog,
                                  QMessageBox, QVBoxLayout, QLabel, QProgressBar, QDialog)
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QRunnable, QThreadPool
    QT_AVAILABLE = True
    QT_VERSION = 6
except Exception:
    try:
        from PyQt5.QtWidgets import (QApplication, QFileDialog, QProgressDialog,
                                     QMessageBox, QVBoxLayout, QLabel, QProgressBar, QDialog)
        from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QRunnable, QThreadPool
        QT_AVAILABLE = True
        QT_VERSION = 5
    except Exception:
        QT_AVAILABLE = False

# Import du gestionnaire de paramètres
from utils.settings_manager import SettingsManager


class PrintService:
    """Wrapper pour les services d'impression"""
    
    def __init__(self):
        from core.database import SessionLocal
        self.session = SessionLocal()
        self.printer = InvoicePrinter(self.session)
    
    def close(self):
        """Ferme la session"""
        if hasattr(self, 'session'):
            self.session.close()


class ProgressDialog:
    """Classe pour gérer les barres de progression"""
    
    def __init__(self, title="Progression", message="Veuillez patienter...", 
                 maximum=100, parent=None):
        self.title = title
        self.message = message
        self.maximum = maximum
        self.parent = parent
        self.dialog = None
        self.is_cancelled = False
        
    def show(self):
        """Affiche la boîte de dialogue de progression"""
        if not GUI_AVAILABLE:
            print(f"{self.title}: {self.message}")
            return
        
        try:
            self.root = tk.Tk()
            self.root.title(self.title)
            self.root.geometry("400x150")
            self.root.resizable(False, False)
            
            self.root.update_idletasks()
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            x = (self.root.winfo_screenwidth() // 2) - (width // 2)
            y = (self.root.winfo_screenheight() // 2) - (height // 2)
            self.root.geometry(f'{width}x{height}+{x}+{y}')
            
            label = tk.Label(self.root, text=self.message, font=("Arial", 10))
            label.pack(pady=20)
            
            self.progress = ttk.Progressbar(
                self.root, 
                orient="horizontal",
                length=300,
                mode="determinate",
                maximum=self.maximum
            )
            self.progress.pack(pady=10)
            
            self.percent_label = tk.Label(self.root, text="0%", font=("Arial", 9))
            self.percent_label.pack()
            
            self.cancel_button = tk.Button(
                self.root, 
                text="Annuler", 
                command=self.cancel,
                width=10
            )
            self.cancel_button.pack(pady=10)
            
            self.root.update()
            
        except Exception as e:
            logger.error(f"Erreur création dialogue progression: {e}")
    
    def update(self, value, message=None):
        """Met à jour la progression"""
        if hasattr(self, 'progress'):
            self.progress['value'] = value
            if message:
                for widget in self.root.winfo_children():
                    if isinstance(widget, tk.Label) and widget.cget("font") == ("Arial", 10):
                        widget.config(text=message)
                        break
            
            percent = int((value / self.maximum) * 100)
            self.percent_label.config(text=f"{percent}%")
            
            self.root.update()
    
    def close(self):
        """Ferme la boîte de dialogue"""
        if hasattr(self, 'root'):
            self.root.destroy()
    
    def cancel(self):
        """Annule l'opération"""
        self.is_cancelled = True
        self.cancel_button.config(text="Annulation...", state="disabled")
        self.root.update()


class InvoicePrinter:
    """Service de génération de factures/tickets style proforma"""
    
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.default_directories = {
            'invoices': os.path.join(os.path.expanduser('~'), 'Documents', 'Korgo', 'Factures'),
            'receipts': os.path.join(os.path.expanduser('~'), 'Documents', 'Korgo', 'Tickets'),
            'batch': os.path.join(os.path.expanduser('~'), 'Documents', 'Korgo', 'Batch'),
            'html': os.path.join(os.path.expanduser('~'), 'Documents', 'Korgo', 'HTML')
        }
        
        # Récupérer les paramètres de l'entreprise
        self.settings_manager = SettingsManager()
        self._load_settings()
        
        # Créer les répertoires par défaut
        self._create_default_directories()
    
    def _load_settings(self):
        """Charge tous les paramètres de l'entreprise"""
        self.company_settings = self.settings_manager.get_company_info_for_invoice()
        
        # Informations générales
        self.CURRENCY = self.company_settings.get('currency', 'FCFA')
        self.logo_path = self.company_settings.get('company_logo', '')
        self.company_name = self.company_settings.get('company_name', 'MON ENTREPRISE')
        self.company_phone = self.company_settings.get('company_phone', '+226 XX XX XX XX')
        self.company_email = self.company_settings.get('company_email', 'contact@entreprise.com')
        self.company_address = self.company_settings.get('company_address', 'Ouagadougou')
        self.invoice_footer = self.company_settings.get('invoice_footer', 'Merci de votre confiance')
        
        # Informations légales
        self.company_ifu = self.company_settings.get('company_ifu', '')
        self.company_rccm = self.company_settings.get('company_rccm', '')
        self.company_po_box = self.company_settings.get('company_po_box', '')
        
        logger.info(f"Paramètres chargés - IFU: {self.company_ifu}, RCCM: {self.company_rccm}, BP: {self.company_po_box}")
    
    def _create_default_directories(self):
        """Crée les répertoires par défaut s'ils n'existent pas"""
        for directory in self.default_directories.values():
            try:
                os.makedirs(directory, exist_ok=True)
            except Exception as e:
                logger.error(f"Erreur création répertoire {directory}: {e}")
    
    def _load_logo(self):
        """Charge le logo depuis le chemin configuré"""
        logo_path = self.logo_path
        if logo_path and os.path.exists(logo_path):
            try:
                return logo_path
            except Exception as e:
                logger.error(f"Erreur chargement logo: {e}")
                return None
        return None
    
    def get_sale_details(self, sale_id: int) -> Optional['Sale']:
        """Récupère les détails d'une vente"""
        try:
            from core.models.sale_models import Sale, SaleItem
            from core.models.customer import Customer

            return self.db_session.query(Sale)\
                .options(
                    joinedload(Sale.items).joinedload(SaleItem.product),
                    joinedload(Sale.customer),
                    joinedload(Sale.cashier)
                )\
                .filter(Sale.id == sale_id)\
                .first()
        except Exception as e:
            logger.error(f"Erreur récupération vente {sale_id}: {e}")
            return None
    
    def _clean_text(self, text: str) -> str:
        """Nettoie le texte en supprimant les balises HTML"""
        if not text:
            return ""
        text = html.unescape(text)
        import re
        text = re.sub(r'<[^>]+>', '', text)
        return text
    
    def _number_to_words(self, number: float, currency: str = "FCFA") -> str:
        """Convertit un nombre en toutes lettres"""
        if number == 0:
            if currency.upper() in ["FCFA", "XAF", "XOF"]:
                return "zéro FCFA"
            elif currency.upper() in ["EUR", "EURO"]:
                return "zéro euro"
            elif currency.upper() in ["USD", "DOLLAR"]:
                return "zéro dollar"
            else:
                return f"zéro {currency}"
        
        integer_part = int(number)
        decimal_part = int(round((number - integer_part) * 100))
        
        units = {
            0: "zéro", 1: "un", 2: "deux", 3: "trois", 4: "quatre",
            5: "cinq", 6: "six", 7: "sept", 8: "huit", 9: "neuf",
            10: "dix", 11: "onze", 12: "douze", 13: "treize", 14: "quatorze",
            15: "quinze", 16: "seize", 17: "dix-sept", 18: "dix-huit", 19: "dix-neuf"
        }
        
        tens = {
            20: "vingt", 30: "trente", 40: "quarante", 50: "cinquante",
            60: "soixante", 70: "soixante-dix", 80: "quatre-vingt", 90: "quatre-vingt-dix"
        }
        
        def _convert_hundreds(n: int) -> str:
            if n == 0:
                return ""
            
            result = ""
            
            if n >= 100:
                hundreds = n // 100
                remainder = n % 100
                
                if hundreds == 1:
                    result += "cent"
                else:
                    result += units[hundreds] + " cent"
                
                if remainder == 0:
                    if hundreds > 1:
                        result += "s"
                    return result
                
                result += " "
            
            remainder = n % 100
            
            if remainder == 0:
                return result
            
            if remainder <= 16:
                result += units[remainder]
            elif remainder < 20:
                result += units[10] + "-" + units[remainder - 10]
            else:
                tens_val = (remainder // 10) * 10
                units_val = remainder % 10
                
                if units_val == 0:
                    if tens_val == 70:
                        result += "soixante-dix"
                    elif tens_val == 90:
                        result += "quatre-vingt-dix"
                    else:
                        result += tens[tens_val]
                elif tens_val == 70:
                    result += "soixante-" + units[10 + units_val]
                elif tens_val == 90:
                    result += "quatre-vingt-" + units[10 + units_val]
                else:
                    if units_val == 1:
                        result += tens[tens_val] + "-et-un"
                    else:
                        result += tens[tens_val] + "-" + units[units_val]
            
            return result
        
        def _convert_chunk(n: int, index: int) -> str:
            if n == 0:
                return ""
            
            chunk_words = _convert_hundreds(n)
            
            if index == 0:
                return chunk_words
            elif index == 1:
                if n == 1:
                    return "mille"
                else:
                    return chunk_words + " mille"
            else:
                names = ["", "", "million", "milliard", "billion", "trillion"]
                plural = "s" if n > 1 else ""
                return chunk_words + " " + names[index] + plural
        
        if integer_part == 0:
            integer_words = "zéro"
        else:
            chunks = []
            num = integer_part
            chunk_index = 0
            
            while num > 0:
                chunk = num % 1000
                if chunk > 0:
                    chunk_words = _convert_chunk(chunk, chunk_index)
                    chunks.append(chunk_words)
                num //= 1000
                chunk_index += 1
            
            chunks.reverse()
            integer_words = " ".join(chunks)
        
        if decimal_part > 0:
            if currency.upper() in ["FCFA", "XAF", "XOF"]:
                subunit_name = "centimes"
            elif currency.upper() in ["EUR", "EURO"]:
                subunit_name = "centimes"
            elif currency.upper() in ["USD", "DOLLAR"]:
                subunit_name = "cents"
            elif currency.upper() in ["GBP", "LIVRE"]:
                subunit_name = "pence"
            else:
                subunit_name = "centimes"
            
            decimal_words = _convert_hundreds(decimal_part)
            if decimal_words:
                result = f"{integer_words} {currency} et {decimal_words} {subunit_name}"
            else:
                result = f"{integer_words} {currency}"
        else:
            if integer_part > 1:
                if currency.upper() in ["FCFA", "XAF", "XOF"]:
                    currency_word = "FCFA"
                elif currency.upper() in ["EUR", "EURO"]:
                    currency_word = "euros"
                elif currency.upper() in ["USD", "DOLLAR"]:
                    currency_word = "dollars"
                elif currency.upper() in ["GBP", "LIVRE"]:
                    currency_word = "livres"
                else:
                    currency_word = currency
            else:
                if currency.upper() in ["EUR", "EURO"]:
                    currency_word = "euro"
                elif currency.upper() in ["USD", "DOLLAR"]:
                    currency_word = "dollar"
                elif currency.upper() in ["GBP", "LIVRE"]:
                    currency_word = "livre"
                else:
                    currency_word = currency
            
            result = f"{integer_words} {currency_word}"
        
        return result
    
    def select_directory_dialog(self, title: str = "Sélectionner un dossier", 
                               initial_dir: str = None) -> Optional[str]:
        """Ouvre une boîte de dialogue pour sélectionner un dossier"""
        if not GUI_AVAILABLE:
            return None
        
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            
            if initial_dir is None:
                initial_dir = os.path.expanduser('~')
            
            directory = filedialog.askdirectory(
                title=title,
                initialdir=initial_dir,
                mustexist=False
            )
            
            root.destroy()
            
            if directory:
                os.makedirs(directory, exist_ok=True)
                return directory
            
            return None
            
        except Exception as e:
            logger.error(f"Erreur boîte de dialogue dossier: {e}")
            return None
    
    def select_save_path_dialog(self, title: str = "Enregistrer sous", 
                               initial_dir: str = None, 
                               default_filename: str = "facture.pdf",
                               file_types: List[Tuple[str, str]] = None) -> Optional[str]:
        """Ouvre une boîte de dialogue pour sélectionner un emplacement de sauvegarde"""
        if not GUI_AVAILABLE:
            return None
        
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            
            if initial_dir is None:
                initial_dir = os.path.expanduser('~')
            
            if file_types is None:
                file_types = [("Fichiers PDF", "*.pdf"), ("Tous les fichiers", "*.*")]
            
            file_path = filedialog.asksaveasfilename(
                title=title,
                initialdir=initial_dir,
                initialfile=default_filename,
                defaultextension=".pdf",
                filetypes=file_types
            )
            
            root.destroy()
            return file_path if file_path else None
            
        except Exception as e:
            logger.error(f"Erreur boîte de dialogue sauvegarde: {e}")
            return None
    
    def generate_invoice(self, sale_id: int, output_path: str = None, 
                        output_dir: str = None, filename: str = None,
                        ask_location: bool = True,
                        show_progress: bool = True) -> Tuple[bool, str, str]:
        """Génère une facture au format PDF style proforma"""
        self._load_settings()
        
        progress_dialog = None
        try:
            if show_progress:
                progress_dialog = ProgressDialog(
                    title="Génération de facture",
                    message="Préparation de la facture...",
                    maximum=100
                )
                progress_dialog.show()
                progress_dialog.update(10, "Récupération des données de vente...")
            
            sale = self.get_sale_details(sale_id)
            if not sale:
                if progress_dialog:
                    progress_dialog.close()
                return False, "Vente non trouvée", ""
            
            if progress_dialog:
                progress_dialog.update(30, "Préparation du chemin de sauvegarde...")
            
            if ask_location:
                if progress_dialog:
                    progress_dialog.update(40, "Ouverture de la boîte de dialogue...")
                result = self._generate_invoice_with_location_dialog(sale, progress_dialog)
                if progress_dialog:
                    progress_dialog.close()
                return result
            
            file_path = self._resolve_output_path(
                output_path=output_path,
                output_dir=output_dir,
                filename=filename,
                default_name=f"Facture_{sale.sale_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                default_category='invoices'
            )
            
            if progress_dialog:
                progress_dialog.update(50, "Création du document PDF...")
            
            doc = SimpleDocTemplate(
                file_path,
                pagesize=A4,
                rightMargin=1*cm,
                leftMargin=1*cm,
                topMargin=1*cm,
                bottomMargin=1*cm
            )
            
            story = []
            
            # En-tête style proforma
            story.extend(self._create_header(sale))
            
            if progress_dialog:
                progress_dialog.update(60, "Ajout des informations client...")
            
            # Informations client style proforma
            story.extend(self._create_info_section(sale))
            
            if progress_dialog:
                progress_dialog.update(70, "Création du tableau des articles...")
            
            # Tableau des articles style proforma
            story.extend(self._create_items_table(sale, doc.width))
            
            if progress_dialog:
                progress_dialog.update(80, "Calcul des totaux...")
            
            # Totaux et signature style proforma
            story.extend(self._create_totals_section(sale))
            
            # Pied de page avec informations légales
            story.extend(self._create_footer())
            
            if progress_dialog:
                progress_dialog.update(90, "Génération du fichier PDF...")
            
            doc.build(story)
            
            if progress_dialog:
                progress_dialog.update(100, "Facture générée avec succès !")
                time.sleep(0.5)
                progress_dialog.close()
            
            return True, f"Facture générée avec succès: {file_path}", file_path
            
        except Exception as e:
            logger.error(f"Erreur génération facture: {e}")
            if progress_dialog:
                progress_dialog.close()
            return False, f"Erreur: {str(e)}", ""
    
    def _generate_invoice_with_location_dialog(self, sale: 'Sale', 
                                             progress_dialog: ProgressDialog = None) -> Tuple[bool, str, str]:
        """Génère une facture en demandant l'emplacement"""
        default_filename = f"Facture_{sale.sale_number}_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        file_path = None
        
        if GUI_AVAILABLE:
            if progress_dialog:
                progress_dialog.update(50, "En attente de la sélection de l'emplacement...")
            
            file_path = self.select_save_path_dialog(
                title=f"Enregistrer la facture {sale.sale_number}",
                initial_dir=self.default_directories['invoices'],
                default_filename=default_filename,
                file_types=[("Fichiers PDF", "*.pdf"), ("Tous les fichiers", "*.*")]
            )
        
        if not file_path:
            output_dir = self.default_directories['invoices']
            file_path = os.path.join(output_dir, default_filename)
        
        return self._generate_invoice_file(sale, file_path, progress_dialog)
    
    def _generate_invoice_file(self, sale: 'Sale', file_path: str, 
                             progress_dialog: ProgressDialog = None) -> Tuple[bool, str, str]:
        """Génère le fichier PDF de facture"""
        try:
            if progress_dialog:
                progress_dialog.update(60, "Création du document PDF...")
            
            doc = SimpleDocTemplate(
                file_path,
                pagesize=A4,
                rightMargin=1*cm,
                leftMargin=1*cm,
                topMargin=1*cm,
                bottomMargin=1*cm
            )
            
            story = []
            
            story.extend(self._create_header(sale))
            
            if progress_dialog:
                progress_dialog.update(70, "Ajout des informations client...")
            
            story.extend(self._create_info_section(sale))
            
            if progress_dialog:
                progress_dialog.update(75, "Création du tableau des articles...")
            
            story.extend(self._create_items_table(sale, doc.width))
            
            if progress_dialog:
                progress_dialog.update(85, "Calcul des totaux...")
            
            story.extend(self._create_totals_section(sale))
            story.extend(self._create_footer())
            
            if progress_dialog:
                progress_dialog.update(90, "Génération du fichier PDF...")
            
            doc.build(story)
            
            if progress_dialog:
                progress_dialog.update(100, "Facture générée avec succès !")
                time.sleep(0.5)
            
            return True, f"Facture générée avec succès: {file_path}", file_path
            
        except Exception as e:
            logger.error(f"Erreur génération fichier facture: {e}")
            return False, f"Erreur: {str(e)}", ""
    
    def generate_receipt(self, sale_id: int, output_path: str = None,
                        output_dir: str = None, filename: str = None,
                        ask_location: bool = True,
                        show_progress: bool = False) -> Tuple[bool, str, str]:
        """Génère un ticket de caisse simple"""
        self._load_settings()
        
        progress_dialog = None
        try:
            if show_progress:
                progress_dialog = ProgressDialog(
                    title="Génération de ticket",
                    message="Préparation du ticket...",
                    maximum=100
                )
                progress_dialog.show()
                progress_dialog.update(10, "Récupération des données de vente...")
            
            sale = self.get_sale_details(sale_id)
            if not sale:
                if progress_dialog:
                    progress_dialog.close()
                return False, "Vente non trouvée", ""
            
            if progress_dialog:
                progress_dialog.update(30, "Préparation du chemin de sauvegarde...")
            
            if ask_location:
                if progress_dialog:
                    progress_dialog.update(40, "Ouverture de la boîte de dialogue...")
                result = self._generate_receipt_with_location_dialog(sale, progress_dialog)
                if progress_dialog:
                    progress_dialog.close()
                return result
            
            file_path = self._resolve_output_path(
                output_path=output_path,
                output_dir=output_dir,
                filename=filename,
                default_name=f"Ticket_{sale.sale_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                default_category='receipts'
            )
            
            return self._generate_receipt_file(sale, file_path, progress_dialog)
            
        except Exception as e:
            logger.error(f"Erreur génération ticket: {e}")
            if progress_dialog:
                progress_dialog.close()
            return False, f"Erreur: {str(e)}", ""
    
    def _generate_receipt_with_location_dialog(self, sale: 'Sale', 
                                             progress_dialog: ProgressDialog = None) -> Tuple[bool, str, str]:
        """Génère un ticket en demandant l'emplacement"""
        default_filename = f"Ticket_{sale.sale_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        file_path = None
        
        if GUI_AVAILABLE:
            if progress_dialog:
                progress_dialog.update(50, "En attente de la sélection de l'emplacement...")
            
            file_path = self.select_save_path_dialog(
                title=f"Enregistrer le ticket {sale.sale_number}",
                initial_dir=self.default_directories['receipts'],
                default_filename=default_filename,
                file_types=[("Fichiers PDF", "*.pdf"), ("Tous les fichiers", "*.*")]
            )
        
        if not file_path:
            output_dir = self.default_directories['receipts']
            file_path = os.path.join(output_dir, default_filename)
        
        return self._generate_receipt_file(sale, file_path, progress_dialog)
    
    def _generate_receipt_file(self, sale: 'Sale', file_path: str, 
                             progress_dialog: ProgressDialog = None) -> Tuple[bool, str, str]:
        """Génère le fichier PDF de ticket"""
        try:
            if progress_dialog:
                progress_dialog.update(60, "Création du document ticket...")
            
            doc = SimpleDocTemplate(
                file_path,
                pagesize=(58*mm, 200*mm),
                rightMargin=5,
                leftMargin=5,
                topMargin=10,
                bottomMargin=10
            )
            
            story = []
            
            company_name = self.company_name or 'KORGO STORE'
            story.append(Paragraph(company_name, self._get_style('Heading2')))
            
            legal_info = []
            if self.company_po_box:
                legal_info.append(f"BP: {self.company_po_box}")
            if self.company_ifu:
                legal_info.append(f"IFU: {self.company_ifu}")
            if self.company_rccm:
                legal_info.append(f"RCCM: {self.company_rccm}")
            
            if legal_info:
                story.append(Paragraph(" | ".join(legal_info), self._get_style('Normal')))
            
            if self.company_phone:
                story.append(Paragraph(f"Tél: {self.company_phone}", self._get_style('Normal')))
            
            if self.company_address:
                story.append(Paragraph(self.company_address, self._get_style('Normal')))
            
            story.append(Paragraph("-" * 30, self._get_style('Normal')))
            
            info_lines = [
                f"Ticket: {sale.sale_number}",
                f"Date: {sale.sale_date.strftime('%d/%m/%Y %H:%M')}",
                f"Vendeur: {sale.cashier.username if sale.cashier else '-'}"
            ]
            
            if sale.customer:
                customer_name = self._clean_text(f"{sale.customer.first_name} {sale.customer.last_name}")
                info_lines.append(f"Client: {customer_name}")
            
            for line in info_lines:
                story.append(Paragraph(line, self._get_style('Normal')))
            
            story.append(Paragraph("-" * 30, self._get_style('Normal')))
            
            if progress_dialog:
                progress_dialog.update(70, "Ajout des articles...")
            
            for item in sale.items:
                product_name = item.product.name if item.product else "Produit"
                product_name = self._clean_text(product_name)
                if len(product_name) > 20:
                    product_name = product_name[:20] + "..."
                
                item_text = f"{product_name} {item.quantity} x {item.unit_price:,.0f}"
                story.append(Paragraph(item_text, self._get_style('Normal')))
                
                if item.discount_percent > 0:
                    story.append(Paragraph(f"  Remise: {item.discount_percent}%", 
                                         self._get_style('Normal')))
            
            story.append(Paragraph("-" * 30, self._get_style('Normal')))
            
            if progress_dialog:
                progress_dialog.update(80, "Calcul des totaux...")
            
            totals = [
                f"Sous-total: {sale.subtotal:,.0f} {self.CURRENCY}",
                f"Remise: {sale.discount_amount:,.0f} {self.CURRENCY}",
                f"TVA: {sale.tax_amount:,.0f} {self.CURRENCY}",
                f"TOTAL: {sale.total_amount:,.0f} {self.CURRENCY}",
                f"Payé: {sale.amount_paid:,.0f} {self.CURRENCY}",
            ]
            
            if sale.change_amount > 0:
                totals.append(f"Monnaie: {sale.change_amount:,.0f} {self.CURRENCY}")
            
            for line in totals:
                story.append(Paragraph(line, self._get_style('Normal')))
            
            story.append(Paragraph("=" * 30, self._get_style('Normal')))
            
            total_in_words = self._number_to_words(sale.total_amount, self.CURRENCY)
            story.append(Paragraph(f"Arrêté à: {total_in_words}", self._get_style('Normal')))
            story.append(Paragraph("=" * 30, self._get_style('Normal')))
            
            footer_text = self.invoice_footer or 'Merci de votre visite !'
            story.append(Paragraph(footer_text, self._get_style('Normal')))
            
            if progress_dialog:
                progress_dialog.update(90, "Génération du fichier PDF...")
            
            doc.build(story)
            
            if progress_dialog:
                progress_dialog.update(100, "Ticket généré avec succès !")
                time.sleep(0.5)
                progress_dialog.close()
            
            return True, f"Ticket généré avec succès: {file_path}", file_path
            
        except Exception as e:
            logger.error(f"Erreur génération fichier ticket: {e}")
            if progress_dialog:
                progress_dialog.close()
            return False, f"Erreur: {str(e)}", ""
    
    def _resolve_output_path(self, output_path: str = None, output_dir: str = None,
                           filename: str = None, default_name: str = None,
                           default_category: str = 'invoices') -> str:
        """Résout le chemin de sortie"""
        if output_path:
            file_path = output_path
        else:
            if output_dir:
                target_dir = output_dir
            else:
                target_dir = self.default_directories.get(default_category, tempfile.gettempdir())
            
            os.makedirs(target_dir, exist_ok=True)
            
            if filename:
                if not filename.endswith('.pdf') and not filename.endswith('.html'):
                    filename += '.pdf'
                target_filename = filename
            else:
                target_filename = default_name or f"document_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            
            file_path = os.path.join(target_dir, target_filename)
        
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        return file_path
    
    def generate_batch_invoices(self, sale_ids: List[int], output_dir: str = None, 
                               filename_pattern: str = "Facture_{sale_number}_{date}",
                               ask_location: bool = False,
                               show_progress: bool = True) -> Dict[int, Tuple[bool, str, str]]:
        """Génère plusieurs factures en batch"""
        self._load_settings()
        
        progress_dialog = None
        try:
            if show_progress:
                progress_dialog = ProgressDialog(
                    title="Génération en lot",
                    message="Préparation de la génération en lot...",
                    maximum=len(sale_ids) * 100
                )
                progress_dialog.show()
            
            if ask_location:
                if progress_dialog:
                    progress_dialog.update(5, "Sélection du dossier de destination...")
                
                selected_dir = self.select_directory_dialog(
                    title="Sélectionner le dossier pour les factures batch",
                    initial_dir=self.default_directories['batch']
                )
                
                if selected_dir:
                    output_dir = selected_dir
                else:
                    output_dir = self.default_directories['batch']
                    if progress_dialog:
                        progress_dialog.update(10, "Utilisation du dossier par défaut...")
            
            if not output_dir:
                output_dir = self.default_directories['batch']
            
            results = {}
            total_invoices = len(sale_ids)
            
            for index, sale_id in enumerate(sale_ids):
                if progress_dialog and progress_dialog.is_cancelled:
                    logger.info("Génération en lot annulée par l'utilisateur")
                    break
                
                base_progress = index * 100
                
                if progress_dialog:
                    progress_dialog.update(
                        base_progress + 10,
                        f"Récupération de la vente {index+1}/{total_invoices}..."
                    )
                
                sale = self.get_sale_details(sale_id)
                if not sale:
                    results[sale_id] = (False, "Vente non trouvée", "")
                    if progress_dialog:
                        progress_dialog.update(base_progress + 100)
                    continue
                
                now = datetime.now()
                filename = filename_pattern.format(
                    sale_number=sale.sale_number,
                    date=now.strftime('%Y%m%d'),
                    time=now.strftime('%H%M%S'),
                    datetime=now.strftime('%Y%m%d_%H%M%S')
                ) + ".pdf"
                
                if progress_dialog:
                    progress_dialog.update(
                        base_progress + 30,
                        f"Génération de la facture {sale.sale_number}..."
                    )
                
                success, message, file_path = self.generate_invoice(
                    sale_id, 
                    output_dir=output_dir,
                    filename=filename,
                    show_progress=False
                )
                
                results[sale_id] = (success, message, file_path)
                
                if progress_dialog:
                    progress_dialog.update(
                        base_progress + 100,
                        f"Facture {index+1}/{total_invoices} terminée"
                    )
                
                time.sleep(0.1)
            
            if progress_dialog:
                if progress_dialog.is_cancelled:
                    progress_dialog.update(
                        progress_dialog.maximum,
                        "Génération annulée par l'utilisateur"
                    )
                    time.sleep(1)
                else:
                    progress_dialog.update(
                        progress_dialog.maximum,
                        f"Génération terminée: {len(results)} factures créées"
                    )
                    time.sleep(1.5)
                progress_dialog.close()
            
            return results
            
        except Exception as e:
            logger.error(f"Erreur génération batch: {e}")
            if progress_dialog:
                progress_dialog.close()
            return {}
    
    def print_file(self, file_path: str, show_progress: bool = False) -> Tuple[bool, str]:
        """Imprime un fichier PDF avec l'imprimante par défaut"""
        progress_dialog = None
        try:
            if show_progress:
                progress_dialog = ProgressDialog(
                    title="Impression",
                    message="Lancement de l'impression...",
                    maximum=100
                )
                progress_dialog.show()
                progress_dialog.update(30)
            
            if not os.path.exists(file_path):
                if progress_dialog:
                    progress_dialog.close()
                return False, f"Fichier non trouvé: {file_path}"
            
            system = platform.system()
            
            if progress_dialog:
                progress_dialog.update(60, "Envoi à l'imprimante...")
            
            if system == 'Windows':
                os.startfile(file_path, "print")
                result_message = "Impression lancée sur Windows"
            elif system == 'Darwin':
                subprocess.run(['lp', file_path])
                result_message = "Impression lancée sur macOS"
            else:
                subprocess.run(['lp', file_path])
                result_message = "Impression lancée sur Linux"
            
            if progress_dialog:
                progress_dialog.update(100, "Impression lancée avec succès !")
                time.sleep(1)
                progress_dialog.close()
            
            return True, result_message
                
        except Exception as e:
            logger.error(f"Erreur impression: {e}")
            if progress_dialog:
                progress_dialog.close()
            return False, f"Erreur: {str(e)}"
    
    def open_file(self, file_path: str, show_progress: bool = False) -> Tuple[bool, str]:
        """Ouvre un fichier avec l'application par défaut"""
        progress_dialog = None
        try:
            if show_progress:
                progress_dialog = ProgressDialog(
                    title="Ouverture de fichier",
                    message="Ouverture du fichier...",
                    maximum=100
                )
                progress_dialog.show()
                progress_dialog.update(30)
            
            if not os.path.exists(file_path):
                if progress_dialog:
                    progress_dialog.close()
                return False, f"Fichier non trouvé: {file_path}"
            
            system = platform.system()
            
            if progress_dialog:
                progress_dialog.update(70, "Lancement de l'application...")
            
            if system == 'Windows':
                os.startfile(file_path)
            elif system == 'Darwin':
                subprocess.run(['open', file_path])
            else:
                subprocess.run(['xdg-open', file_path])
            
            if progress_dialog:
                progress_dialog.update(100, "Fichier ouvert avec succès !")
                time.sleep(1)
                progress_dialog.close()
            
            return True, f"Fichier ouvert: {file_path}"
            
        except Exception as e:
            logger.error(f"Erreur ouverture fichier: {e}")
            if progress_dialog:
                progress_dialog.close()
            return False, f"Erreur: {str(e)}"
    
    def save_html_invoice(self, sale_id: int, output_path: str = None,
                         output_dir: str = None, filename: str = None,
                         ask_location: bool = False,
                         show_progress: bool = False) -> Tuple[bool, str, str]:
        """Génère et sauvegarde une facture au format HTML style proforma"""
        self._load_settings()
        
        progress_dialog = None
        try:
            if show_progress:
                progress_dialog = ProgressDialog(
                    title="Génération HTML",
                    message="Préparation de la facture HTML...",
                    maximum=100
                )
                progress_dialog.show()
                progress_dialog.update(10, "Récupération des données de vente...")
            
            sale = self.get_sale_details(sale_id)
            if not sale:
                if progress_dialog:
                    progress_dialog.close()
                return False, "Vente non trouvée", ""
            
            if ask_location:
                if progress_dialog:
                    progress_dialog.update(30, "Ouverture de la boîte de dialogue...")
                
                default_filename = f"Facture_{sale.sale_number}_{datetime.now().strftime('%Y%m%d')}.html"
                
                file_path = None
                if GUI_AVAILABLE:
                    file_path = self.select_save_path_dialog(
                        title=f"Enregistrer la facture HTML {sale.sale_number}",
                        initial_dir=self.default_directories['html'],
                        default_filename=default_filename,
                        file_types=[("Fichiers HTML", "*.html"), ("Tous les fichiers", "*.*")]
                    )
                
                if not file_path:
                    output_dir = self.default_directories['html']
                    file_path = os.path.join(output_dir, default_filename)
                
                result = self._save_html_invoice_file(sale, file_path, progress_dialog)
                if progress_dialog:
                    progress_dialog.close()
                return result
            
            if progress_dialog:
                progress_dialog.update(40, "Génération du code HTML...")
            
            success, html_content, message = self.generate_html_invoice(sale_id)
            if not success:
                if progress_dialog:
                    progress_dialog.close()
                return False, message, ""
            
            file_path = self._resolve_output_path(
                output_path=output_path,
                output_dir=output_dir,
                filename=filename,
                default_name=f"Facture_{sale.sale_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                default_category='html'
            )
            
            if progress_dialog:
                progress_dialog.update(70, "Sauvegarde du fichier HTML...")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            if progress_dialog:
                progress_dialog.update(100, "Facture HTML sauvegardée avec succès !")
                time.sleep(0.5)
                progress_dialog.close()
            
            return True, f"Facture HTML sauvegardée: {file_path}", file_path
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde HTML: {e}")
            if progress_dialog:
                progress_dialog.close()
            return False, f"Erreur: {str(e)}", ""
    
    def _save_html_invoice_file(self, sale: 'Sale', file_path: str, 
                              progress_dialog: ProgressDialog = None) -> Tuple[bool, str, str]:
        """Sauvegarde une facture HTML dans un fichier"""
        try:
            if progress_dialog:
                progress_dialog.update(60, "Génération du code HTML...")
            
            html_content = self._create_html_template(sale)
            
            if progress_dialog:
                progress_dialog.update(80, "Sauvegarde du fichier HTML...")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            if progress_dialog:
                progress_dialog.update(100, "Facture HTML sauvegardée avec succès !")
                time.sleep(0.5)
            
            return True, f"Facture HTML sauvegardée: {file_path}", file_path
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde fichier HTML: {e}")
            return False, f"Erreur: {str(e)}", ""
    
    def get_default_directory(self, category: str = 'invoices') -> str:
        """Retourne le répertoire par défaut pour une catégorie"""
        return self.default_directories.get(category, tempfile.gettempdir())
    
    def set_default_directory(self, category: str, path: str) -> bool:
        """Définit un nouveau répertoire par défaut"""
        try:
            os.makedirs(path, exist_ok=True)
            self.default_directories[category] = path
            return True
        except Exception as e:
            logger.error(f"Erreur définition répertoire par défaut: {e}")
            return False
    
    def refresh_settings(self):
        """Rafraîchit les paramètres de l'entreprise"""
        self._load_settings()
        logger.info("Paramètres rafraîchis")
    
    # ============ MÉTHODES PRIVÉES POUR LA GÉNÉRATION PDF STYLE PROFORMA ============
    
    def _get_style(self, style_name: str):
        """Récupère un style"""
        styles = getSampleStyleSheet()
        
        if style_name == 'CustomTitle':
            if not hasattr(self, '_custom_title_style'):
                self._custom_title_style = ParagraphStyle(
                    'CustomTitle',
                    parent=styles['Heading1'],
                    fontSize=16,
                    textColor=colors.HexColor('#1e40af'),
                    spaceAfter=20
                )
            return self._custom_title_style
        
        if style_name == 'ProformaTitle':
            if not hasattr(self, '_proforma_title_style'):
                self._proforma_title_style = ParagraphStyle(
                    'ProformaTitle',
                    parent=styles['Heading1'],
                    fontSize=18,
                    textColor=colors.HexColor('#1a5490'),
                    alignment=1,  # Center
                    spaceAfter=10
                )
            return self._proforma_title_style
        
        return styles[style_name]
    
    def _create_header(self, sale: 'Sale') -> List:
        """Crée l'en-tête de la facture style proforma"""
        styles = getSampleStyleSheet()
        
        company_name = self.company_name or 'MON ENTREPRISE'
        company_address = self.company_address or 'Ouagadougou'
        company_phone = self.company_phone or '+226 XX XX XX XX'
        company_email = self.company_email or 'contact@entreprise.com'
        
        header_elements = []
        
        # Logo si disponible
        logo_path = self._load_logo()
        if logo_path:
            try:
                logo_img = Image(logo_path, width=50*mm, height=25*mm)
                header_elements.append(logo_img)
                header_elements.append(Spacer(1, 10))
            except Exception as e:
                logger.warning(f"Impossible d'ajouter le logo: {e}")
        
        # En-tête avec style proforma - nom de l'entreprise uniquement
        header_text = f"""
        <para alignment="center" spaceAfter="12">
        <font size="22" color="#1a5490"><b>{company_name}</b></font>
        </para>
        """
        
        header_elements.append(Paragraph(header_text, styles['Normal']))
        header_elements.append(Spacer(1, 15))
        
        # Date
        date_str = sale.sale_date.strftime('%d/%m/%Y')
        date_text = f"""
        <para alignment="right" fontSize="10" color="#4b5563">
        Ouagadougou, le {date_str}
        </para>
        """
        header_elements.append(Paragraph(date_text, styles['Normal']))
        header_elements.append(Spacer(1, 15))
        
        # Titre FACTURE PRO FORMA
        title_text = f"""
        <para alignment="center" spaceAfter="10">
        <font size="18" color="#1a5490"><u><b>FACTURE N°{sale.sale_number}</b></u></font><br/>
        
        </para>
        """
        header_elements.append(Paragraph(title_text, styles['Normal']))
        header_elements.append(Spacer(1, 20))
        
        return header_elements
    
    def _create_info_section(self, sale: 'Sale') -> List:
        """Crée la section informations client style proforma"""
        styles = getSampleStyleSheet()
        
        customer_name = ""
        customer_address = ""
        customer_phone = ""
        customer_email = ""
        
        if sale.customer:
            customer_name = self._clean_text(f"{sale.customer.first_name or ''} {sale.customer.last_name or ''}").strip()
            customer_address = self._clean_text(sale.customer.address) if hasattr(sale.customer, 'address') and sale.customer.address else ""
            customer_phone = self._clean_text(sale.customer.phone) if hasattr(sale.customer, 'phone') and sale.customer.phone else ""
            customer_email = self._clean_text(sale.customer.email) if hasattr(sale.customer, 'email') and sale.customer.email else ""
        
        if not customer_name:
            customer_name = "Client"
        
        # Objet
        subject = sale.notes or "Achat et réparation"
        
        # Construction des informations client - tout à gauche
        info_html = f"""
        <para>
        <font size="11" color="#1a5490"><u><b>DOIT :</b></u></font><br/>
        <font size="11" color="#1a1a1a"><b>{customer_name}</b></font><br/>
        <font size="9" color="#4b5563">{customer_address}</font><br/>
        {f'<font size="9" color="#4b5563">Tél: {customer_phone}</font><br/>' if customer_phone else ''}
        {f'<font size="9" color="#4b5563">Email: {customer_email}</font>' if customer_email else ''}
        </para>
        """
        
        # Objet
        object_html = f"""
        <para>
        <font size="10" color="#1a1a1a"><u><b>Objet :</b></u> <font size="10">{subject}</font></font>
        </para>
        """
        
        return [
            Paragraph(info_html, styles['Normal']),
            Spacer(1, 15),
            Paragraph(object_html, styles['Normal']),
            Spacer(1, 20)
        ]
    
    def _create_items_table(self, sale: 'Sale', table_width: float) -> List:
        """Crée le tableau des articles style proforma"""
        items_data = [
            ["N°", "DÉSIGNATION", "QTÉ", "PRIX UNIT.", "TOTAL"]
        ]
        
        # Ajouter tous les articles
        for idx, item in enumerate(sale.items, start=1):
            product_name = item.product.name if item.product else "Produit"
            product_name = self._clean_text(product_name)
            
            qty = int(item.quantity) if item.quantity == int(item.quantity) else item.quantity
            
            items_data.append([
                str(idx),
                product_name,
                str(qty),
                f"{item.unit_price:,.0f}",
                f"{item.line_total:,.0f}"
            ])
        
        # Ajouter 2 lignes vides pour l'espacement
        items_data.append(["", "", "", "", ""])
        items_data.append(["", "", "", "", ""])
        
        # Ligne du total
        total_amount = sale.total_amount
        items_data.append(["", "", "", "Total net :", f"{total_amount:,.0f}"])
        
        col_widths = [
            table_width * 0.08,  # N°
            table_width * 0.52,  # DÉSIGNATION
            table_width * 0.10,  # QTÉ
            table_width * 0.15,  # PRIX UNIT.
            table_width * 0.15   # TOTAL
        ]
        
        items_table = Table(items_data, colWidths=col_widths)
        
        total_row_index = len(items_data) - 1
        
        table_style = [
            # En-tête
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            
            # Alignement
            ('ALIGN', (0, 1), (0, total_row_index - 1), 'CENTER'),  # N°
            ('ALIGN', (2, 1), (2, total_row_index - 1), 'CENTER'),  # QTÉ
            ('ALIGN', (3, 1), (4, total_row_index - 1), 'RIGHT'),   # PRIX et TOTAL
            
            # Bordures
            ('GRID', (0, 0), (-1, total_row_index - 3), 0.5, colors.black),
            ('LINEBELOW', (0, total_row_index - 3), (-1, total_row_index - 3), 1, colors.black),
            
            # Alternance des couleurs
            ('BACKGROUND', (0, 1), (-1, total_row_index - 3), colors.white),
            ('ROWBACKGROUNDS', (0, 1), (-1, total_row_index - 3), [colors.white, colors.HexColor('#fafafa')]),
            
            # Padding
            ('PADDING', (0, 0), (-1, -1), 6),
            
            # Taille police
            ('FONTSIZE', (0, 1), (-1, -1), 10),
        ]
        
        # Style spécial pour la ligne TOTAL
        table_style.extend([
            ('BACKGROUND', (3, total_row_index), (4, total_row_index), colors.white),
            ('TEXTCOLOR', (3, total_row_index), (4, total_row_index), colors.HexColor('#1a5490')),
            ('FONTNAME', (3, total_row_index), (4, total_row_index), 'Helvetica-Bold'),
            ('FONTSIZE', (3, total_row_index), (4, total_row_index), 11),
            ('ALIGN', (3, total_row_index), (4, total_row_index), 'RIGHT'),
            ('LINEABOVE', (0, total_row_index), (-1, total_row_index), 1, colors.black),
            ('LINEBELOW', (0, total_row_index), (-1, total_row_index), 1, colors.black),
        ])
        
        items_table.setStyle(TableStyle(table_style))
        
        return [items_table, Spacer(1, 15)]
    
    def _create_totals_section(self, sale: 'Sale') -> List:
        """Crée la section des totaux avec montant en lettres style proforma"""
        styles = getSampleStyleSheet()
        
        total_amount = sale.total_amount
        currency = self.CURRENCY
        
        # Convertir le montant en lettres
        amount_in_words = self._number_to_words(total_amount, currency)
        
        # Montant en lettres
        letters_html = f"""
        <para fontSize="10" backColor="#f9fafb" borderColor="#1a5490" borderWidth="0.5" borderPadding="8" leftIndent="6">
        <i><b>Arrêté à la somme de :</b> {amount_in_words} ({total_amount:,.0f}) francs CFA</i>
        </para>
        """
        
        # Signature
        signature_html = """
        <para alignment="right" fontSize="10" color="#1a1a1a">
        <b>Le Gérant</b>
        </para>
        """
        
        signature_line_html = """
        <para alignment="right" fontSize="10" color="#1a1a1a">
        <font color="#1a1a1a">TIENDREBEOGO François</font>
        </para>
        """
        
        return [
            Spacer(1, 10),
            Paragraph(letters_html, styles['Normal']),
            Spacer(1, 30),
            Paragraph(signature_html, styles['Normal']),
            Spacer(1, 5),
            Paragraph(signature_line_html, styles['Normal']),
            Spacer(1, 20),
        ]
    
    def _create_footer(self) -> List:
        """Crée le pied de page style proforma avec contacts, adresse et informations légales"""
        styles = getSampleStyleSheet()
        
        footer_text = self.invoice_footer or 'Merci de votre confiance'
        
        # Contacts et adresse de l'entreprise
        contact_parts = []
        if self.company_address:
            contact_parts.append(self.company_address)
        if self.company_phone:
            contact_parts.append(f"Tél: {self.company_phone}")
        if self.company_email:
            contact_parts.append(f"Email: {self.company_email}")
        
        contact_info = " | ".join(contact_parts) if contact_parts else ""
        
        # Informations légales
        legal_parts = []
        if self.company_po_box:
            legal_parts.append(f"BP: {self.company_po_box}")
        if self.company_ifu:
            legal_parts.append(f"IFU: {self.company_ifu}")
        if self.company_rccm:
            legal_parts.append(f"RCCM: {self.company_rccm}")
        
        legal_info = " | ".join(legal_parts) if legal_parts else ""
        
        return [
            Spacer(1, 20),
            Paragraph(
                f'<para alignment="center" fontSize="9" color="#6b7280">{footer_text}</para>',
                styles['Normal']
            ),
            Spacer(1, 5),
            Paragraph(
                f'<para alignment="center" fontSize="9" color="#6b7280">{contact_info}</para>',
                styles['Normal']
            ),
            Spacer(1, 5),
            Paragraph(
                f'<para alignment="center" fontSize="9" color="#6b7280">{legal_info}</para>',
                styles['Normal']
            ),
        ]
    
    def generate_html_invoice(self, sale_id: int) -> Tuple[bool, str, str]:
        """Génère une facture au format HTML style proforma"""
        try:
            sale = self.get_sale_details(sale_id)
            if not sale:
                return False, "", "Vente non trouvée"
            
            html = self._create_html_template(sale)
            return True, html, "HTML généré avec succès"
            
        except Exception as e:
            logger.error(f"Erreur génération HTML: {e}")
            return False, "", f"Erreur: {str(e)}"
    
    def _create_html_template(self, sale: 'Sale') -> str:
        """Crée le template HTML style proforma"""
        
        company_name = self.company_name or 'MON ENTREPRISE'
        company_address = self.company_address or 'Ouagadougou'
        company_phone = self.company_phone or '+226 XX XX XX XX'
        company_email = self.company_email or 'contact@entreprise.com'
        currency = self.CURRENCY
        
        # Informations légales
        company_ifu = self.company_ifu
        company_rccm = self.company_rccm
        company_po_box = self.company_po_box
        footer_text = self.invoice_footer or 'Merci de votre confiance'
        
        # Client
        customer_name = ""
        customer_address = ""
        customer_phone = ""
        customer_email = ""
        
        if sale.customer:
            customer_name = self._clean_text(f"{sale.customer.first_name or ''} {sale.customer.last_name or ''}").strip()
            customer_address = self._clean_text(sale.customer.address) if hasattr(sale.customer, 'address') and sale.customer.address else ""
            customer_phone = self._clean_text(sale.customer.phone) if hasattr(sale.customer, 'phone') and sale.customer.phone else ""
            customer_email = self._clean_text(sale.customer.email) if hasattr(sale.customer, 'email') and sale.customer.email else ""
        
        if not customer_name:
            customer_name = "Client"
        
        # Objet
        subject = sale.notes or "Achat et réparation"
        
        # Articles
        items_rows = ""
        for idx, item in enumerate(sale.items, start=1):
            product_name = item.product.name if item.product else "Produit"
            product_name = self._clean_text(product_name)
            
            qty = int(item.quantity) if item.quantity == int(item.quantity) else item.quantity
            
            items_rows += f"""
            <tr>
                <td class="center">{idx}</td>
                <td>{product_name}</td>
                <td class="center">{qty}</td>
                <td class="right">{item.unit_price:,.0f}</td>
                <td class="right">{item.line_total:,.0f}</td>
            </tr>
            """
        
        # Total
        total_amount = sale.total_amount
        amount_in_words = self._number_to_words(total_amount, currency)
        
        # Construction des contacts et adresse
        contact_parts = []
        if company_address:
            contact_parts.append(company_address)
        if company_phone:
            contact_parts.append(f"Tél: {company_phone}")
        if company_email:
            contact_parts.append(f"Email: {company_email}")
        contact_info = " | ".join(contact_parts) if contact_parts else ""
        
        # Construction des informations légales
        legal_parts = []
        if company_po_box:
            legal_parts.append(f"BP: {company_po_box}")
        if company_ifu:
            legal_parts.append(f"IFU: {company_ifu}")
        if company_rccm:
            legal_parts.append(f"RCCM: {company_rccm}")
        legal_info = " | ".join(legal_parts) if legal_parts else ""
        
        date_str = sale.sale_date.strftime('%d/%m/%Y')
        
        html = f'''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8" />
<title>Facture Pro Forma</title>

<style>
    *{{
        margin:0;
        padding:0;
        box-sizing:border-box;
    }}

    body{{
        background:#ffffff;
        font-family: 'Times New Roman', Times, serif;
        color:#1a1a1a;
        font-size:10pt;
        line-height:1.4;
    }}

    .page{{
        width:210mm;
        min-height:297mm;
        margin:auto;
        padding:10mm 10mm;
        position:relative;
    }}

    /* En-tête */
    .header-table{{
        width:100%;
        border-collapse:collapse;
        margin-bottom:15px;
    }}
    .header-table td{{
        padding:5px 0;
        vertical-align:top;
    }}
    .company-name{{
        font-size:22pt;
        font-weight:bold;
        color:#1a5490;
    }}
    .company-info{{
        font-size:8pt;
        color:#4b5563;
    }}
    .title{{
        font-size:18pt;
        font-weight:bold;
        text-decoration:underline;
        color:#1a5490;
    }}
    .date{{
        font-size:10pt;
        color:#4b5563;
        text-align:right;
    }}
    .invoice-number{{
        font-size:12pt;
        font-weight:bold;
        color:#1a5490;
        margin-top:5px;
    }}

    /* Informations client */
    .info-block{{
        margin-bottom:10px;
        padding:8px 0;
    }}
    .info-block b{{
        font-weight:600;
    }}
    .customer-info{{
        margin:8px 0;
        font-size:10pt;
    }}
    .customer-name{{
        font-size:11pt;
        font-weight:bold;
    }}
    .customer-address{{
        font-size:9pt;
        color:#4b5563;
    }}
    .customer-contact{{
        font-size:9pt;
        color:#4b5563;
    }}
    .object-title{{
        font-size:10pt;
        font-weight:bold;
    }}

    /* Tableau */
    .main-table{{
        width:100%;
        border-collapse:collapse;
        margin:15px 0;
    }}
    .main-table th{{
        background-color:#f3f4f6;
        font-weight:bold;
        font-size:9pt;
        text-align:center;
        border:1px solid #000;
        padding:6px 4px;
        text-transform:uppercase;
    }}
    .main-table td{{
        border:1px solid #000;
        padding:5px 4px;
        font-size:10pt;
    }}
    .main-table tr:nth-child(even){{
        background-color:#fafafa;
    }}
    .center{{
        text-align:center;
    }}
    .right{{
        text-align:right;
    }}

    /* Total */
    .total-row td{{
        border:none;
        padding:8px 4px;
    }}
    .total-label{{
        font-size:11pt;
        font-weight:bold;
        text-align:right;
    }}
    .total-amount{{
        font-size:12pt;
        font-weight:bold;
        color:#1a5490;
        text-align:right;
    }}

    /* Montant en lettres */
    .letters{{
        font-size:10pt;
        font-style:italic;
        margin:10px 0;
        padding:8px;
        background-color:#f9fafb;
        border-left:3px solid #1a5490;
    }}

    /* Signature */
    .signature-block{{
        margin-top:40px;
        text-align:right;
    }}
    .signature-line{{
        margin-top:30px;
        padding-top:10px;
        border-top:1px solid #000;
        display:inline-block;
        min-width:200px;
    }}

    /* Pied de page */
    .footer{{
        margin-top:30px;
        font-size:9pt;
        color:#6b7280;
        text-align:center;
        border-top:1px solid #e5e7eb;
        padding-top:15px;
        position:absolute;
        bottom:10mm;
        left:10mm;
        right:10mm;
    }}

    @media print{{
        body{{
            margin:0;
        }}
        .page{{
            margin:0;
            width:100%;
        }}
    }}
</style>
</head>

<body>

<div class="page">

    <!-- En-tête : nom de l'entreprise uniquement -->
    <table class="header-table">
        <tr>
            <td width="50%">
                <div class="company-name">{company_name}</div>
            </td>
            <td width="50%" style="text-align:right;">
                <div class="date">Ouagadougou, le {date_str}</div>
                <br>
                <div class="title">FACTURE PRO FORMA</div>
                <div class="invoice-number">N° {sale.sale_number}</div>
            </td>
        </tr>
    </table>

    <!-- Informations client - tout à gauche -->
    <div class="info-block">
        <b><u>DOIT :</u></b><br>
        <span class="customer-name">{customer_name}</span><br>
        <span class="customer-address">{customer_address}</span><br>
        {f'<span class="customer-address">Tél: {customer_phone}</span><br>' if customer_phone else ''}
        {f'<span class="customer-address">Email: {customer_email}</span>' if customer_email else ''}
    </div>

    <!-- Objet -->
    <div class="info-block">
        <span class="object-title"><u>Objet :</u></span> <span style="font-size:10pt;">{subject}</span>
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
            {items_rows}
        </tbody>
        <tfoot>
            <tr>
                <td colspan="3" style="border:none;padding:10px 4px;"></td>
                <td class="total-label" style="border:none;padding:10px 4px;">Total net :</td>
                <td class="total-amount" style="border:none;padding:10px 4px;">{total_amount:,.0f} FCFA</td>
            </tr>
        </tfoot>
    </table>

    <!-- Montant en lettres -->
    <div class="letters">
        <b>Arrêté à la somme de :</b> {amount_in_words} ({total_amount:,.0f}) francs CFA
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
        {footer_text}<br>
        {contact_info}<br>
        {legal_info}
    </div>

</div>

</body>
</html>'''
          
        return html
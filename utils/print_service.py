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
# Predeclare names so static analyzers (Pylance) know they exist even if import fails
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

# Predeclare PyQt symbols for static analyzers
QApplication = None
QFileDialog = None
QProgressDialog = None
QMessageBox = None
QVBoxLayout = None
QLabel = None
QProgressBar = None
QDialog = None
Qt = None
QTimer = None
pyqtSignal = None
QObject = None
QRunnable = None
QThreadPool = None

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
    
    def print_proforma_invoice(self, proforma):
        """Imprime une facture proforma"""
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
        import tempfile
        
        try:
            # Créer un PDF temporaire
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                pdf_path = tmp.name
            
            # Créer le PDF
            c = canvas.Canvas(pdf_path, pagesize=A4)
            width, height = A4
            
            # En-tête
            c.setFont("Helvetica-Bold", 16)
            c.drawString(50, height - 50, "FACTURE PROFORMA")
            
            c.setFont("Helvetica", 10)
            c.drawString(50, height - 80, f"N°: {proforma.proforma_number}")
            c.drawString(50, height - 95, f"Date: {proforma.created_date.strftime('%d/%m/%Y')}")
            
            if proforma.valid_until:
                c.drawString(50, height - 110, f"Valide jusqu'au: {proforma.valid_until.strftime('%d/%m/%Y')}")
            
            # Informations client
            y = height - 150
            if proforma.customer:
                c.setFont("Helvetica-Bold", 11)
                c.drawString(50, y, "CLIENT:")
                y -= 15
                c.setFont("Helvetica", 10)
                c.drawString(70, y, f"Nom: {proforma.customer.full_name}")
                y -= 12
                if proforma.customer.company:
                    c.drawString(70, y, f"Entreprise: {proforma.customer.company}")
                    y -= 12
                if proforma.customer.address:
                    c.drawString(70, y, f"Adresse: {proforma.customer.address}")
                    y -= 12
                if proforma.customer.phone:
                    c.drawString(70, y, f"Téléphone: {proforma.customer.phone}")
            
            # Tableau des articles
            y = height - 280
            c.setFont("Helvetica-Bold", 10)
            c.drawString(50, y, "Description")
            c.drawString(250, y, "Quantité")
            c.drawString(320, y, "Prix Unit.")
            c.drawString(400, y, "Montant")
            
            y -= 15
            c.setLineWidth(1)
            c.line(50, y, 550, y)
            
            y -= 15
            c.setFont("Helvetica", 9)
            
            for item in proforma.items:
                c.drawString(50, y, f"{item.description[:35]}")
                c.drawRightString(300, y, f"{item.quantity:.2f}")
                c.drawRightString(370, y, f"{item.unit_price:.2f}")
                c.drawRightString(500, y, f"{item.line_total:.2f}")
                y -= 12
                
                if y < 80:
                    c.showPage()
                    y = height - 50
            
            # Totaux
            y -= 10
            c.setLineWidth(1)
            c.line(50, y, 550, y)
            y -= 15
            
            c.setFont("Helvetica", 10)
            c.drawString(350, y, f"Sous-total: {proforma.subtotal:.2f} {proforma.currency}")
            
            y -= 12
            if proforma.discount_percent > 0:
                c.drawString(350, y, f"Remise ({proforma.discount_percent}%): -{proforma.discount_amount:.2f} {proforma.currency}")
                y -= 12
            
            c.drawString(350, y, f"TVA ({proforma.tax_percent}%): {proforma.tax_amount:.2f} {proforma.currency}")
            
            y -= 12
            c.setFont("Helvetica-Bold", 12)
            c.drawString(350, y, f"TOTAL: {proforma.total_amount:.2f} {proforma.currency}")
            
            # Convertir le montant en lettres
            amount_in_words = self.printer._number_to_words(proforma.total_amount, proforma.currency)
            
            # Notes
            if proforma.notes:
                y -= 30
                c.setFont("Helvetica", 9)
                c.drawString(50, y, "Notes:")
                y -= 12
                c.drawString(70, y, proforma.notes[:80])
            
            # Montant en lettres
            y -= 20
            c.setFont("Helvetica-Bold", 9)
            c.drawString(50, y, "Arrêté à la somme de :")
            y -= 15
            c.setFont("Helvetica", 9)
            
            # Gérer le texte long en plusieurs lignes si nécessaire
            words_text = f"{amount_in_words} ({proforma.total_amount:,.0f} {proforma.currency})"
            if len(words_text) > 80:
                lines = [words_text[i:i+80] for i in range(0, len(words_text), 80)]
                for line in lines:
                    c.drawString(70, y, line)
                    y -= 12
            else:
                c.drawString(70, y, words_text)
                y -= 12
            
            # Conditions
            if proforma.terms_and_conditions:
                y -= 20
                c.setFont("Helvetica-Bold", 9)
                c.drawString(50, y, "Conditions Générales:")
                y -= 12
                c.setFont("Helvetica", 8)
                c.drawString(70, y, proforma.terms_and_conditions[:80])
            
            # === PIED DE PAGE - INFORMATIONS LÉGALES ===
            y = 50
            c.setFont("Helvetica", 8)
            c.setFillColorRGB(0.4, 0.4, 0.4)  # Gris
            
            legal_info = []
            if hasattr(self.printer, 'company_po_box') and self.printer.company_po_box:
                legal_info.append(f"BP: {self.printer.company_po_box}")
            if hasattr(self.printer, 'company_ifu') and self.printer.company_ifu:
                legal_info.append(f"IFU: {self.printer.company_ifu}")
            if hasattr(self.printer, 'company_rccm') and self.printer.company_rccm:
                legal_info.append(f"RCCM: {self.printer.company_rccm}")
            
            if legal_info:
                legal_text = " | ".join(legal_info)
                c.drawCentredString(width/2, y, legal_text)
                y -= 15
            
            # Ajouter le nom de l'entreprise en pied de page
            if hasattr(self.printer, 'company_name') and self.printer.company_name:
                c.setFont("Helvetica", 7)
                c.drawCentredString(width/2, y, self.printer.company_name)
            
            c.setFillColorRGB(0, 0, 0)  # Retour en noir
            
            c.save()
            
            # Imprimer le PDF
            self.printer.print_file(pdf_path)
            
            logger.info(f"Proforma {proforma.proforma_number} imprimée")
            return True, pdf_path
        
        except Exception as e:
            logger.error(f"Erreur impression proforma: {str(e)}")
            return False, str(e)


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
            # Mode texte simple si Tkinter non disponible
            print(f"{self.title}: {self.message}")
            return
        
        try:
            # Créer une fenêtre Tkinter pour la progression
            self.root = tk.Tk()
            self.root.title(self.title)
            self.root.geometry("400x150")
            self.root.resizable(False, False)
            
            # Centrer la fenêtre
            self.root.update_idletasks()
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            x = (self.root.winfo_screenwidth() // 2) - (width // 2)
            y = (self.root.winfo_screenheight() // 2) - (height // 2)
            self.root.geometry(f'{width}x{height}+{x}+{y}')
            
            # Message
            label = tk.Label(self.root, text=self.message, font=("Arial", 10))
            label.pack(pady=20)
            
            # Barre de progression
            self.progress = ttk.Progressbar(
                self.root, 
                orient="horizontal",
                length=300,
                mode="determinate",
                maximum=self.maximum
            )
            self.progress.pack(pady=10)
            
            # Label de pourcentage
            self.percent_label = tk.Label(self.root, text="0%", font=("Arial", 9))
            self.percent_label.pack()
            
            # Bouton Annuler
            self.cancel_button = tk.Button(
                self.root, 
                text="Annuler", 
                command=self.cancel,
                width=10
            )
            self.cancel_button.pack(pady=10)
            
            # Mettre à jour la fenêtre
            self.root.update()
            
        except Exception as e:
            logger.error(f"Erreur création dialogue progression: {e}")
    
    def update(self, value, message=None):
        """Met à jour la progression"""
        if hasattr(self, 'progress'):
            self.progress['value'] = value
            if message:
                # Mettre à jour le message si fourni
                for widget in self.root.winfo_children():
                    if isinstance(widget, tk.Label) and widget.cget("font") == ("Arial", 10):
                        widget.config(text=message)
                        break
            
            # Mettre à jour le pourcentage
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
    """Service de génération de factures/tickets"""
    
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
        self.company_name = self.company_settings.get('company_name', 'NOM DE VOTRE ENTREPRISE')
        self.company_phone = self.company_settings.get('company_phone', '')
        self.company_email = self.company_settings.get('company_email', '')
        self.company_address = self.company_settings.get('company_address', '')
        self.invoice_footer = self.company_settings.get('invoice_footer', 'Merci pour votre confiance.')
        
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
        """Récupère les détails d'une vente (imports locaux pour éviter les imports circulaires)"""
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
        """
        Nettoie le texte en supprimant les balises HTML et en échappant les caractères spéciaux
        
        Args:
            text: Texte à nettoyer
        
        Returns:
            Texte nettoyé
        """
        if not text:
            return ""
        
        # Décoder les entités HTML (comme &amp;, &lt;, etc.)
        text = html.unescape(text)
        
        # Supprimer les balises HTML
        import re
        text = re.sub(r'<[^>]+>', '', text)
        
        return text
    
    def _number_to_words(self, number: float, currency: str = "FCFA") -> str:
        """
        Convertit un nombre en toutes lettres
        
        Args:
            number: Le nombre à convertir
            currency: La devise (FCFA, Euro, Dollar, etc.)
        
        Returns:
            Le nombre en toutes lettres
        """
        if number == 0:
            if currency.upper() in ["FCFA", "XAF", "XOF"]:
                return "zéro FCFA"
            elif currency.upper() in ["EUR", "EURO"]:
                return "zéro euro"
            elif currency.upper() in ["USD", "DOLLAR"]:
                return "zéro dollar"
            else:
                return f"zéro {currency}"
        
        # Séparer la partie entière et décimale
        integer_part = int(number)
        decimal_part = int(round((number - integer_part) * 100))
        
        # Dictionnaires pour la conversion
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
            """Convertit un nombre de 0 à 999 en lettres"""
            if n == 0:
                return ""
            
            result = ""
            
            # Centaines
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
            
            # Dizaines et unités
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
            """Convertit un chunk de 3 chiffres avec son nom"""
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
        
        # Convertir la partie entière
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
        
        # Partie décimale
        if decimal_part > 0:
            # Déterminer le nom de la subdivision de la devise
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
            # Déterminer le pluriel pour la devise
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
        """
        Ouvre une boîte de dialogue pour sélectionner un dossier
        
        Args:
            title: Titre de la boîte de dialogue
            initial_dir: Répertoire initial (par défaut: Documents)
        
        Returns:
            Chemin du dossier sélectionné ou None
        """
        if not GUI_AVAILABLE:
            logger.warning("Impossible d'afficher la boîte de dialogue (Tkinter non disponible)")
            return None
        
        try:
            # Masquer la fenêtre principale de Tkinter
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
        """
        Ouvre une boîte de dialogue pour sélectionner un emplacement de sauvegarde
        
        Args:
            title: Titre de la boîte de dialogue
            initial_dir: Répertoire initial
            default_filename: Nom de fichier par défaut
            file_types: Liste des types de fichiers [(description, pattern)]
        
        Returns:
            Chemin complet du fichier ou None
        """
        if not GUI_AVAILABLE:
            logger.warning("Impossible d'afficher la boîte de dialogue (Tkinter non disponible)")
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
        """
        Génère une facture détaillée au format PDF
        
        Args:
            sale_id: ID de la vente
            output_path: Chemin complet du fichier de sortie (prioritaire)
            output_dir: Répertoire de sortie (si output_path non fourni)
            filename: Nom du fichier (si output_path non fourni)
            ask_location: Si True, ouvre une boîte de dialogue pour choisir l'emplacement
            show_progress: Si True, montre une barre de progression
        
        Returns:
            Tuple[success: bool, message: str, file_path: str]
        """
        # Rafraîchir les paramètres avant de générer
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
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72
            )
            
            story = []
            
            story.extend(self._create_header(sale))
            
            if progress_dialog:
                progress_dialog.update(60, "Ajout des informations client...")
            
            story.extend(self._create_info_section(sale))
            
            if progress_dialog:
                progress_dialog.update(70, "Création du tableau des articles...")
            
            story.extend(self._create_items_table(sale, doc.width))
            
            if progress_dialog:
                progress_dialog.update(80, "Calcul des totaux...")
            
            story.extend(self._create_totals_section(sale))
            
            story.extend(self._create_signature_section())
            
            # === PIED DE PAGE AVEC INFORMATIONS LÉGALES ===
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
    
    def _generate_invoice_with_location_dialog(self, sale: Sale, 
                                             progress_dialog: ProgressDialog = None) -> Tuple[bool, str, str]:
        """Génère une facture en demandant l'emplacement via une boîte de dialogue"""
        default_filename = f"Facture_{sale.sale_number}_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        file_path = None
        
        if GUI_AVAILABLE:
            if progress_dialog:
                progress_dialog.update(50, "En attente de la sélection de l'emplacement...")
            
            file_path = self.select_save_path_dialog(
                title=f"Enregistrer la facture {sale.sale_number}",
                initial_dir=self.default_directories['invoices'],
                default_filename=default_filename,
                file_types=[
                    ("Fichiers PDF", "*.pdf"), 
                    ("Fichiers HTML", "*.html"), 
                    ("Tous les fichiers", "*.*")
                ]
            )
        
        if not file_path:
            output_dir = self.default_directories['invoices']
            file_path = os.path.join(output_dir, default_filename)
        
        if file_path.lower().endswith('.html'):
            return self._save_html_invoice_file(sale.id, file_path, progress_dialog)
        else:
            return self._generate_invoice_file(sale, file_path, progress_dialog)
    
    def _generate_invoice_file(self, sale: Sale, file_path: str, 
                             progress_dialog: ProgressDialog = None) -> Tuple[bool, str, str]:
        """Génère le fichier PDF de facture"""
        try:
            if progress_dialog:
                progress_dialog.update(60, "Création du document PDF...")
            
            doc = SimpleDocTemplate(
                file_path,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72
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
            
            story.extend(self._create_signature_section())
            
            # === PIED DE PAGE AVEC INFORMATIONS LÉGALES ===
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
        """
        Génère un ticket de caisse simple
        
        Args:
            sale_id: ID de la vente
            output_path: Chemin complet du fichier de sortie (prioritaire)
            output_dir: Répertoire de sortie (si output_path non fourni)
            filename: Nom du fichier (si output_path non fourni)
            ask_location: Si True, ouvre une boîte de dialogue pour choisir l'emplacement
            show_progress: Si True, montre une barre de progression
        
        Returns:
            Tuple[success: bool, message: str, file_path: str]
        """
        # Rafraîchir les paramètres avant de générer
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
    
    def _generate_receipt_with_location_dialog(self, sale: Sale, 
                                             progress_dialog: ProgressDialog = None) -> Tuple[bool, str, str]:
        """Génère un ticket en demandant l'emplacement via une boîte de dialogue"""
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
    
    def _generate_receipt_file(self, sale: Sale, file_path: str, 
                             progress_dialog: ProgressDialog = None) -> Tuple[bool, str, str]:
        """Génère le fichier PDF de ticket avec les informations de l'entreprise"""
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
            
            logo_path = self.logo_path
            if logo_path and os.path.exists(logo_path):
                try:
                    logo_img = Image(logo_path, width=25, height=25)
                    story.append(logo_img)
                    story.append(Spacer(1, 3))
                except Exception as e:
                    logger.warning(f"Impossible d'ajouter le logo au ticket: {e}")
            
            company_name = self.company_name or 'KORGO STORE'
            story.append(Paragraph(company_name, self._get_style('Heading2')))
            
            # === PIED DE PAGE DU TICKET - INFORMATIONS LÉGALES ===
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
            
            # Ajouter le montant en lettres sur le ticket
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
        """
        Résout le chemin de sortie en fonction des paramètres fournis
        """
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
        """
        Génère plusieurs factures en batch
        
        Args:
            sale_ids: Liste des IDs de vente
            output_dir: Répertoire de sortie
            filename_pattern: Pattern pour les noms de fichiers
            ask_location: Si True, ouvre une boîte de dialogue pour choisir le dossier
            show_progress: Si True, montre une barre de progression
        
        Returns:
            Dict[sale_id: (success, message, file_path)]
        """
        # Rafraîchir les paramètres avant de générer
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
        """
        Imprime un fichier PDF avec l'imprimante par défaut
        
        Args:
            file_path: Chemin du fichier à imprimer
            show_progress: Si True, montre une barre de progression
        """
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
        """
        Génère et sauvegarde une facture au format HTML
        
        Args:
            sale_id: ID de la vente
            output_path: Chemin complet
            output_dir: Répertoire de sortie
            filename: Nom du fichier
            ask_location: Si True, ouvre une boîte de dialogue pour choisir l'emplacement
            show_progress: Si True, montre une barre de progression
        
        Returns:
            Tuple[success, message, file_path]
        """
        # Rafraîchir les paramètres avant de générer
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
                
                result = self._save_html_invoice_file(sale_id, file_path, progress_dialog)
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
    
    def _save_html_invoice_file(self, sale_id: int, file_path: str, 
                              progress_dialog: ProgressDialog = None) -> Tuple[bool, str, str]:
        """Sauvegarde une facture HTML dans un fichier"""
        try:
            if progress_dialog:
                progress_dialog.update(60, "Génération du code HTML...")
            
            success, html_content, message = self.generate_html_invoice(sale_id)
            if not success:
                return False, message, ""
            
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
        """
        Retourne le répertoire par défaut pour une catégorie
        
        Args:
            category: 'invoices', 'receipts', 'batch', 'html'
        
        Returns:
            Chemin du répertoire
        """
        return self.default_directories.get(category, tempfile.gettempdir())
    
    def set_default_directory(self, category: str, path: str) -> bool:
        """
        Définit un nouveau répertoire par défaut
        
        Args:
            category: 'invoices', 'receipts', 'batch', 'html'
            path: Nouveau chemin
        
        Returns:
            True si réussi, False sinon
        """
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
    
    # Méthodes privées pour la génération PDF
    
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
        
        return styles[style_name]
    
    def _create_header(self, sale: Sale) -> List:
        """Crée l'en-tête de la facture (sans informations légales)"""
        styles = getSampleStyleSheet()
        
        company_name = self.company_name or 'NOM DE VOTRE ENTREPRISE'
        
        header_text = f"""
        <para alignment="center">
        <font size="24"><b>{company_name}</b></font><br/>
        </para>
        """
        
        return [Paragraph(header_text, styles['Normal']), Spacer(1, 20)]
    
    def _create_info_section(self, sale: Sale) -> List:
        """Crée la section informations client et vendeur"""
        styles = getSampleStyleSheet()
        
        customer_code = str(sale.customer.id) if sale.customer and sale.customer.id else ""
        customer_name = ""
        customer_company = ""
        customer_address = ""
        customer_city = ""
        customer_province = ""
        customer_postal = ""
        customer_phone = ""
        delivery_address = ""
        
        if sale.customer:
            customer_name = self._clean_text(f"{sale.customer.first_name or ''} {sale.customer.last_name or ''}").strip()
            customer_company = self._clean_text(sale.customer.company) if sale.customer.company else ""
            customer_address = self._clean_text(sale.customer.address) if hasattr(sale.customer, 'address') and sale.customer.address else ""
            customer_city = self._clean_text(sale.customer.city) if hasattr(sale.customer, 'city') and sale.customer.city else ""
            customer_province = self._clean_text(sale.customer.province) if hasattr(sale.customer, 'province') and sale.customer.province else ""
            customer_postal = self._clean_text(sale.customer.postal_code) if hasattr(sale.customer, 'postal_code') and sale.customer.postal_code else ""
            customer_phone = self._clean_text(sale.customer.phone) if hasattr(sale.customer, 'phone') and sale.customer.phone else ""
            delivery_address = customer_address
        
        if not customer_name:
            customer_name = "Client général"
        
        # Informations vendeur
        vendor_name = self._clean_text(sale.cashier.username if sale.cashier else "")
        
        info_lines = [
            f"<b>DATE :</b> {sale.sale_date.strftime('%d/%m/%Y')}",
            f"<b>Numéro Facture N° :</b> {sale.sale_number}",
            f"<b>Vendeur :</b> {vendor_name}",
            f"<b>Code client :</b> {customer_code}",
            f"<b>Nom :</b> {customer_name}",
            f"<b>Livré à :</b> {delivery_address}",
            f"<b>Entreprise :</b> {customer_company}",
            f"<b>Adresse :</b> {customer_address}",
            f"<b>Ville :</b> {customer_city}",
            f"<b>État/Province :</b> {customer_province}",
            f"<b>Code Postal :</b> {customer_postal}",
            f"<b>Téléphone :</b> {customer_phone}",
        ]
        
        info_text = "<br/>".join(info_lines)
        
        return [Paragraph(info_text, styles['Normal']), Spacer(1, 20)]
    
    def _create_items_table(self, sale: Sale, table_width: float) -> List:
        """
        Crée le tableau des articles - Affiche TOUS les produits sans limite
        
        Args:
            sale: Objet Sale contenant les articles
            table_width: Largeur disponible pour le tableau
        
        Returns:
            Liste des éléments ReportLab pour le tableau
        """
        items_data = [["QUANTITÉ", "DESCRIPTION", "PRIX UNITAIRE", "TOTAL"]]
        
        # Ajouter TOUS les articles sans limite
        for item in sale.items:
            product_name = item.product.name if item.product else "Produit"
            product_name = self._clean_text(product_name)
            
            items_data.append([
                f"{item.quantity:.2f}",
                product_name,
                f"{item.unit_price:,.0f} {self.CURRENCY}",
                f"{item.line_total:,.0f} {self.CURRENCY}"
            ])
        
        # Ajouter 2 lignes vides pour l'espacement avant le total
        items_data.append(["", "", "", ""])
        items_data.append(["", "", "", ""])
        
        # Ligne des totaux
        total_amount = sale.total_amount
        items_data.append(["", "", "TOTAL", f"{total_amount:,.0f} {self.CURRENCY}"])
        
        col_widths = [table_width * 0.15, table_width * 0.50, table_width * 0.175, table_width * 0.175]
        
        items_table = Table(items_data, colWidths=col_widths)
        
        # Style du tableau
        total_row_index = len(items_data) - 1
        table_style = [
            # En-tête
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0047ab')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            
            # Alignement des colonnes (sauf en-tête)
            ('ALIGN', (2, 1), (3, total_row_index - 1), 'RIGHT'),
            
            # Grille principale (toutes les lignes sauf les vides et le total)
            ('GRID', (0, 0), (-1, total_row_index - 3), 0.5, colors.black),
            
            # Ligne de séparation avant le total
            ('LINEBELOW', (0, total_row_index - 3), (-1, total_row_index - 3), 1, colors.black),
            
            # Padding
            ('PADDING', (0, 0), (-1, -1), 6),
        ]
        
        # Style spécial pour la ligne TOTAL
        table_style.extend([
            ('BACKGROUND', (2, total_row_index), (3, total_row_index), colors.HexColor('#0047ab')),
            ('TEXTCOLOR', (2, total_row_index), (3, total_row_index), colors.white),
            ('FONTNAME', (2, total_row_index), (3, total_row_index), 'Helvetica-Bold'),
            ('ALIGN', (2, total_row_index), (3, total_row_index), 'RIGHT'),
        ])
        
        items_table.setStyle(TableStyle(table_style))
        
        return [items_table, Spacer(1, 20)]
    
    def _create_totals_section(self, sale: Sale) -> List:
        """Crée la section des notes et signature avec le montant en lettres"""
        styles = getSampleStyleSheet()
        
        company_name = self.company_name or '[VOTRE NOM DE COMPAGNIE]'
        company_phone = self.company_phone or '[NUMÉRO DE TÉLÉPHONE]'
        company_email = self.company_email or '[COURRIEL]'
        total_amount = sale.total_amount
        
        # Convertir le montant en lettres
        amount_in_words = self._number_to_words(total_amount, self.CURRENCY)
        
        notes_text = f"""
        <para>
        Arrêté la présente facture à la somme de <b>{amount_in_words}</b> ({total_amount:,.0f} {self.CURRENCY})<br/>
        Émettre tous les chèques à l'ordre de {company_name}<br/>
        Si vous avez des questions concernant la présente facture, n'hésitez pas à nous contacter au {company_phone}, {company_email}
        </para>
        """
        
        return [
            Paragraph(notes_text, styles['Normal']),
            Spacer(1, 40),
        ]
    
    def _create_signature_section(self) -> List:
        """Crée la section signature"""
        styles = getSampleStyleSheet()
        
        signature_text = """
        <para alignment="right">
        Signature<br/>
        _________________________
        </para>
        """
        
        return [Paragraph(signature_text, styles['Normal'])]
    
    def _create_footer(self) -> List:
        """
        Crée le pied de page avec les informations légales
        (IFU, RCCM, Boîte Postale)
        """
        styles = getSampleStyleSheet()
        
        # Construire les informations légales
        legal_info_lines = []
        if self.company_po_box:
            legal_info_lines.append(f"BP: {self.company_po_box}")
        if self.company_ifu:
            legal_info_lines.append(f"IFU: {self.company_ifu}")
        if self.company_rccm:
            legal_info_lines.append(f"RCCM: {self.company_rccm}")
        
        legal_info_text = " | ".join(legal_info_lines) if legal_info_lines else ""
        
        # Pied de page avec les informations légales
        footer_text = f"""
        <para alignment="center" fontName="Helvetica" fontSize="8" color="#666666">
        {legal_info_text}
        </para>
        """
        
        return [Spacer(1, 10), Paragraph(footer_text, styles['Normal'])]
    
    def generate_html_invoice(self, sale_id: int) -> Tuple[bool, str, str]:
        """
        Génère une facture au format HTML pour l'impression rapide
        
        Returns:
            Tuple[success, html_content, message]
        """
        try:
            sale = self.get_sale_details(sale_id)
            if not sale:
                return False, "", "Vente non trouvée"
            
            html = self._create_html_template(sale)
            return True, html, "HTML généré avec succès"
            
        except Exception as e:
            logger.error(f"Erreur génération HTML: {e}")
            return False, "", f"Erreur: {str(e)}"
    
    def _create_html_template(self, sale: Sale) -> str:
        """Crée le template HTML avec les informations légales en pied de page"""
        
        # Récupérer les informations de l'entreprise
        company_name = self.company_name or 'NOM DE VOTRE ENTREPRISE'
        company_phone = self.company_phone or '[VOTRE NUMERO DE TELEPHONE]'
        company_email = self.company_email or '[COURRIEL]'
        currency = self.CURRENCY
        
        # Récupérer les informations légales pour le pied de page
        company_ifu = self.company_ifu
        company_rccm = self.company_rccm
        company_po_box = self.company_po_box
        
        # Informations client
        customer_code = str(sale.customer.id) if sale.customer and sale.customer.id else ""
        customer_name = ""
        customer_company = ""
        customer_address = ""
        customer_city = ""
        customer_province = ""
        customer_postal = ""
        customer_phone = ""
        delivery_address = ""
        
        if sale.customer:
            customer_name = self._clean_text(f"{sale.customer.first_name or ''} {sale.customer.last_name or ''}").strip()
            customer_company = self._clean_text(sale.customer.company) if sale.customer.company else ""
            customer_address = self._clean_text(sale.customer.address) if hasattr(sale.customer, 'address') and sale.customer.address else ""
            customer_city = self._clean_text(sale.customer.city) if hasattr(sale.customer, 'city') and sale.customer.city else ""
            customer_province = self._clean_text(sale.customer.province) if hasattr(sale.customer, 'province') and sale.customer.province else ""
            customer_postal = self._clean_text(sale.customer.postal_code) if hasattr(sale.customer, 'postal_code') and sale.customer.postal_code else ""
            customer_phone = self._clean_text(sale.customer.phone) if hasattr(sale.customer, 'phone') and sale.customer.phone else ""
            delivery_address = customer_address
        
        if not customer_name:
            customer_name = "Client général"
        
        # Informations vendeur
        salesperson = self._clean_text(sale.cashier.username if sale.cashier else '')
        
        # Détail des articles - TOUS les articles, pas de limite
        items_rows = ""
        for item in sale.items:
            product_name = item.product.name if item.product else "Produit"
            product_name = self._clean_text(product_name)
            
            items_rows += f"""
                <tr>
                    <td class="qty">{item.quantity:.2f}</td>
                    <td class="desc">{product_name}</td>
                    <td class="price">{item.unit_price:,.0f}</td>
                    <td class="total">{item.line_total:,.0f}</td>
                </tr>
            """
        
        # Ajouter 2 lignes vides pour l'espacement avant le total
        for _ in range(2):
            items_rows += """
                <tr>
                    <td class="qty">&nbsp;</td>
                    <td class="desc">&nbsp;</td>
                    <td class="price">&nbsp;</td>
                    <td class="total">&nbsp;</td>
                </tr>
            """
        
        # Totaux
        total_amount = sale.total_amount
        
        # Convertir le montant en lettres
        amount_in_words = self._number_to_words(total_amount, currency)
        
        # Construction des informations légales pour le pied de page HTML
        legal_html = ""
        legal_parts = []
        if company_po_box:
            legal_parts.append(f"BP: {company_po_box}")
        if company_ifu:
            legal_parts.append(f"IFU: {company_ifu}")
        if company_rccm:
            legal_parts.append(f"RCCM: {company_rccm}")
        
        if legal_parts:
            legal_html = " | ".join(legal_parts)
        
        # Construction du HTML avec le template
        html = f'''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8" />
<title>Facture</title>

<style>
    *{{
        margin:0;
        padding:0;
        box-sizing:border-box;
    }}

    body{{
        background:#ffffff;
        font-family:Arial, Helvetica, sans-serif;
        color:#000;
    }}

    .page{{
        width:210mm;
        min-height:297mm;
        margin:auto;
        padding:18mm 15mm;
        position:relative;
    }}

    .header{{
        text-align:center;
        margin-bottom:25px;
    }}

    .company-name{{
        font-size:24px;
        font-weight:bold;
        text-transform:uppercase;
        margin-bottom:2px;
    }}

    .company-slogan{{
        font-size:13px;
        font-style:italic;
        font-weight:bold;
    }}

    .company-address{{
        font-size:12px;
    }}

    .company-contact{{
        font-size:12px;
    }}

    .client-section{{
        width:100%;
        margin-top:20px;
        margin-bottom:25px;
        font-size:13px;
        line-height:1.35;
    }}

    .client-section b{{
        display:inline-block;
        width:160px;
    }}

    .invoice-title{{
        text-align:center;
        font-size:38px;
        font-weight:bold;
        margin:35px 0 25px;
    }}

    .comments{{
        font-size:14px;
        font-weight:bold;
        margin-bottom:12px;
    }}

    table{{
        width:100%;
        border-collapse:collapse;
    }}

    .blue-header th{{
        background:#0047ab;
        color:#fff;
        border:2px solid #1c1c1c;
        padding:8px 5px;
        font-size:13px;
        text-align:center;
    }}

    .top-table td{{
        border:1px solid #7d7d7d;
        height:50px;
        padding:8px;
        font-size:13px;
        vertical-align:top;
    }}

    .items-table{{
        margin-top:18px;
        border:2px solid #1c1c1c;
    }}

    .items-table th{{
        background:#0047ab;
        color:white;
        border:1px solid #1c1c1c;
        padding:6px;
        font-size:13px;
        text-align:center;
    }}

    .items-table td{{
        border:1px solid #9d9d9d;
        height:24px;
        padding:4px 6px;
        font-size:13px;
    }}

    .qty{{
        width:16%;
        text-align:center;
    }}

    .desc{{
        width:48%;
    }}

    .price{{
        width:18%;
        text-align:right;
    }}

    .total{{
        width:18%;
        text-align:right;
    }}

    .summary-label{{
        text-align:right;
        font-weight:normal;
        padding-right:10px !important;
    }}

    .summary-value{{
        text-align:right;
        padding-right:10px !important;
    }}

    .grand-total-label{{
        background:#0047ab;
        color:white;
        font-weight:bold;
    }}

    .grand-total-value{{
        background:#0047ab;
        color:white;
        font-weight:bold;
    }}

    .notes{{
        margin-top:18px;
        font-size:13px;
        line-height:1.6;
    }}

    .notes b{{
        font-weight:bold;
    }}

    .signature{{
        width:320px;
        margin-top:45px;
        margin-left:auto;
        text-align:center;
        font-size:14px;
    }}

    .signature-line{{
        margin-top:8px;
        border-top:1px solid #000;
        height:1px;
    }}

    /* === PIED DE PAGE AVEC INFORMATIONS LÉGALES === */
    .footer-legal{{
        position:absolute;
        bottom:15mm;
        left:0;
        right:0;
        text-align:center;
        font-size:9px;
        color:#666;
        border-top:1px solid #ccc;
        padding-top:8px;
        margin:0 15mm;
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

    <!-- HEADER -->
    <div class="header">
        <div class="company-name">{company_name}</div>
    </div>

    <!-- CLIENT -->
    <div class="client-section">

        <div><b>DATE :</b> {sale.sale_date.strftime('%d/%m/%Y')}</div>

        <div><b>Numéro Facture N° :</b> {sale.sale_number}</div>

        <div><b>Code client :</b> {customer_code}</div>

        <div><b>Nom :</b> {customer_name}</div>

        <div><b>Livré à :</b> {delivery_address}</div>

        <div><b>Entreprise :</b> {customer_company}</div>

        <div><b>Adresse :</b> {customer_address}</div>

        <div><b>Ville :</b> {customer_city}</div>

        <div><b>État/Province :</b> {customer_province}</div>

        <div><b>Code Postal :</b> {customer_postal}</div>

        <div><b>Téléphone :</b> {customer_phone}</div>

    </div>

    <!-- TITLE -->
    <div class="invoice-title">
        Facture
    </div>

    <!-- COMMENTS -->
    <div class="comments">
        Commentaires ou Indications particulières :
    </div>

    <!-- TOP TABLE -->
    <table class="top-table">

        <thead class="blue-header">
            <tr>
                <th>VENDEUR</th>
                <th>NUMÉRO B.C.</th>
                <th>DATE EXP.</th>
                <th>PORT DE TRANSIT</th>
                <th>POINT F.O.B.</th>
                <th>MODALITÉS</th>
            </tr>
        </thead>

        <tbody>
            <tr>
                <td>{salesperson}</td>
                <td>&nbsp;</td>
                <td>&nbsp;</td>
                <td>&nbsp;</td>
                <td>&nbsp;</td>
                <td style="text-align:center;">
                    Paiement à la livraison.
                </td>
            </tr>
        </tbody>

    </table>

    <!-- ITEMS TABLE -->
    <table class="items-table">

        <thead>
            <tr>
                <th class="qty">QUANTITÉ</th>
                <th class="desc">DESCRIPTION</th>
                <th class="price">PRIX UNITAIRE</th>
                <th class="total">TOTAL</th>
            </tr>
        </thead>

        <tbody>
{items_rows}
            <!-- TOTALS -->
            <tr>
                <td colspan="2"></td>
                <td class="summary-label grand-total-label">
                    TOTAL
                </td>

                <td class="summary-value grand-total-value">
                    {total_amount:,.0f}
                </td>
            </tr>

        </tbody>

    </table>

    <!-- NOTES -->
    <div class="notes">

        Arrêté la présente facture à la somme de <b>{amount_in_words}</b> ({total_amount:,.0f} {currency})
        <br>

        Émettre tous les chèques à l'ordre de {company_name}
        <br>

        Si vous avez des questions concernant la présente facture,
        n'hésitez pas à nous contacter au
        {company_phone}, {company_email}

    </div>

    <!-- SIGNATURE -->
    <div class="signature">

        Signature

        <div class="signature-line"></div>

    </div>

    <!-- === PIED DE PAGE - INFORMATIONS LÉGALES === -->
    <div class="footer-legal">
        {legal_html}
    </div>

</div>

</body>
</html>'''
        
        return html
# ui/settings_manager.py
import os
import json
from PySide6.QtCore import QObject, Signal
from pathlib import Path

class SettingsManager(QObject):
    """
    Gestionnaire centralisé des paramètres de l'application.
    Singleton pour garantir une seule instance dans toute l'app.
    """
    _instance = None
    settings_changed = Signal(dict)  # Signal émis quand les paramètres changent
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SettingsManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        super().__init__()
        self.settings_file = "company_settings.json"
        self.default_settings = {
            "company_name": "KORGO",
            "company_address": "",
            "company_phone": "",
            "company_email": "",
            "company_logo": "",
            "currency": "FCFA",
            "tax_rate": 20.0,  # Taux de TVA par défaut
            "invoice_footer": "Merci de votre confiance !",
            "theme": "light",
            "language": "fr",
            "invoice_prefix": "FAC",
            "invoice_start": 1,
            "payment_terms": 30,
            "discount": 0,
            "date_format": "dd/MM/yyyy",
            "animations": True
        }
        self.current_settings = self.load_settings()
        self._initialized = True
    
    def load_settings(self):
        """Charge les paramètres depuis le fichier JSON"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # Fusion avec les valeurs par défaut pour les clés manquantes
                    settings = self.default_settings.copy()
                    settings.update(loaded)
                    return settings
        except Exception as e:
            print(f"Erreur lors du chargement des paramètres: {e}")
        
        return self.default_settings.copy()
    
    def save_settings(self, settings=None):
        """Sauvegarde les paramètres dans le fichier JSON"""
        try:
            if settings:
                self.current_settings.update(settings)
            
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_settings, f, ensure_ascii=False, indent=4)
            
            # Émettre le signal de changement
            self.settings_changed.emit(self.current_settings.copy())
            return True
        except Exception as e:
            print(f"Erreur lors de la sauvegarde des paramètres: {e}")
            return False
    
    def get_setting(self, key, default=None):
        """Récupère une valeur de paramètre spécifique"""
        return self.current_settings.get(key, default if default is not None else self.default_settings.get(key))
    
    def set_setting(self, key, value):
        """Définit une valeur de paramètre spécifique"""
        self.current_settings[key] = value
        return self.save_settings()
    
    def get_all_settings(self):
        """Retourne tous les paramètres"""
        return self.current_settings.copy()
    
    def reset_to_defaults(self):
        """Réinitialise tous les paramètres aux valeurs par défaut"""
        self.current_settings = self.default_settings.copy()
        return self.save_settings()
    
    def get_logo_path(self):
        """Retourne le chemin du logo ou None s'il n'existe pas"""
        logo_path = self.get_setting("company_logo")
        if logo_path and os.path.exists(logo_path):
            return logo_path
        return None
    
    def get_company_info(self):
        """Retourne les informations de l'entreprise sous forme de dictionnaire"""
        return {
            'name': self.get_setting('company_name'),
            'address': self.get_setting('company_address'),
            'phone': self.get_setting('company_phone'),
            'email': self.get_setting('company_email'),
            'logo': self.get_setting('company_logo')
        }
    
    def get_billing_info(self):
        """Retourne les informations de facturation"""
        return {
            'company_name': self.get_setting('company_name'),
            'company_address': self.get_setting('company_address'),
            'company_phone': self.get_setting('company_phone'),
            'company_email': self.get_setting('company_email'),
            'company_logo': self.get_setting('company_logo'),
            'tax_rate': self.get_setting('tax_rate', 20.0),
            'invoice_footer': self.get_setting('invoice_footer', 'Merci de votre confiance !'),
            'currency': self.get_setting('currency', 'FCFA'),
            'invoice_prefix': self.get_setting('invoice_prefix', 'FAC'),
            'invoice_start': self.get_setting('invoice_start', 1),
            'payment_terms': self.get_setting('payment_terms', 30)
        }
    
    def get_company_info_for_invoice(self):
        """Retourne les informations formatées pour les factures"""
        info = self.get_company_info()
        info.update({
            'tax_rate': self.get_setting('tax_rate', 20.0),
            'currency': self.get_setting('currency', 'FCFA'),
            'invoice_footer': self.get_setting('invoice_footer', 'Merci de votre confiance !')
        })
        return info
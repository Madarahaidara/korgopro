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
            "animations": True,
            # Webhook Discord : secret — renseigné dans company_settings.json
            # (non versionné), jamais en dur dans le code.
            "discord_webhook_url": "",
        }
        self.current_settings = self.load_settings()
        self._initialized = True
    
    def load_settings(self):
        """Charge les paramètres en fusionnant, par priorité croissante :
        valeurs par défaut < cache local (company_settings.json) < base
        partagée Supabase (source de vérité).

        En mode local (SQLite / base injougne), la base distante est simplement
        ignorée et le fichier JSON fait office de persistance, comme avant.
        """
        settings = self.default_settings.copy()
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # Fusion avec les valeurs par défaut pour les clés manquantes
                    settings.update(loaded)
        except Exception as e:
            print(f"Erreur lors du chargement des paramètres: {e}")

        # Source de vérité partagée (Supabase) : écrase le cache local si dispo.
        remote = self._load_from_db()
        if remote:
            settings.update(remote)
        return settings

    # -- persistance Supabase (source de vérité partagée) -------------------
    def _db_available(self):
        """Vrai si le backend est une base partagée PostgreSQL (Supabase).

        En repli SQLite (développement / tests), la synchro distante est
        désactivée : le fichier JSON local suffit et évite une dépendance DB.
        """
        try:
            from core.database import get_dialect_name
            return get_dialect_name() == "postgresql"
        except Exception:
            return False

    def _load_from_db(self):
        """Lit le dictionnaire de paramètres depuis ``app_settings``.

        Retourne un ``dict`` (éventuellement vide) ou ``None`` si la base
        partagée est indisponible / la table absente. L'échec est silencieux :
        le poste retombe alors sur le cache local.
        """
        if not self._db_available():
            return None
        try:
            from core.database import SessionLocal
            from core.models.app_setting import AppSetting
            with SessionLocal() as session:
                row = session.get(AppSetting, 1)
                if row is None or not isinstance(row.data, dict):
                    return None
                return dict(row.data)
        except Exception as e:
            print(f"Avertissement : paramètres distants illisibles ({e})")
            return None

    def _save_to_db(self, data):
        """Fusionne ``data`` dans ``app_settings`` (merge shallow jsonb).

        ``data = data || patch`` : seules les clés fournies sont écrasées, les
        clés propres à l'autre plateforme sont préservées. Retourne ``True`` si
        la base partagée est à jour (ou hors-mode-partagé), ``False`` si la
        synchronisation a échoué (le cache local reste écrit malgré tout).
        """
        if not self._db_available():
            return True
        try:
            from sqlalchemy import text
            from core.database import SessionLocal
            with SessionLocal() as session:
                session.execute(
                    text(
                        "INSERT INTO app_settings (id, data) VALUES (1, CAST(:d AS jsonb)) "
                        "ON CONFLICT (id) DO UPDATE SET "
                        "data = app_settings.data || EXCLUDED.data, "
                        "updated_at = now()"
                    ),
                    {"d": json.dumps(data, ensure_ascii=False)},
                )
                session.commit()
            return True
        except Exception as e:
            print(f"Avertissement : sauvegarde des paramètres sur Supabase échouée ({e})")
            return False

    def save_settings(self, settings=None, emit=True):
        """Sauvegarde les paramètres : d'abord sur la base partagée (source de
        vérité), puis dans le cache local (repli hors-ligne).

        emit=False : mettre à jour sans diffuser settings_changed (utile
        pour les réglages techniques comme active_store_id, dont le
        changement est déjà géré par les vues elles-mêmes).
        """
        try:
            if settings:
                self.current_settings.update(settings)

            # 1) Base partagée (best-effort : un échec n'empêche pas le repli).
            self._save_to_db(self.current_settings)

            # 2) Cache local (toujours écrit).
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_settings, f, ensure_ascii=False, indent=4)

            # Émettre le signal de changement
            if emit:
                self.settings_changed.emit(self.current_settings.copy())
            return True
        except Exception as e:
            print(f"Erreur lors de la sauvegarde des paramètres: {e}")
            return False
    
    def get_setting(self, key, default=None):
        """Récupère une valeur de paramètre spécifique"""
        return self.current_settings.get(key, default if default is not None else self.default_settings.get(key))
    
    def set_setting(self, key, value, emit=True):
        """Définit une valeur de paramètre spécifique.

        emit=False pour les réglages techniques (pas de diffusion à toutes
        les vues — voir save_settings).
        """
        self.current_settings[key] = value
        return self.save_settings(emit=emit)
    
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
            'invoice_footer': self.get_setting('invoice_footer', 'Merci de votre confiance !'),
            'company_name': self.get_setting('company_name'),
            'company_address': self.get_setting('company_address'),
            'company_phone': self.get_setting('company_phone'),
            'company_email': self.get_setting('company_email'),
            'company_logo': self.get_setting('company_logo'),
            'company_ifu': self.get_setting('company_ifu', ''),
            'company_rccm': self.get_setting('company_rccm', ''),
            'company_po_box': self.get_setting('company_po_box', '')
        })
        return info

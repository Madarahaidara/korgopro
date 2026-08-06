# ui/icons/icon_manager.py
"""
Gestionnaire centralisé des icônes de l'application
Permet de charger et gérer toutes les icônes de manière cohérente
"""

from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication
from pathlib import Path
import os

class IconManager:
    """Gestionnaire centralisé des icônes de l'application"""
    
    # ===== ICÔNE PRINCIPALE DE L'APPLICATION =====
    APP_ICON_PATHS = [
        # Chemins relatifs depuis le dossier ui/icons
        "logo.ico",  # Votre icône principale
        "app_icon.ico",
        "app_icon.svg",
        "app_icon.png",
        "icon.ico",
        "icon.svg",
        "icon.png",
        # Chemins relatifs depuis la racine du projet
        "../logo.ico",
        "ui/icons/logo.ico",
    ]
    
    # ===== ICÔNES POUR LES BOUTONS DU MENU =====
    # Basé sur les fichiers que vous avez dans ui/icons/
    MENU_ICONS = {
        "dashboard": "dashboard.svg",
        "sale": "sale.svg",
        "stock": "stock.svg",
        "receipt": "receipt.svg",
        "admin": "admin.svg",
        "settings": "settings.svg",
        "user": "user.svg",
    }
    
    # ===== ICÔNES POUR LES ACTIONS =====
    ACTION_ICONS = {
        "add": "add.svg",
        "edit": "edit.svg",
        "delete": "delete.svg",
        "save": "save.svg",
        "cancel": "cancel.svg",
        "refresh": "refresh.svg",
        "search": "search.svg",
        "print": "print.svg",
        "export": "export.svg",
        "import": "import.svg",
        "check": "check.svg",
        "clear": "clear.svg",
    }
    
    # Cache pour les icônes chargées
    _icon_cache = {}
    _app_initialized = False
    
    @classmethod
    def initialize_app_check(cls):
        """Vérifie si l'application Qt est initialisée"""
        cls._app_initialized = QApplication.instance() is not None
    
    @classmethod
    def get_app_icon(cls):
        """Retourne l'icône principale de l'application"""
        cache_key = "app_icon"
        if cache_key not in cls._icon_cache:
            cls._icon_cache[cache_key] = cls._load_icon(cls.APP_ICON_PATHS)
        return cls._icon_cache[cache_key]
    
    @classmethod
    def get_menu_icon(cls, icon_name):
        """Retourne une icône du menu par son nom"""
        cache_key = f"menu_{icon_name}"
        if cache_key not in cls._icon_cache:
            if icon_name in cls.MENU_ICONS:
                icon_file = cls.MENU_ICONS[icon_name]
                icon_paths = [
                    os.path.join("ui/icons", icon_file),
                    icon_file,
                ]
                cls._icon_cache[cache_key] = cls._load_icon(icon_paths)
            else:
                cls._icon_cache[cache_key] = QIcon()
        return cls._icon_cache[cache_key]
    
    @classmethod
    def get_action_icon(cls, action_name):
        """Retourne une icône d'action par son nom"""
        cache_key = f"action_{action_name}"
        if cache_key not in cls._icon_cache:
            if action_name in cls.ACTION_ICONS:
                icon_file = cls.ACTION_ICONS[action_name]
                icon_paths = [
                    os.path.join("ui/icons", icon_file),
                    icon_file,
                ]
                cls._icon_cache[cache_key] = cls._load_icon(icon_paths)
            else:
                cls._icon_cache[cache_key] = QIcon()
        return cls._icon_cache[cache_key]
    
    @classmethod
    def get_icon(cls, icon_path):
        """Retourne une icône à partir d'un chemin spécifique"""
        cache_key = f"path_{icon_path}"
        if cache_key not in cls._icon_cache:
            cls._icon_cache[cache_key] = cls._load_icon([icon_path])
        return cls._icon_cache[cache_key]
    
    @classmethod
    def get_pixmap(cls, icon_path, width=32, height=32):
        """Retourne un QPixmap à partir d'un chemin (seulement si app initialisée)"""
        if not cls._app_initialized:
            # Ne pas créer de QPixmap si l'app n'est pas initialisée
            return QPixmap()
        
        icon = cls.get_icon(icon_path)
        if not icon.isNull():
            return icon.pixmap(width, height)
        return QPixmap()
    
    @classmethod
    def get_pixmap_safe(cls, icon_name, icon_type="menu", width=32, height=32):
        """Version sécurisée pour obtenir un pixmap"""
        cls.initialize_app_check()
        
        if not cls._app_initialized:
            return QPixmap()
        
        # Obtenir l'icône
        if icon_type == "menu":
            icon = cls.get_menu_icon(icon_name)
        elif icon_type == "action":
            icon = cls.get_action_icon(icon_name)
        elif icon_type == "app":
            icon = cls.get_app_icon()
        else:
            icon = cls.get_icon(icon_name)
        
        # Créer le pixmap seulement si l'app est initialisée
        if not icon.isNull() and cls._app_initialized:
            return icon.pixmap(width, height)
        
        return QPixmap()
    
    @classmethod
    def _load_icon(cls, paths):
        """
        Charge une icône depuis une liste de chemins
        Retourne QIcon() si aucune icône n'est trouvée
        """
        # D'abord vérifier si on est dans le bon dossier
        current_dir = Path(__file__).resolve().parent
        icons_dir = current_dir if current_dir.name == "icons" else current_dir / "icons"

        for path in paths:
            # Essayer différents chemins en utilisant pathlib
            possible_paths = [
                (icons_dir / path) if not Path(path).is_absolute() else Path(path),
                (current_dir / path) if not Path(path).is_absolute() else Path(path),
                (current_dir.parent / path) if not Path(path).is_absolute() else Path(path),
                (Path.cwd() / "ui" / "icons" / path) if not Path(path).is_absolute() else Path(path),
                (Path.cwd() / path) if not Path(path).is_absolute() else Path(path),
                Path(path),  # Essayer tel quel
            ]

            for full_path in possible_paths:
                try:
                    if full_path.exists():
                        icon = QIcon(str(full_path))
                        if not icon.isNull():
                            return icon
                except Exception as e:
                    print(f"Erreur lors du chargement de l'icône {full_path}: {e}")
                    continue
        
        # Icône vide en dernier recours
        return QIcon()
    
    @classmethod
    def set_app_icon(cls, app=None):
        """Définit l'icône globale de l'application"""
        if app is None:
            app = QApplication.instance()
        
        if app:
            app_icon = cls.get_app_icon()
            if not app_icon.isNull():
                app.setWindowIcon(app_icon)
                print("[OK] Icône d'application définie avec succès")
                cls._app_initialized = True
                return True
            else:
                print("[WARN] Impossible de charger l'icône de l'application")
        return False
    
    @classmethod
    def set_window_icon(cls, window):
        """Définit l'icône pour une fenêtre spécifique"""
        cls.initialize_app_check()
        
        if cls._app_initialized:
            app_icon = cls.get_app_icon()
            if not app_icon.isNull():
                window.setWindowIcon(app_icon)
                return True
        return False
    
    @classmethod
    def get_icon_for_button(cls, button_name):
        """Méthode utilitaire pour obtenir une icône de bouton"""
        # Essayer d'abord comme icône de menu
        icon = cls.get_menu_icon(button_name)
        if icon.isNull():
            # Essayer comme icône d'action
            icon = cls.get_action_icon(button_name)
        return icon
    
    @classmethod
    def check_available_icons(cls):
        """Vérifie quelles icônes sont disponibles"""
        print("\n=== Vérification des icônes disponibles ===")
        
        # Icône principale
        app_icon = cls.get_app_icon()
        print(f"Icône application: {'✓ Disponible' if not app_icon.isNull() else '✗ Non disponible'}")
        
        # Icônes de menu
        print("\nIcônes de menu:")
        for icon_name in cls.MENU_ICONS.keys():
            icon = cls.get_menu_icon(icon_name)
            status = "✓" if not icon.isNull() else "✗"
            print(f"  {status} {icon_name}")
        
        print("=" * 40)


# Instance unique pour un usage simplifié
icon_manager = IconManager()
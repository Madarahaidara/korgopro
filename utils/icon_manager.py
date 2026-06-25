# utils/icon_manager.py
import os
from PySide6.QtGui import QIcon
from utils.resource_path import get_icon_path

class IconManager:
    """Gestionnaire d'icônes avec cache"""
    
    _icons = {}
    
    @classmethod
    def get_icon(cls, icon_name):
        """Récupère une icône avec mise en cache"""
        if icon_name not in cls._icons:
            icon_path = get_icon_path(icon_name)
            if os.path.exists(icon_path):
                cls._icons[icon_name] = QIcon(icon_path)
            else:
                # Retourne une icône vide si le fichier n'existe pas
                cls._icons[icon_name] = QIcon()
                print(f"Warning: Icon not found: {icon_path}")
        
        return cls._icons[icon_name]
    
    @classmethod
    def clear_cache(cls):
        """Vide le cache des icônes"""
        cls._icons.clear()
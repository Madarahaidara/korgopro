# ui/views/splash_screen_enhanced.py
import os
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel
from ui.views.splash_screen import ModernSplashScreen

class EnhancedSplashScreen(ModernSplashScreen):
    def __init__(self, app):
        super().__init__(app)
        self.add_logo()  # Ajouter le logo par défaut
        
    def add_logo(self, image_path=None):
        """Ajoute un logo au splash screen (PNG, JPG ou texte)"""
        if image_path and os.path.exists(image_path):
            # Charger une image
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                # Redimensionner l'image
                pixmap = pixmap.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio, 
                                      Qt.TransformationMode.SmoothTransformation)
                logo_label = QLabel()
                logo_label.setPixmap(pixmap)
                logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                logo_label.setStyleSheet("background-color: transparent; margin-top: 20px;")
            else:
                logo_label = self._create_text_logo()
        else:
            # Logo par défaut (texte)
            logo_label = self._create_text_logo()
        
        # Insérer le logo au début du layout
        self.splash_widget.layout().insertWidget(0, logo_label, 0, Qt.AlignmentFlag.AlignCenter)
    
    def _create_text_logo(self):
        """Crée un logo texte par défaut"""
        logo_label = QLabel("KorgoPro")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setStyleSheet("""
            QLabel {
                font-size: 48px;
                font-weight: bold;
                color: #00d2ff;
                background-color: transparent;
                margin-top: 30px;
                font-family: 'Segoe UI', 'Arial', sans-serif;
            }
        """)
        return logo_label
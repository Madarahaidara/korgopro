# ui/views/splash_screen_simple.py
from PySide6.QtWidgets import QSplashScreen, QProgressBar, QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation
from PySide6.QtGui import QPixmap, QColor

class ModernSplashScreen(QSplashScreen):
    def __init__(self, app):
        # Taille basée sur l'écran (30% de la largeur, max 600x400)
        screen = app.primaryScreen().geometry()
        splash_w = min(600, int(screen.width() * 0.4))
        splash_h = min(400, int(screen.height() * 0.5))
        pixmap = QPixmap(splash_w, splash_h)
        self.splash_w = splash_w
        self.splash_h = splash_h

        # Fond blanc
        pixmap.fill(QColor(255, 255, 255))  # #FFFFFF
        
        super().__init__(pixmap)
        
        self.app = app
        self.init_ui()
        self.setup_animations()
        
        # Rendre le splash screen sans bordure et transparent sur les bords pour le border-radius
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Centrer
        self.center_on_screen()
        
    def init_ui(self):
        """Initialise l'interface du splash screen aux couleurs du logo"""
        self.widget = QWidget(self)
        self.widget.setGeometry(0, 0, self.splash_w, self.splash_h)
        # Application du fond blanc et des coins arrondis
        self.widget.setStyleSheet("background-color: #FFFFFF; border-radius: 15px;")
        
        layout = QVBoxLayout(self.widget)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(15)
        
        # 1. LOGO (Intégration de l'image logo.ico)
        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Chargement et redimensionnement propre du logo reçu
        logo_pixmap = QPixmap("logo.ico") # Assurez-vous que le chemin est correct
        if not logo_pixmap.isNull():
            self.logo_label.setPixmap(logo_pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            # Repli textuel ou icône si le fichier est manquant temporairement
            self.logo_label.setText("K")
            self.logo_label.setStyleSheet("color: #268B83; font-size: 72px; font-weight: bold; background: transparent;")
        layout.addWidget(self.logo_label)
        
        # 2. TITRE
        self.title_label = QLabel("KorgoPro")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("color: #121620; font-size: 30px; font-weight: bold; background: transparent; font-family: 'Segoe UI', Arial, sans-serif;")
        layout.addWidget(self.title_label)
        
        # 3. SOUS-TITRE
        self.subtitle_label = QLabel("Solution de Gestion Professionnelle")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setStyleSheet("color: #666666; font-size: 13px; background: transparent; letter-spacing: 1px;")
        layout.addWidget(self.subtitle_label)
        
        layout.addSpacing(20) # Espace avant la zone de chargement
        
        # 4. STATUT
        self.status_label = QLabel("Initialisation des modules...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #888888; font-size: 11px; background: transparent;")
        layout.addWidget(self.status_label)
        
        # 5. BARRE DE PROGRESSION (Glow & Sarcelle #268B83)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4) # Plus fine pour faire plus moderne
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { 
                background-color: rgba(0, 0, 0, 0.05); 
                border-radius: 2px; 
                border: none; 
            }
            QProgressBar::chunk { 
                background-color: #268B83; 
                border-radius: 2px; 
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # 6. VERSION
        version_label = QLabel("Version 2.0.0")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: #CCCCCC; font-size: 10px; background: transparent; margin-top: 10px;")
        layout.addWidget(version_label)
        
        self.widget.show()
        
    def setup_animations(self):
        """Configure les animations de texte légères pour le statut"""
        self.dot_count = 0
        self.base_status = "Initialisation"
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_loader_text)
        self.animation_timer.start(400)
        
    def update_loader_text(self):
        """Animation discrète par points (...) plutôt que des émojis pour rester pro"""
        self.dot_count = (self.dot_count + 1) % 4
        dots = "." * self.dot_count
        # Conserve le message actuel et anime juste les points à la fin si désiré
        if "..." in self.status_label.text():
            current_text = self.status_label.text().split("...")[0]
            self.status_label.setText(f"{current_text}{dots}")
        
    def center_on_screen(self):
        screen = self.app.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
        
    def update_status(self, message, progress=None):
        self.status_label.setText(message)
        if progress is not None:
            self.progress_bar.setValue(progress)
        self.repaint()
        
    def fade_out(self, callback=None):
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(400)
        self.animation.setStartValue(1.0)
        self.animation.setEndValue(0.0)
        if callback:
            self.animation.finished.connect(callback)
        self.animation.finished.connect(self.close)
        self.animation.start()
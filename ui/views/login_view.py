from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton
)
from PySide6.QtCore import Signal, Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QThread
from PySide6.QtGui import QPainter, QColor, QPen, QPixmap
from controllers.auth_controller import AuthController
from utils.settings_manager import SettingsManager
import time
import os


LOGIN_BUTTON_STYLE = """
    QPushButton {
        background-color: #10B981;
        color: white;
        border: none;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 600;
        padding: 0 20px;
    }
    QPushButton:hover {
        background-color: #059669;
    }
    QPushButton:pressed {
        background-color: #047857;
    }
    QPushButton:disabled {
        background-color: #6EE7B7;
        color: #D1FAE5;
    }
"""


SUCCESS_BUTTON_STYLE = """
    QPushButton {
        background-color: #6EE7B7;
        color: #065F46;
        border: none;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 600;
        padding: 0 20px;
    }
"""


class LoadingWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_angle)
        self.setFixedSize(28, 28)
        
    def update_angle(self):
        self.angle = (self.angle + 10) % 360
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen()
        pen.setWidth(3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setColor(QColor("#10B981"))
        painter.setPen(pen)
        rect = self.rect().adjusted(3, 3, -3, -3)
        painter.drawArc(rect, self.angle * 16, 270 * 16)

    def start(self):
        self.timer.start()
        self.show()
        
    def stop(self):
        self.timer.stop()
        self.hide()


class LoginWorker(QThread):
    finished = Signal(object)
    error = Signal(str)
    
    def __init__(self, username, password, auth_controller):
        super().__init__()
        self.username = username
        self.password = password
        self.auth_controller = auth_controller
        
    def run(self):
        try:
            time.sleep(0.3)
            user_data = self.auth_controller.authenticate(self.username, self.password)
            self.finished.emit(user_data)
        except Exception as e:
            self.error.emit(str(e))


class LoginView(QWidget):
    login_successful = Signal(dict, str)

    def __init__(self, auth_controller=None, settings_manager=None):
        super().__init__(
            f=Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowTitle("KORGO Pro — Connexion")
        
        # Fond transparent pour que seule la vue arrondie soit visible  
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.setFixedSize(800, 520)
        
        self.dragging = False
        self.drag_position = QPoint()
        self.worker = None
        self.shake_animation = None
        self.auth_controller = auth_controller or AuthController()
        self.settings_manager = settings_manager or SettingsManager()

        # Layout principal avec marges pour laisser de l'espace autour
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(0)

        # ========================================
        # CONTENEUR PRINCIPAL ARRONDI
        # ========================================
        container = QWidget()
        container.setObjectName("MainContainer")
        container.setStyleSheet("""
            #MainContainer {
                background-color: #ffffff;
                border-radius: 20px;
                border: 1px solid #E5E7EB;
            }
        """)
        
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # ========================================
        # HEADER avec bouton de fermeture
        # ========================================
        header_widget = QWidget()
        header_widget.setObjectName("HeaderWidget")
        header_widget.setFixedHeight(40)
        header_widget.setStyleSheet("""
            #HeaderWidget {
                background: transparent;
                border-top-left-radius: 20px;
                border-top-right-radius: 20px;
            }
        """)
        
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(15, 0, 15, 0)
        header_layout.setSpacing(0)
        
        header_layout.addStretch()
        
        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("CloseBtn")
        self.btn_close.setFixedSize(32, 32)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setToolTip("Fermer l'application")
        self.btn_close.setStyleSheet("""
            #CloseBtn {
                background-color: transparent;
                color: #9CA3AF;
                font-size: 16px;
                border: none;
                border-radius: 16px;
                font-weight: bold;
            }
            #CloseBtn:hover {
                background-color: #FEE2E2;
                color: #EF4444;
            }
            #CloseBtn:pressed {
                background-color: #FECACA;
            }
        """)
        self.btn_close.clicked.connect(self._quit_application)
        header_layout.addWidget(self.btn_close)

        container_layout.addWidget(header_widget)

        # ========================================
        # CONTENU (gauche + droite)
        # ========================================
        content_widget = QWidget()
        content_widget.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
        """)
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # ========================================
        # PARTIE GAUCHE - Logo KORGO (50%)
        # ========================================
        left_panel = QWidget()
        left_panel.setObjectName("LeftPanel")
        left_panel.setStyleSheet("""
            #LeftPanel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #065F46, stop:1 #10B981);
                border-top-left-radius: 20px;
                border-bottom-left-radius: 20px;
            }
        """)
        
        left_layout = QVBoxLayout(left_panel)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.setSpacing(15)
        left_layout.setContentsMargins(30, 50, 30, 50)

        # Logo KORGO
        self.korgo_logo = QLabel()
        self.korgo_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.korgo_logo.setFixedSize(140, 140)
        
        korgo_logo_path = self.settings_manager.get_setting("logo_path", "")
        if korgo_logo_path and os.path.exists(korgo_logo_path):
            pixmap = QPixmap(korgo_logo_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.korgo_logo.setPixmap(scaled)
                self.korgo_logo.setStyleSheet("""
                    QLabel {
                        background-color: rgba(255, 255, 255, 0.1);
                        border-radius: 30px;
                        padding: 10px;
                    }
                """)
            else:
                self._create_korgo_fallback()
        else:
            self._create_korgo_fallback()
        
        left_layout.addWidget(self.korgo_logo)

        title = QLabel("KORGO Pro")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                font-size: 28px;
                font-weight: bold;
                color: white;
                letter-spacing: 2px;
            }
        """)
        left_layout.addWidget(title)

        subtitle = QLabel("Gestion d'entreprise simplifiée")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: rgba(255, 255, 255, 0.7);
            }
        """)
        left_layout.addWidget(subtitle)

        version = QLabel("v1.0.0")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: rgba(255, 255, 255, 0.3);
                margin-top: 20px;
            }
        """)
        left_layout.addWidget(version)

        # ========================================
        # PARTIE DROITE - Formulaire (50%)
        # ========================================
        right_panel = QWidget()
        right_panel.setObjectName("RightPanel")
        right_panel.setStyleSheet("""
            #RightPanel {
                background-color: #ffffff;
                border-top-right-radius: 20px;
                border-bottom-right-radius: 20px;
            }
        """)
        
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(50, 40, 50, 40)
        right_layout.setSpacing(0)

        # Logo entreprise
        self.company_logo = QLabel()
        self.company_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.company_logo.setFixedSize(100, 100)
        
        company_logo_path = self.settings_manager.get_setting("company_logo", "")
        if company_logo_path and os.path.exists(company_logo_path):
            pixmap = QPixmap(company_logo_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(90, 90, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.company_logo.setPixmap(scaled)
                self.company_logo.setStyleSheet("""
                    QLabel {
                        background-color: rgba(16, 185, 129, 0.08);
                        border-radius: 20px;
                        padding: 5px;
                    }
                """)
            else:
                self._create_company_fallback()
        else:
            self._create_company_fallback()
        
        right_layout.addWidget(self.company_logo, alignment=Qt.AlignmentFlag.AlignCenter)

        right_layout.addSpacing(60)

        welcome = QLabel("Bienvenue")
        welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome.setStyleSheet("""
            QLabel {
                font-size: 22px;
                font-weight: bold;
                color: #111827;
            }
        """)
        right_layout.addWidget(welcome, alignment=Qt.AlignmentFlag.AlignCenter)

        desc = QLabel("Connectez-vous à votre compte")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("""
            QLabel {
                font-size: 13px;
                color: #6B7280;
                margin-bottom: 5px;
            }
        """)
        right_layout.addWidget(desc, alignment=Qt.AlignmentFlag.AlignCenter)

        right_layout.addSpacing(30)

        # Champ Utilisateur
        label_user = QLabel("Nom d'utilisateur")
        label_user.setStyleSheet("""
            QLabel {
                font-size: 12px;
                font-weight: 600;
                color: #374151;
                margin-bottom: 4px;
            }
        """)
        right_layout.addWidget(label_user)

        self.username = QLineEdit()
        self.username.setPlaceholderText("Entrez votre identifiant")
        self.username.setMinimumHeight(40)
        self.username.setStyleSheet("""
            QLineEdit {
                background-color: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 14px;
            }
            QLineEdit:focus {
                background-color: white;
                border: 1px solid #10B981;
            }
            QLineEdit::placeholder {
                color: #9CA3AF;
            }
        """)
        right_layout.addWidget(self.username)

        right_layout.addSpacing(15)

        # Champ Mot de passe
        label_pass = QLabel("Mot de passe")
        label_pass.setStyleSheet("""
            QLabel {
                font-size: 12px;
                font-weight: 600;
                color: #374151;
                margin-bottom: 4px;
            }
        """)
        right_layout.addWidget(label_pass)

        self.password = QLineEdit()
        self.password.setPlaceholderText("Entrez votre mot de passe")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setMinimumHeight(40)
        self.password.setStyleSheet("""
            QLineEdit {
                background-color: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 14px;
            }
            QLineEdit:focus {
                background-color: white;
                border: 1px solid #10B981;
            }
            QLineEdit::placeholder {
                color: #9CA3AF;
            }
        """)
        right_layout.addWidget(self.password)

        right_layout.addSpacing(25)

        # Bouton de connexion avec loader
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.loading_widget = LoadingWidget()
        btn_row.addWidget(self.loading_widget)

        self.btn_login = QPushButton("Se connecter")
        self.btn_login.setMinimumHeight(44)
        self.btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_login.setDefault(True)
        self.btn_login.clicked.connect(self.on_login_pressed)
        self.btn_login.setStyleSheet(LOGIN_BUTTON_STYLE)
        btn_row.addWidget(self.btn_login)

        right_layout.addLayout(btn_row)

        right_layout.addSpacing(15)

        # Message d'erreur
        self.error_label = QLabel("")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setWordWrap(True)
        self.error_label.setFixedHeight(0)
        self.error_label.setStyleSheet("""
            QLabel {
                color: #DC2626;
                font-size: 13px;
                padding: 6px 10px;
                background-color: #FEF2F2;
                border: 1px solid #FECACA;
                border-radius: 6px;
            }
        """)
        right_layout.addWidget(self.error_label)

        right_layout.addStretch()

        # Pied de page
        footer = QLabel("© 2026 KORGO Pro — Tous droits réservés")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("""
            QLabel {
                color: #9CA3AF;
                font-size: 11px;
                padding-top: 15px;
                border-top: 1px solid #F3F4F6;
            }
        """)
        right_layout.addWidget(footer)

        # ========================================
        # ASSEMBLAGE FINAL
        # ========================================
        content_layout.addWidget(left_panel, 50)
        content_layout.addWidget(right_panel, 50)
        container_layout.addWidget(content_widget)

        main_layout.addWidget(container)

        # Connexion des touches Entrée
        self.username.returnPressed.connect(self.on_login_pressed)
        self.password.returnPressed.connect(self.on_login_pressed)

        # État initial
        self.error_label.hide()
        self.loading_widget.hide()

        self.raise_()
        self.activateWindow()

    def _create_korgo_fallback(self):
        """Crée un logo de secours pour KORGO"""
        self.korgo_logo.setText("K")
        self.korgo_logo.setStyleSheet("""
            QLabel {
                font-size: 48px;
                font-weight: bold;
                color: white;
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 30px;
                padding: 10px;
            }
        """)

    def _create_company_fallback(self):
        """Crée un logo de secours pour l'entreprise"""
        self.company_logo.setText("🏢")
        self.company_logo.setStyleSheet("""
            QLabel {
                font-size: 40px;
                background-color: rgba(16, 185, 129, 0.08);
                border-radius: 20px;
                padding: 5px;
            }
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.dragging:
            self.move(event.globalPosition().toPoint() - self.drag_position)

    def mouseReleaseEvent(self, event):
        self.dragging = False

    def on_login_pressed(self):
        if self.worker and self.worker.isRunning():
            return

        username = self.username.text().strip()
        password = self.password.text()

        if not username:
            self._show_temporary_error("Veuillez saisir votre nom d'utilisateur")
            self.username.setFocus()
            return

        if not password:
            self._show_temporary_error("Veuillez saisir votre mot de passe")
            self.password.setFocus()
            return

        self.set_loading_state(True)
        self.error_label.hide()
        self.error_label.setFixedHeight(0)

        self.worker = LoginWorker(
            username,
            password,
            self.auth_controller
        )
        self.worker.finished.connect(self.on_authentication_finished)
        self.worker.error.connect(self.on_authentication_error)
        self.worker.start()

    def set_loading_state(self, loading):
        self.username.setEnabled(not loading)
        self.password.setEnabled(not loading)
        self.btn_login.setEnabled(not loading)

        if loading:
            self.loading_widget.show()
            self.loading_widget.start()
            self.btn_login.setText("Connexion...")
        else:
            self.loading_widget.hide()
            self.loading_widget.stop()
            self.btn_login.setText("Se connecter")
            self.btn_login.setStyleSheet(LOGIN_BUTTON_STYLE)

    def on_authentication_finished(self, user_data):
        self.set_loading_state(False)

        if not user_data:
            self.password.clear()
            self._show_temporary_error("Identifiants incorrects")
            self.password.setFocus()
            return

        self._set_success_state()
        theme = self.settings_manager.get_setting("theme", "light")
        QTimer.singleShot(400, lambda: self.login_successful.emit(user_data, theme))

    def on_authentication_error(self, error_message):
        self.set_loading_state(False)
        self._show_temporary_error(f"Erreur: {error_message}")
        self.password.setFocus()

    def _show_temporary_error(self, message):
        """Affiche un message d'erreur éphémère qui disparaît après 3 secondes"""
        self.error_label.setText(f"⚠ {message}")
        self.error_label.setFixedHeight(35)
        self.error_label.show()
        QTimer.singleShot(3000, self._hide_error)

    def _hide_error(self):
        self.error_label.hide()
        self.error_label.setFixedHeight(0)

    def _set_success_state(self):
        self.btn_login.setText("✓ Connecté")
        self.btn_login.setStyleSheet(SUCCESS_BUTTON_STYLE)

    def _shake_animation(self):
        """Animation shake — désactivée pour éviter les warnings setGeometry sur Windows"""
        pass

    def _quit_application(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            app.quit()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait()
        super().closeEvent(event)

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QFrame, QSizePolicy,
    QGraphicsDropShadowEffect, QSpacerItem
)
from PySide6.QtCore import Signal, Qt, QTimer, QPropertyAnimation, QEasingCurve, QSize, QThread, QPoint
from PySide6.QtGui import QMovie, QPainter, QColor, QPen, QPixmap, QFont, QIcon, QPalette, QLinearGradient, QBrush
import time
import os


class LoadingWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_angle)
        self.timer.start(30)
        self.setFixedSize(28, 28)
        
    def update_angle(self):
        self.angle = (self.angle + 10) % 360
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen()
        pen.setWidth(3)
        pen.setCapStyle(Qt.RoundCap)
        pen.setColor(QColor("#3B82F6"))
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
    finished = Signal(dict)
    error = Signal(str)
    
    def __init__(self, username, password, auth_controller):
        super().__init__()
        self.username = username
        self.password = password
        self.auth_controller = auth_controller
        
    def run(self):
        try:
            # Simuler un léger délai pour l'expérience utilisateur
            time.sleep(0.3)
            user_data = self.auth_controller.authenticate(
                self.username,
                self.password
            )
            self.finished.emit(user_data)
        except Exception as e:
            self.error.emit(str(e))


class LoginView(QWidget):
    login_successful = Signal(dict, str)

    def __init__(self):
        super().__init__()
        self.setObjectName("LoginView")
        self.setWindowTitle("KORGO Pro — Connexion")
        # Taille adaptative (peut être redimensionné)
        self.setMinimumSize(420, 540)
        self.resize(420, 540)
        
        # Enlever la barre de titre Windows pour un look moderne
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        
        # Permettre le déplacement de la fenêtre
        self.dragging = False
        self.drag_position = QPoint()
        
        # Worker pour l'authentification
        self.worker = None

        # Layout principal avec fond
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Widget conteneur central avec padding
        container = QWidget()
        container.setObjectName("LoginContainer")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(40, 35, 40, 35)
        container_layout.setSpacing(0)

        # === Barre de titre personnalisée (pour FramelessWindowHint) ===
        title_bar = QWidget()
        title_bar.setObjectName("TitleBar")
        title_bar.setFixedHeight(30)
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("CloseBtn")
        self.btn_close.setFixedSize(28, 28)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.clicked.connect(self.close)
        
        title_bar_layout.addStretch()
        title_bar_layout.addWidget(self.btn_close)
        container_layout.addWidget(title_bar)

        # === Espacement haut ===
        container_layout.addSpacing(15)

        # === Logo ===
        self._build_logo_section(container_layout)
        
        # === Espacement ===
        container_layout.addSpacing(20)

        # === Titre de bienvenue ===
        welcome = QLabel("Bienvenue")
        welcome.setObjectName("WelcomeLabel")
        welcome.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(welcome)

        subtitle = QLabel("Connectez-vous à votre espace")
        subtitle.setObjectName("SubtitleLabel")
        subtitle.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(subtitle)

        container_layout.addSpacing(25)

        # === Champs de formulaire ===
        self._build_form(container_layout)

        container_layout.addSpacing(18)

        # === Bouton de connexion ===
        self._build_buttons(container_layout)

        container_layout.addSpacing(12)

        # === Message d'erreur ===
        self.error_label = QLabel("")
        self.error_label.setObjectName("ErrorLabel")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setWordWrap(True)
        self.error_label.setFixedHeight(0)  # Caché par défaut
        container_layout.addWidget(self.error_label)

        # === Espacement bas ===
        container_layout.addStretch()

        # === Pied de page ===
        footer = QLabel("KORGO Pro v1.0 — Tous droits réservés")
        footer.setObjectName("FooterLabel")
        footer.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(footer)

        main_layout.addWidget(container)

        # === Ombre portée sur le conteneur ===
        self._apply_shadow(container)

        # === Thème ===
        self.apply_light_theme()

        # === État initial ===
        self.error_label.hide()
        self.loading_widget.hide()

    def mousePressEvent(self, event):
        """Permet de déplacer la fenêtre sans barre de titre"""
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """Déplacement de la fenêtre"""
        if event.buttons() == Qt.LeftButton and self.dragging:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        """Fin du déplacement"""
        self.dragging = False
        event.accept()

    def _build_logo_section(self, parent_layout):
        """Construit la section logo"""
        logo_container = QWidget()
        logo_container.setObjectName("LogoSection")
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setAlignment(Qt.AlignCenter)

        # Logo circulaire avec lettre
        self.logo_label = QLabel()
        self.logo_label.setObjectName("LoginLogo")
        self.logo_label.setFixedSize(80, 80)
        self.logo_label.setAlignment(Qt.AlignCenter)

        # Charger le logo ou afficher les initiales
        company_name = "KORGO"
        try:
            from utils.settings_manager import SettingsManager
            settings_manager = SettingsManager()
            company_info = settings_manager.get_company_info()
            company_name = company_info.get('name', 'KORGO').strip()
            logo_path = company_info.get('logo', '')

            if logo_path and os.path.exists(logo_path):
                pixmap = QPixmap(logo_path)
                if not pixmap.isNull():
                    self.logo_label.setPixmap(
                        pixmap.scaled(70, 70, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    )
                    # Ajuster le style pour image
                    self.logo_label.setStyleSheet("""
                        QLabel {
                            background: transparent;
                            border: none;
                            border-radius: 40px;
                        }
                    """)
                else:
                    self._set_text_logo(company_name[0].upper())
            else:
                self._set_text_logo(company_name[0].upper())
        except Exception:
            self._set_text_logo("K")

        logo_layout.addWidget(self.logo_label)
        parent_layout.addWidget(logo_container)

    def _set_text_logo(self, letter):
        """Définit un logo textuel avec cercle de couleur"""
        self.logo_label.setText(letter)
        self.logo_label.setStyleSheet("""
            QLabel {
                font-size: 36px;
                font-weight: bold;
                color: white;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #3B82F6, stop:1 #1D4ED8);
                border-radius: 40px;
                min-width: 80px;
                min-height: 80px;
            }
        """)

    def _build_form(self, parent_layout):
        """Construit les champs du formulaire"""
        # Champ Utilisateur
        user_container = QWidget()
        user_container.setObjectName("FieldContainer")
        user_layout = QVBoxLayout(user_container)
        user_layout.setContentsMargins(0, 0, 0, 0)
        user_layout.setSpacing(6)

        user_label = QLabel("Nom d'utilisateur")
        user_label.setObjectName("FieldLabel")

        self.username = QLineEdit()
        self.username.setObjectName("LoginInput")
        self.username.setPlaceholderText("Entrez votre identifiant")
        self.username.setMinimumHeight(44)

        user_layout.addWidget(user_label)
        user_layout.addWidget(self.username)
        parent_layout.addWidget(user_container)

        parent_layout.addSpacing(14)

        # Champ Mot de passe
        pass_container = QWidget()
        pass_container.setObjectName("FieldContainer")
        pass_layout = QVBoxLayout(pass_container)
        pass_layout.setContentsMargins(0, 0, 0, 0)
        pass_layout.setSpacing(6)

        pass_label = QLabel("Mot de passe")
        pass_label.setObjectName("FieldLabel")

        self.password = QLineEdit()
        self.password.setObjectName("LoginInput")
        self.password.setPlaceholderText("Entrez votre mot de passe")
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setMinimumHeight(44)

        pass_layout.addWidget(pass_label)
        pass_layout.addWidget(self.password)
        parent_layout.addWidget(pass_container)

        # Connexion returnPressed
        self.username.returnPressed.connect(self.on_login_pressed)
        self.password.returnPressed.connect(self.on_login_pressed)

    def _build_buttons(self, parent_layout):
        """Construit les boutons d'action"""
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(10)

        # Loading + Bouton connexion
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.loading_widget = LoadingWidget()
        self.loading_widget.setFixedSize(28, 28)
        btn_row.addWidget(self.loading_widget)

        self.btn_login = QPushButton("Se connecter")
        self.btn_login.setObjectName("LoginBtn")
        self.btn_login.setMinimumHeight(44)
        self.btn_login.setCursor(Qt.PointingHandCursor)
        self.btn_login.setDefault(True)
        self.btn_login.clicked.connect(self.on_login_pressed)

        btn_row.addWidget(self.btn_login, 1)
        btn_layout.addLayout(btn_row)

        parent_layout.addLayout(btn_layout)

    def _apply_shadow(self, widget):
        """Applique une ombre portée"""
        shadow = QGraphicsDropShadowEffect(widget)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 40))
        widget.setGraphicsEffect(shadow)

    def load_company_logo(self, main_layout):
        """Méthode conservée pour compatibilité"""
        pass

    def search_logo_in_common_locations(self, company_name):
        pass

    def show_text_logo(self, company_name):
        pass

    def on_login_pressed(self):
        """Déclenche l'authentification avec effet visuel"""
        self.set_loading_state(True)
        self.error_label.hide()
        self.error_label.setFixedHeight(0)

        from controllers.auth_controller import AuthController
        auth = AuthController()

        self.worker = LoginWorker(
            self.username.text(),
            self.password.text(),
            auth
        )
        self.worker.finished.connect(self.on_authentication_finished)
        self.worker.error.connect(self.on_authentication_error)
        self.worker.start()

    def on_cancel_pressed(self):
        """Quitter"""
        QTimer.singleShot(100, self.close)

    def set_loading_state(self, loading):
        """Active ou désactive l'état de chargement"""
        self.username.setEnabled(not loading)
        self.password.setEnabled(not loading)
        self.btn_login.setEnabled(not loading)

        if loading:
            self.loading_widget.show()
            self.loading_widget.start()
            self.btn_login.setText("Connexion…")
        else:
            self.loading_widget.hide()
            self.loading_widget.stop()
            self.btn_login.setText("Se connecter")

    def on_authentication_finished(self, user_data):
        self.set_loading_state(False)

        if not user_data:
            self.password.clear()
            self._show_error("Identifiants incorrects")
            self.password.setFocus()
            # Animation de shake
            self._shake_animation()
            return

        # Animation de succès
        self.btn_login.setText("✓ Connecté")
        self.btn_login.setStyleSheet(self.btn_login.styleSheet().replace("#3B82F6", "#10B981"))
        QTimer.singleShot(400, lambda: self.login_successful.emit(user_data, "light"))

    def on_authentication_error(self, error_message):
        self.set_loading_state(False)
        self._show_error(f"Erreur: {error_message}")
        self.password.setFocus()

    def _show_error(self, message):
        """Affiche un message d'erreur stylisé"""
        self.error_label.setText(f"⚠ {message}")
        self.error_label.setFixedHeight(35)
        self.error_label.show()

    def _shake_animation(self):
        """Animation de shake pour indiquer une erreur"""
        original_pos = self.pos()
        shake = QPropertyAnimation(self, b"pos")
        shake.setDuration(300)
        shake.setLoopCount(1)
        shake.setKeyValueAt(0, original_pos)
        shake.setKeyValueAt(0.1, original_pos + QPoint(8, 0))
        shake.setKeyValueAt(0.2, original_pos - QPoint(8, 0))
        shake.setKeyValueAt(0.3, original_pos + QPoint(6, 0))
        shake.setKeyValueAt(0.4, original_pos - QPoint(6, 0))
        shake.setKeyValueAt(0.5, original_pos + QPoint(4, 0))
        shake.setKeyValueAt(0.6, original_pos - QPoint(4, 0))
        shake.setKeyValueAt(0.7, original_pos + QPoint(2, 0))
        shake.setKeyValueAt(0.8, original_pos - QPoint(2, 0))
        shake.setKeyValueAt(1, original_pos)
        shake.setEasingCurve(QEasingCurve.OutCubic)
        shake.start()

    def apply_light_theme(self):
        """Applique le thème moderne"""
        self.setStyleSheet("""
            /* Fond de la fenêtre avec dégradé */
            #LoginView {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #EFF6FF, stop:1 #DBEAFE);
            }

            /* Conteneur central (carte blanche) */
            #LoginContainer {
                background-color: white;
                border-radius: 16px;
                margin: 12px;
            }

            /* Barre de titre */
            #TitleBar {
                background: transparent;
            }
            #CloseBtn {
                background-color: transparent;
                color: #9CA3AF;
                font-size: 14px;
                border: none;
                border-radius: 14px;
                font-weight: bold;
            }
            #CloseBtn:hover {
                background-color: #FEE2E2;
                color: #EF4444;
            }

            /* Logo section */
            #LogoSection {
                background: transparent;
            }
            #LoginLogo {
                font-size: 32px;
                font-weight: bold;
            }

            /* Bienvenue */
            #WelcomeLabel {
                font-size: 22px;
                font-weight: bold;
                color: #111827;
                letter-spacing: -0.5px;
            }
            #SubtitleLabel {
                font-size: 13px;
                color: #6B7280;
                margin-top: 4px;
            }

            /* Labels des champs */
            #FieldLabel {
                font-size: 12px;
                font-weight: 600;
                color: #374151;
                letter-spacing: 0.3px;
            }

            /* Champs de saisie */
            #LoginInput {
                background-color: #F9FAFB;
                border: 2px solid #E5E7EB;
                border-radius: 10px;
                padding: 10px 14px;
                font-size: 14px;
                color: #111827;
                selection-background-color: #BFDBFE;
            }
            #LoginInput:focus {
                background-color: white;
                border-color: #3B82F6;
            }
            #LoginInput:hover:not(:focus) {
                border-color: #D1D5DB;
                background-color: #F3F4F6;
            }
            #LoginInput::placeholder {
                color: #9CA3AF;
                font-size: 13px;
            }

            /* Bouton connexion */
            #LoginBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #3B82F6, stop:1 #2563EB);
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 15px;
                font-weight: 600;
                letter-spacing: 0.3px;
            }
            #LoginBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #2563EB, stop:1 #1D4ED8);
            }
            #LoginBtn:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1D4ED8, stop:1 #1E40AF);
            }
            #LoginBtn:disabled {
                background: #93C5FD;
                color: #DBEAFE;
            }

            /* Message d'erreur */
            #ErrorLabel {
                color: #DC2626;
                font-size: 13px;
                font-weight: 500;
                padding: 8px 12px;
                background-color: #FEF2F2;
                border: 1px solid #FECACA;
                border-radius: 8px;
            }

            /* Footer */
            #FooterLabel {
                color: #9CA3AF;
                font-size: 10px;
                padding-top: 8px;
                border-top: 1px solid #F3F4F6;
            }
        """)

    def closeEvent(self, event):
        """Nettoyer à la fermeture"""
        if self.worker and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait()
        super().closeEvent(event)
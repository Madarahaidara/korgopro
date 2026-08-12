from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QFrame, QSizePolicy,
    QSpacerItem, QApplication, QCheckBox
)
from PySide6.QtCore import Signal, Qt, QTimer, QPropertyAnimation, QEasingCurve, QSize, QThread, QRect, QPoint
from PySide6.QtGui import QMovie, QPainter, QColor, QPen, QPixmap, QFont, QIcon, QLinearGradient, QBrush, QScreen, QFontDatabase
import time
import os


class LoadingWidget(QWidget):
    """Spinner de chargement animé premium"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LoadingWidget")
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_angle)
        self.timer.start(30)
        self.setFixedSize(26, 26)
        
    def update_angle(self):
        self.angle = (self.angle + 10) % 360
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        pen = QPen()
        pen.setWidth(3)
        pen.setCapStyle(Qt.RoundCap)
        pen.setColor(QColor("#2F4255"))
        painter.setPen(pen)
        
        rect = self.rect().adjusted(3, 3, -3, -3)
        painter.drawArc(rect, self.angle * 16, 200 * 16)
        
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
            time.sleep(0.5)
            user_data = self.auth_controller.authenticate(
                self.username,
                self.password
            )
            self.finished.emit(user_data)
        except Exception as e:
            self.error.emit(str(e))


class AnimatedIconWidget(QWidget):
    """Widget icône animé avec effet pulse subtil"""
    
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setObjectName("BrandIcon")
        self.text = text
        self.scale = 1.0
        self.scale_direction = 1
        
        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self.animate_pulse)
        self.pulse_timer.start(2000)
        
    def animate_pulse(self):
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(1000)
        anim.setStartValue(1.0)
        anim.setEndValue(0.85)
        anim.setEasingCurve(QEasingCurve.InOutSine)
        
        anim_back = QPropertyAnimation(self, b"windowOpacity")
        anim_back.setDuration(1000)
        anim_back.setStartValue(0.85)
        anim_back.setEndValue(1.0)
        anim_back.setEasingCurve(QEasingCurve.InOutSine)
        
        anim.finished.connect(anim_back.start)
        anim.start()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Fond glassmorphique
        painter.setPen(Qt.NoPen)
        brush = QBrush(QColor(255, 255, 255, 40))
        painter.setBrush(brush)
        painter.drawRoundedRect(self.rect(), 22, 22)
        
        # Texte
        painter.setPen(QColor(255, 255, 255))
        font = painter.font()
        font.setPointSize(32)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter, self.text)


class LeftPanel(QWidget):
    """Panneau gauche premium avec branding et illustration"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LeftPanel")
        self.setMinimumWidth(280)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(8)
        
        # Spacer en haut
        layout.addStretch(1)
        
        # Logo de la marque - GRAND FORMAT
        icon_container = QWidget()
        icon_center_layout = QHBoxLayout(icon_container)
        icon_center_layout.setContentsMargins(20, 0, 20, 0)
        
        self.logo_label = QLabel()
        self.logo_label.setObjectName("BrandLogo")
        self.logo_label.setMinimumSize(140, 140)
        self.logo_label.setMaximumSize(180, 180)
        self.logo_label.setAlignment(Qt.AlignCenter)
        # Accessibilité
        try:
            self.logo_label.setAccessibleName("Logo Korgo Pro")
            self.logo_label.setAccessibleDescription("Logo de l'application Korgo Pro")
        except Exception:
            pass
        
        # Charger le logo depuis le fichier
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "icons", "logo.ico")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                self.logo_label.setPixmap(pixmap.scaled(140, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.logo_label.setText("K")
                self.logo_label.setStyleSheet("color: white; font-size: 120px; font-weight: bold;")
        else:
            self.logo_label.setText("K")
            self.logo_label.setStyleSheet("color: white; font-size: 120px; font-weight: bold;")
        
        icon_center_layout.addStretch()
        icon_center_layout.addWidget(self.logo_label)
        icon_center_layout.addStretch()
        layout.addWidget(icon_container)
        
        # Titre avec effet de fondu
        self.title_label = QLabel("KORGO PRO")
        self.title_label.setObjectName("BrandTitle")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)
        
        # Sous-titre
        subtitle = QLabel("Système de Gestion d'Entreprise")
        subtitle.setObjectName("BrandSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)
        layout.addSpacing(10)
        
        # Séparateur décoratif
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("background-color: rgba(255,255,255,0.15); max-height: 1px;")
        divider.setFixedHeight(1)
        divider_container = QWidget()
        divider_layout = QHBoxLayout(divider_container)
        divider_layout.setContentsMargins(60, 0, 60, 0)
        divider_layout.addWidget(divider)
        layout.addWidget(divider_container)
        
        layout.addSpacing(12)
        
        # Liste des fonctionnalités principales (en dessous du logo)
        features = [
            "✓ Gestion des ventes",
            "✓ Contrôle de stock",
            "✓ Rapports & analyses",
            "✓ Sécurité renforcée"
        ]
        
        features_container = QWidget()
        features_layout = QVBoxLayout(features_container)
        features_layout.setContentsMargins(20, 0, 20, 0)
        features_layout.setSpacing(4)
        
        for feature in features:
            feat_label = QLabel(feature)
            feat_label.setObjectName("FeatureItem")
            feat_label.setAlignment(Qt.AlignCenter)
            features_layout.addWidget(feat_label)
        
        layout.addWidget(features_container)
        
        # Spacer en bas
        layout.addStretch(2)
        
        # Version
        version_label = QLabel("v0.1.0")
        version_label.setObjectName("VersionLabel")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)


class LoginInputField(QWidget):
    """Champ de saisie premium avec icône intégrée"""
    
    def __init__(self, icon_text, placeholder, echo_mode=QLineEdit.Normal, parent=None):
        super().__init__(parent)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Champ de saisie
        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.setEchoMode(echo_mode)
        
        # Accessibilité : nom et description accessibles
        try:
            self.input.setAccessibleName(placeholder)
            self.input.setAccessibleDescription(f"Champ de saisie : {placeholder}")
        except Exception:
            pass
        
        # Style déjà géré par le QSS
        self.input.setObjectName("LoginInput")
        
        layout.addWidget(self.input)
    
    def text(self):
        return self.input.text()
    
    def clear(self):
        self.input.clear()
    
    def setFocus(self):
        self.input.setFocus()
    
    def setEnabled(self, enabled):
        self.input.setEnabled(enabled)
    
    def setEchoMode(self, mode):
        self.input.setEchoMode(mode)


class LoginView(QWidget):
    login_successful = Signal(dict, str)

    def __init__(self):
        super().__init__()
        self.setObjectName("LoginView")
        self.setWindowTitle("Korgo Pro - Connexion")
        
        # Taille moderne et élégante
        self.setFixedSize(800, 520)
        
        # Centrer sur l'écran
        screen = QScreen.availableGeometry(QApplication.primaryScreen())
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2
        )
        
        # Supprimer la bordure de la fenêtre pour un look moderne
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Worker pour l'authentification
        self.worker = None
        
        # Layout principal
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setAlignment(Qt.AlignCenter)
        
        # === Fenêtre principale avec ombre portée ===
        # Utilisation d'un conteneur externe pour l'effet d'ombre
        outer_container = QFrame()
        outer_container.setObjectName("OuterContainer")
        outer_container.setFixedSize(760, 480)
        
        outer_layout = QHBoxLayout(outer_container)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        
        # Conteneur principal avec coins arrondis
        container = QFrame()
        container.setObjectName("LoginContainer")
        
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # ===== PANEL GAUCHE (Branding) =====
        self.left_panel = LeftPanel()
        container_layout.addWidget(self.left_panel)
        
        # ===== PANEL DROIT (Formulaire) =====
        right_panel = QWidget()
        right_panel.setObjectName("RightPanel")
        right_panel.setMinimumWidth(420)
        
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(40, 40, 40, 30)
        right_layout.setSpacing(3)
        
        # Espacement haut
        right_layout.addStretch(1)
        
        # Titre du formulaire
        form_title = QLabel("Connexion")
        form_title.setObjectName("FormTitle")
        right_layout.addWidget(form_title)
        
        form_subtitle = QLabel("Connectez-vous à votre espace de gestion")
        form_subtitle.setObjectName("FormSubtitle")
        right_layout.addWidget(form_subtitle)
        
        right_layout.addSpacing(18)
        
        # Champ Utilisateur
        user_label = QLabel("UTILISATEUR")
        user_label.setObjectName("FieldLabel")
        right_layout.addWidget(user_label)
        
        right_layout.addSpacing(6)
        
        self.username = LoginInputField("👤", "Nom d'utilisateur")
        right_layout.addWidget(self.username)
        
        right_layout.addSpacing(12)
        
        # Champ Mot de passe
        pass_label = QLabel("MOT DE PASSE")
        pass_label.setObjectName("FieldLabel")
        right_layout.addWidget(pass_label)
        
        right_layout.addSpacing(6)
        
        self.password = LoginInputField("🔒", "Mot de passe", QLineEdit.Password)
        right_layout.addWidget(self.password)
        
        right_layout.addSpacing(6)
        
        right_layout.addSpacing(14)
        
        # Boutons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(14)
        
        # Chargement
        self.loading_widget = LoadingWidget()
        self.loading_widget.hide()
        btn_layout.addWidget(self.loading_widget)
        
        # Bouton Se connecter premium
        self.btn_login = QPushButton("Se connecter")
        self.btn_login.setObjectName("LoginButton")
        self.btn_login.setCursor(Qt.PointingHandCursor)
        self.btn_login.setFixedHeight(44)
        self.btn_login.setFixedWidth(140)
        try:
            self.btn_login.setAccessibleName("Bouton Se connecter")
            self.btn_login.setAccessibleDescription("Valider les identifiants et se connecter à l'application")
        except Exception:
            pass
        btn_layout.addWidget(self.btn_login)
        
        # Bouton Quitter
        self.btn_cancel = QPushButton("Quitter")
        self.btn_cancel.setObjectName("CancelButton")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setFixedHeight(44)
        self.btn_cancel.setFixedWidth(140)
        try:
            self.btn_cancel.setAccessibleName("Bouton Quitter")
            self.btn_cancel.setAccessibleDescription("Fermer l'application")
        except Exception:
            pass
        btn_layout.addWidget(self.btn_cancel)
        
        btn_layout.addStretch()
        
        right_layout.addLayout(btn_layout)
        
        # Message d'erreur
        right_layout.addSpacing(8)
        self.error_label = QLabel("")
        self.error_label.setObjectName("ErrorLabel")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        right_layout.addWidget(self.error_label)
        
        # Espacement bas
        right_layout.addStretch(2)
        
        # Label de sécurité avec icône
        secure_layout = QHBoxLayout()
        secure_label = QLabel("🔒 Connexion sécurisée")
        secure_label.setObjectName("SecureLabel")
        secure_layout.addWidget(secure_label)
        secure_layout.addStretch()
        right_layout.addLayout(secure_layout)
        
        container_layout.addWidget(right_panel)
        
        outer_layout.addWidget(container)
        main_layout.addWidget(outer_container)
        
        # Connecter les signaux
        self.btn_login.setDefault(True)
        self.username.input.returnPressed.connect(self.on_login_pressed)
        self.password.input.returnPressed.connect(self.on_login_pressed)
        self.btn_login.clicked.connect(self.on_login_pressed)
        self.btn_cancel.clicked.connect(self.on_cancel_pressed)
        
        # Animation d'apparition
        self.fade_in()
        
        # Appliquer le thème
        self.apply_theme()

    def fade_in(self):
        """Animation d'apparition en fondu"""
        self.setWindowOpacity(0.0)
        self.fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self.fade_anim.setDuration(400)
        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.fade_anim.start()

    def slide_error(self):
        """Animation d'apparition du message d'erreur"""
        if not self.error_label.isHidden():
            anim = QPropertyAnimation(self.error_label, b"maximumHeight")
            anim.setDuration(200)
            anim.setStartValue(0)
            anim.setEndValue(60)
            anim.setEasingCurve(QEasingCurve.OutBack)
            
            anim_opacity = QPropertyAnimation(self.error_label, b"windowOpacity")
            anim_opacity.setDuration(200)
            anim_opacity.setStartValue(0.0)
            anim_opacity.setEndValue(1.0)
            
            anim.start()
            anim_opacity.start()

    def on_login_pressed(self):
        """Déclenche l'authentification avec effet visuel"""
        # Validation rapide
        if not self.username.text().strip():
            self.error_label.setText("⚠️ Veuillez saisir votre nom d'utilisateur")
            self.error_label.show()
            self.slide_error()
            self.username.setFocus()
            return
        
        if not self.password.text():
            self.error_label.setText("⚠️ Veuillez saisir votre mot de passe")
            self.error_label.show()
            self.slide_error()
            self.password.setFocus()
            return
        
        self.set_loading_state(True)
        self.error_label.hide()
        
        from controllers.auth_controller import AuthController
        auth = AuthController()
        
        self.worker = LoginWorker(
            self.username.text().strip(),
            self.password.text(),
            auth
        )
        self.worker.finished.connect(self.on_authentication_finished)
        self.worker.error.connect(self.on_authentication_error)
        self.worker.start()

    def on_cancel_pressed(self):
        """Quitter l'application avec animation"""
        self.animate_button_press(self.btn_cancel)
        
        # Animation de fermeture
        self.close_anim = QPropertyAnimation(self, b"windowOpacity")
        self.close_anim.setDuration(200)
        self.close_anim.setStartValue(1.0)
        self.close_anim.setEndValue(0.0)
        self.close_anim.setEasingCurve(QEasingCurve.InCubic)
        self.close_anim.finished.connect(self.close)
        self.close_anim.start()

    def animate_button_press(self, button):
        """Animation de pression sur le bouton"""
        anim = QPropertyAnimation(button, b"geometry")
        anim.setDuration(80)
        start = button.geometry()
        pressed = start.adjusted(2, 2, -2, -2)
        anim.setStartValue(start)
        anim.setEndValue(pressed)
        anim.setEasingCurve(QEasingCurve.OutQuad)
        
        anim_back = QPropertyAnimation(button, b"geometry")
        anim_back.setDuration(80)
        anim_back.setStartValue(pressed)
        anim_back.setEndValue(start)
        anim_back.setEasingCurve(QEasingCurve.OutQuad)
        
        anim.finished.connect(anim_back.start)
        anim.start()

    def set_loading_state(self, loading):
        """Active ou désactive l'état de chargement"""
        self.username.setEnabled(not loading)
        self.password.setEnabled(not loading)
        self.btn_login.setEnabled(not loading)
        self.btn_cancel.setEnabled(not loading)
        
        if loading:
            self.loading_widget.show()
            self.loading_widget.start()
            self.btn_login.setText("Connexion...")
        else:
            self.loading_widget.hide()
            self.loading_widget.stop()
            self.btn_login.setText("Se connecter")

    def on_authentication_finished(self, user_data):
        """Appelé quand l'authentification est terminée"""
        self.set_loading_state(False)
        
        if not user_data:
            self.password.clear()
            self.password.setFocus()
            
            # Animation shake sur le champ mot de passe
            self.error_label.setText("❌ Identifiants incorrects")
            self.error_label.show()
            self.slide_error()
            
            # Effet shake sur le conteneur
            self.shake_animation()
            return
        
        # Succès - animation de transition
        self.success_animation()
        QTimer.singleShot(500, lambda: self.login_successful.emit(user_data, "light"))

    def success_animation(self):
        """Animation de succès avant transition"""
        self.btn_login.setText("✓ Connecté")
        self.btn_login.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: white;
                border: none;
                border-radius: 12px;
                padding: 14px 24px;
                font-size: 15px;
                font-weight: 600;
                min-height: 22px;
            }
        """)
        
        # Animation de progression vers la vue suivante
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(300)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()

    def shake_animation(self):
        """Effet shake pour indiquer une erreur"""
        original_pos = self.pos()
        shake_steps = [(original_pos.x() - 10, original_pos.y()),
                       (original_pos.x() + 10, original_pos.y()),
                       (original_pos.x() - 5, original_pos.y()),
                       (original_pos.x() + 5, original_pos.y()),
                       (original_pos.x(), original_pos.y())]
        
        for i, (x, y) in enumerate(shake_steps):
            QTimer.singleShot(i * 40, lambda px=x, py=y: self.move(px, py))

    def on_authentication_error(self, error_message):
        """Appelé quand il y a une erreur d'authentification"""
        self.set_loading_state(False)
        self.error_label.setText(f"❌ Erreur: {error_message}")
        self.error_label.show()
        self.slide_error()
        self.password.setFocus()

    def apply_theme(self):
        """Applique le thème depuis le fichier QSS ou le style par défaut"""
        import os
        
        possible_paths = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "themes", "login.qss"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes", "login.qss"),
        ]
        
        for path in possible_paths:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.setStyleSheet(f.read())
                    return
            except FileNotFoundError:
                continue
        
        # Style par défaut si le fichier QSS n'est pas trouvé
        self.setStyleSheet("""
            LoginView {
                background-color: #f0f4f8;
            }
        """)
    
    def closeEvent(self, event):
        """Nettoyer les ressources à la fermeture"""
        if self.worker and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait()
        super().closeEvent(event)
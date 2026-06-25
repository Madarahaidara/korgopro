from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QFrame, QSizePolicy
)

from PySide6.QtCore import (
    Signal, Qt, QTimer, QPropertyAnimation,
    QEasingCurve, QThread
)

from PySide6.QtGui import (
    QPainter, QColor, QPen
)

import time


class LoadingWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.angle = 0

        self.timer = QTimer(self)

        self.timer.timeout.connect(
            self.update_angle
        )

        self.timer.start(30)

        self.setFixedSize(380, 460)
        

    def update_angle(self):

        self.angle = (
            self.angle + 10
        ) % 360

        self.update()

    def paintEvent(self, event):

        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.Antialiasing
        )

        pen = QPen()

        pen.setWidth(3)

        pen.setCapStyle(
            Qt.RoundCap
        )

        pen.setColor(
            QColor("#2a82da")
        )

        painter.setPen(pen)

        rect = self.rect().adjusted(
            5, 5, -5, -5
        )

        painter.drawArc(
            rect,
            self.angle * 16,
            200 * 16
        )

    def start(self):

        self.timer.start()

        self.show()

    def stop(self):

        self.timer.stop()

        self.hide()


class UnlockWorker(QThread):

    finished = Signal(bool)

    error = Signal(str)

    def __init__(
        self,
        username,
        password,
        auth_controller
    ):
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

            self.finished.emit(
                bool(user_data)
            )

        except Exception as e:

            self.error.emit(str(e))


class LockScreen(QDialog):

    unlocked = Signal()

    def __init__(
        self,
        username="",
        parent=None
    ):
        super().__init__(parent)

        self.worker = None

        self.setObjectName(
            "LockScreen"
        )

        self.setWindowTitle(
            "Session verrouillée"
        )

        self.setModal(True)

        # Taille fixe : 380x460
        self.setFixedSize(380, 460)

        # Supprimer les flags de redimensionnement
        self.setWindowFlags(
            Qt.Dialog |
            Qt.CustomizeWindowHint |
            Qt.WindowTitleHint |
            Qt.WindowCloseButtonHint
        )

        # Désactiver le redimensionnement
        self.setSizeGripEnabled(False)

        main_layout = QVBoxLayout(self)

        main_layout.setContentsMargins(
            20, 20, 20, 10
        )

        main_layout.setSpacing(15)

        # ===== HEADER =====

        self.lock_icon = QLabel("🔒")

        self.lock_icon.setAlignment(
            Qt.AlignCenter
        )

        self.lock_icon.setStyleSheet("""
            QLabel {
                font-size: 54px;
                padding: 10px;
            }
        """)

        title = QLabel(
            "Session verrouillée"
        )

        title.setAlignment(
            Qt.AlignCenter
        )

        title.setStyleSheet("""
            QLabel {
                font-size: 22px;
                font-weight: bold;
                color: #2a82da;
            }
        """)

        subtitle = QLabel(
            "Entrez votre mot de passe pour continuer"
        )

        subtitle.setAlignment(
            Qt.AlignCenter
        )

        subtitle.setStyleSheet("""
            QLabel {
                color: #777777;
                font-size: 12px;
            }
        """)

        main_layout.addWidget(
            self.lock_icon
        )

        main_layout.addWidget(title)

        main_layout.addWidget(subtitle)

        # ===== FORMULAIRE =====

        form_layout = QGridLayout()

        form_layout.setHorizontalSpacing(10)

        form_layout.setVerticalSpacing(12)

        lbl_user = QLabel("Utilisateur")

        lbl_pass = QLabel("Mot de passe")

        self.username = QLineEdit()

        self.username.setText(username)

        self.username.setReadOnly(True)

        self.username.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed
        )

        self.password = QLineEdit()

        self.password.setEchoMode(
            QLineEdit.Password
        )

        self.password.setPlaceholderText(
            "••••••••"
        )

        self.password.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed
        )

        form_layout.addWidget(
            lbl_user,
            0,
            0
        )

        form_layout.addWidget(
            self.username,
            0,
            1
        )

        form_layout.addWidget(
            lbl_pass,
            1,
            0
        )

        form_layout.addWidget(
            self.password,
            1,
            1
        )

        form_layout.setColumnStretch(
            1,
            1
        )

        main_layout.addLayout(
            form_layout
        )

        # ===== LOADING + BUTTON =====

        btn_layout = QHBoxLayout()

        self.loading_container = QFrame()

        self.loading_container.setFixedSize(
            50,
            50
        )

        self.loading_container.hide()

        self.loading_widget = LoadingWidget(
            self.loading_container
        )

        self.loading_widget.setGeometry(
            0,
            0,
            50,
            50
        )

        btn_layout.addWidget(
            self.loading_container
        )

        btn_layout.addStretch()

        self.btn_unlock = QPushButton(
            "Déverrouiller"
        )

        self.btn_unlock.setMinimumWidth(
            140
        )

        self.btn_unlock.setDefault(True)

        self.btn_unlock.setCursor(
            Qt.PointingHandCursor
        )

        btn_layout.addWidget(
            self.btn_unlock
        )

        main_layout.addLayout(
            btn_layout
        )

        # ===== ERREUR =====

        self.error_label = QLabel()

        self.error_label.hide()

        self.error_label.setAlignment(
            Qt.AlignCenter
        )

        self.error_label.setObjectName(
            "ErrorLabel"
        )

        main_layout.addWidget(
            self.error_label
        )

        secure = QLabel(
            "🔒 Secure connection"
        )

        secure.setAlignment(
            Qt.AlignLeft
        )

        secure.setObjectName(
            "SecureLabel"
        )

        main_layout.addWidget(
            secure
        )

        # ===== EVENTS =====

        self.password.returnPressed.connect(
            self.on_unlock_pressed
        )

        self.btn_unlock.clicked.connect(
            self.on_unlock_pressed
        )

        self.apply_theme()

        self.password.setFocus()

    def on_unlock_pressed(self):

        self.error_label.hide()

        self.set_loading_state(True)

        from controllers.auth_controller import (
            AuthController
        )

        auth = AuthController()

        self.worker = UnlockWorker(
            self.username.text(),
            self.password.text(),
            auth
        )

        self.worker.finished.connect(
            self.on_auth_finished
        )

        self.worker.error.connect(
            self.on_auth_error
        )

        self.worker.start()

    def set_loading_state(
        self,
        loading
    ):

        self.password.setEnabled(
            not loading
        )

        self.btn_unlock.setEnabled(
            not loading
        )

        if loading:

            self.loading_container.show()

            self.loading_widget.start()

            self.btn_unlock.setText(
                "Vérification..."
            )

        else:

            self.loading_container.hide()

            self.loading_widget.stop()

            self.btn_unlock.setText(
                "Déverrouiller"
            )

    def on_auth_finished(
        self,
        success
    ):

        self.set_loading_state(False)

        if not success:

            self.password.clear()

            self.error_label.setText(
                "❌ Mot de passe incorrect"
            )

            self.error_label.show()

            self.password.setFocus()

            return

        self.unlocked.emit()

        self.accept()

    def on_auth_error(
        self,
        message
    ):

        self.set_loading_state(False)

        self.error_label.setText(
            f"❌ {message}"
        )

        self.error_label.show()

        self.password.setFocus()

    def apply_theme(self):

        self.setStyleSheet("""
            QWidget, QDialog {
                background-color: #f5f5f5;
                font-family: 'Segoe UI', Arial, sans-serif;
            }

            QLabel {
                color: #333333;
                font-size: 12px;
            }

            QLineEdit {
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 8px;
                background-color: white;
                font-size: 13px;
                min-height: 20px;
            }

            QLineEdit:focus {
                border: 1px solid #2a82da;
            }

            QPushButton {
                background-color: #2a82da;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
                min-height: 30px;
            }

            QPushButton:hover {
                background-color: #1e6bb8;
            }

            QPushButton:pressed {
                background-color: #155a9e;
            }

            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }

            #ErrorLabel {
                color: #e74c3c;
                font-size: 12px;
                padding: 5px;
                background-color: #ffeaea;
                border-radius: 3px;
                border: 1px solid #ffcccc;
            }

            #SecureLabel {
                color: #27ae60;
                font-size: 11px;
                padding-top: 10px;
            }
        """)

    def reject(self):

        pass

    def closeEvent(
        self,
        event
    ):

        event.ignore()

    def keyPressEvent(
        self,
        event
    ):

        if event.key() == Qt.Key_Escape:

            return

        super().keyPressEvent(event)
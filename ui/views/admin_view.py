from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QFrame, QMessageBox, QComboBox,
    QHeaderView, QAbstractItemView, QCheckBox, QDialog,
    QFormLayout, QLineEdit, QSpinBox, QTextEdit, QGroupBox
)
from PySide6.QtCore import Qt, Signal, QTimer, QDateTime
from PySide6.QtGui import QFont, QColor, QBrush
from datetime import datetime
from typing import Dict, Any, List

# Import du gestionnaire de paramètres
from utils.settings_manager import SettingsManager

# Import des modèles
from core.models.user import User


class AdminView(QWidget):
    """Vue d'administration pour la gestion des utilisateurs et permissions"""
    
    # Signaux
    user_created = Signal(dict)
    user_updated = Signal(dict)
    user_deleted = Signal(int)
    
    def __init__(self, user_data: Dict[str, Any]):
        super().__init__()
        self.current_user = user_data
        self.settings_manager = SettingsManager()
        
        # Taille adaptative (pas de setGeometry fixe)
        self.resize(1200, 750)
        self.setMinimumSize(900, 600)
        
        self.setWindowTitle("Administration")
        
        # Variables
        self.users = []
        self.filtered_users = []
        
        # Interface
        self.init_ui()
        self.apply_light_theme()
        
        # Charger les données
        self.load_users()
    
    def init_ui(self):
        """Initialise l'interface utilisateur"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # En-tête
        header_layout = QHBoxLayout()
        
        title_label = QLabel("Administration")
        title_label.setObjectName("pageTitle")
        title_font = QFont("Segoe UI", 18, QFont.Bold)
        title_label.setFont(title_font)
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        # Bouton créer utilisateur
        create_user_btn = QPushButton("+ Nouvel utilisateur")
        create_user_btn.setObjectName("primaryButton")
        create_user_btn.clicked.connect(self.show_create_user_dialog)
        header_layout.addWidget(create_user_btn)
        
        main_layout.addLayout(header_layout)
        
        # Filtres
        filters_frame = QFrame()
        filters_frame.setObjectName("filtersFrame")
        filters_layout = QHBoxLayout(filters_frame)
        
        # Recherche
        search_label = QLabel("Recherche:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Nom, email, rôle...")
        self.search_input.textChanged.connect(self.filter_users)
        
        # Filtre par rôle
        role_label = QLabel("Rôle:")
        self.role_filter = QComboBox()
        self.role_filter.addItem("Tous les rôles")
        self.role_filter.addItems(["ADMIN", "GERANT", "CAISSIER", "STOCKIST", "ACCOUNTANT"])
        self.role_filter.currentTextChanged.connect(self.filter_users)
        
        # Filtre par statut
        status_label = QLabel("Statut:")
        self.status_filter = QComboBox()
        self.status_filter.addItem("Tous les statuts")
        self.status_filter.addItems(["Actif", "Inactif"])
        self.status_filter.currentTextChanged.connect(self.filter_users)
        
        filters_layout.addWidget(search_label)
        filters_layout.addWidget(self.search_input, 2)
        filters_layout.addWidget(role_label)
        filters_layout.addWidget(self.role_filter, 1)
        filters_layout.addWidget(status_label)
        filters_layout.addWidget(self.status_filter, 1)
        
        main_layout.addWidget(filters_frame)
        
        # Tableau des utilisateurs
        self.users_table = QTableWidget()
        self.users_table.setObjectName("usersTable")
        self.setup_table()
        
        main_layout.addWidget(self.users_table)
        
        # Barre de statistiques
        stats_frame = QFrame()
        stats_frame.setObjectName("statsFrame")
        stats_layout = QHBoxLayout(stats_frame)
        
        self.total_users_label = QLabel("Total: 0")
        self.active_users_label = QLabel("Actifs: 0")
        self.admin_users_label = QLabel("Admins: 0")
        
        stats_layout.addWidget(self.total_users_label)
        stats_layout.addWidget(self.active_users_label)
        stats_layout.addWidget(self.admin_users_label)
        stats_layout.addStretch()
        
        main_layout.addWidget(stats_frame)
    
    def setup_table(self):
        """Configure le tableau des utilisateurs"""
        headers = ["ID", "Nom d'utilisateur", "Email", "Rôle", "Statut", "Dernière connexion", "Actions"]
        self.users_table.setColumnCount(len(headers))
        self.users_table.setHorizontalHeaderLabels(headers)
        
        # Configuration des colonnes
        header = self.users_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Nom
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # Email
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Rôle
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Statut
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Connexion
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Actions
        
        self.users_table.setAlternatingRowColors(True)
        self.users_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.users_table.setSelectionMode(QAbstractItemView.SingleSelection)
        
        # Charger les données
        self.load_users_table()
    
    def load_users(self):
        """Charge les utilisateurs depuis la base de données"""
        try:
            from core.database import SessionLocal
            from sqlalchemy.orm import joinedload
            
            db = SessionLocal()
            try:
                self.users = db.query(User).order_by(User.id).all()
                self.filtered_users = self.users.copy()
                self.load_users_table()
                self.update_stats()
            finally:
                db.close()
        except Exception as e:
            print(f"Erreur lors du chargement des utilisateurs: {e}")
            QMessageBox.critical(self, "Erreur", f"Impossible de charger les utilisateurs: {str(e)}")
    
    def load_users_table(self):
        """Charge les utilisateurs dans le tableau"""
        self.users_table.setRowCount(len(self.filtered_users))
        
        for row, user in enumerate(self.filtered_users):
            # ID
            id_item = QTableWidgetItem(str(user.id))
            id_item.setTextAlignment(Qt.AlignCenter)
            self.users_table.setItem(row, 0, id_item)
            
            # Nom d'utilisateur
            username_item = QTableWidgetItem(user.username)
            self.users_table.setItem(row, 1, username_item)
            
            # Email
            email_item = QTableWidgetItem(user.email or "")
            self.users_table.setItem(row, 2, email_item)
            
            # Rôle
            role_item = QTableWidgetItem(user.role or "USER")
            role_item.setTextAlignment(Qt.AlignCenter)
            
            # Couleur selon le rôle
            if user.role == "ADMIN":
                role_item.setForeground(QColor("#dc2626"))  # Rouge
            elif user.role == "GERANT":
                role_item.setForeground(QColor("#f59e0b"))  # Orange
            elif user.role == "CAISSIER":
                role_item.setForeground(QColor("#3b82f6"))  # Bleu
            
            self.users_table.setItem(row, 3, role_item)
            
            # Statut
            status_item = QTableWidgetItem("Actif" if user.active else "Inactif")
            status_item.setTextAlignment(Qt.AlignCenter)
            
            if user.active:
                status_item.setForeground(QColor("#10b981"))  # Vert
            else:
                status_item.setForeground(QColor("#ef4444"))  # Rouge
            
            self.users_table.setItem(row, 4, status_item)
            
            # Dernière connexion
            last_login = user.last_login.strftime("%d/%m/%Y %H:%M") if user.last_login else "Jamais"
            login_item = QTableWidgetItem(last_login)
            login_item.setTextAlignment(Qt.AlignCenter)
            self.users_table.setItem(row, 5, login_item)
            
            # Actions
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(5, 5, 5, 5)
            actions_layout.setSpacing(3)
            
            # Bouton Modifier
            edit_btn = QPushButton("✎")
            edit_btn.setToolTip("Modifier")
            edit_btn.setFixedSize(30, 30)
            edit_btn.clicked.connect(lambda _, u=user: self.edit_user(u))
            
            # Bouton Réinitialiser mot de passe
            reset_btn = QPushButton("🔑")
            reset_btn.setToolTip("Réinitialiser mot de passe")
            reset_btn.setFixedSize(30, 30)
            reset_btn.clicked.connect(lambda _, u=user: self.reset_password(u))
            
            # Bouton Activer/Désactiver
            toggle_btn = QPushButton("✓" if user.active else "✗")
            toggle_btn.setToolTip("Activer/Désactiver")
            toggle_btn.setFixedSize(30, 30)
            toggle_btn.clicked.connect(lambda _, u=user: self.toggle_user_status(u))
            
            actions_layout.addWidget(edit_btn)
            actions_layout.addWidget(reset_btn)
            actions_layout.addWidget(toggle_btn)
            actions_layout.addStretch()
            
            self.users_table.setCellWidget(row, 6, actions_widget)
    
    def filter_users(self):
        """Filtre les utilisateurs selon les critères"""
        search_text = self.search_input.text().lower()
        role_filter = self.role_filter.currentText()
        status_filter = self.status_filter.currentText()
        
        self.filtered_users = []
        
        for user in self.users:
            # Filtre recherche
            if search_text:
                if not (search_text in user.username.lower() or
                        search_text in (user.email or "").lower() or
                        search_text in (user.role or "").lower()):
                    continue
            
            # Filtre rôle
            if role_filter != "Tous les rôles":
                if user.role != role_filter:
                    continue
            
            # Filtre statut
            if status_filter == "Actif" and not user.active:
                continue
            elif status_filter == "Inactif" and user.active:
                continue
            
            self.filtered_users.append(user)
        
        self.load_users_table()
    
    def update_stats(self):
        """Met à jour les statistiques"""
        total = len(self.users)
        active = len([u for u in self.users if u.active])
        admins = len([u for u in self.users if u.role == "ADMIN"])
        
        self.total_users_label.setText(f"Total: {total}")
        self.active_users_label.setText(f"Actifs: {active}")
        self.admin_users_label.setText(f"Admins: {admins}")
    
    def show_create_user_dialog(self):
        """Affiche le dialogue de création d'utilisateur"""
        dialog = UserDialog(self, settings_manager=self.settings_manager)
        if dialog.exec():
            self.load_users()
            QMessageBox.information(self, "Succès", "Utilisateur créé avec succès!")
    
    def edit_user(self, user):
        """Modifie un utilisateur"""
        dialog = UserDialog(self, user=user, settings_manager=self.settings_manager)
        if dialog.exec():
            self.load_users()
            QMessageBox.information(self, "Succès", "Utilisateur modifié avec succès!")
    
    def reset_password(self, user):
        """Réinitialise le mot de passe d'un utilisateur"""
        reply = QMessageBox.question(
            self, "Confirmation",
            f"Voulez-vous réinitialiser le mot de passe de {user.username} ?\n\n"
            f"Le nouveau mot de passe sera: 'password'\n"
            f"L'utilisateur devra le changer à la prochaine connexion.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                from core.security import get_password_hash
                
                user.hashed_password = get_password_hash("password")
                user.must_change_password = True
                
                from core.database import SessionLocal
                db = SessionLocal()
                db.add(user)
                db.commit()
                db.close()
                
                QMessageBox.information(
                    self, "Succès",
                    f"Mot de passe réinitialisé pour {user.username}.\n"
                    f"Nouveau mot de passe: 'password'"
                )
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur: {str(e)}")
    
    def toggle_user_status(self, user):
        """Active ou désactive un utilisateur"""
        action = "désactiver" if user.active else "activer"
        reply = QMessageBox.question(
            self, "Confirmation",
            f"Voulez-vous {action} l'utilisateur {user.username} ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                user.active = not user.active
                
                from core.database import SessionLocal
                db = SessionLocal()
                db.add(user)
                db.commit()
                db.close()
                
                self.load_users()
                QMessageBox.information(
                    self, "Succès",
                    f"Utilisateur {action} avec succès!"
                )
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur: {str(e)}")
    
    def refresh(self):
        """Rafraîchit les données"""
        self.load_users()
    
    def apply_light_theme(self):
        """Applique le thème clair"""
        self.setStyleSheet("""
            #pageTitle {
                color: #111827;
                margin-bottom: 10px;
            }
            
            #filtersFrame {
                background-color: #f9fafb;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 15px;
            }
            
            #primaryButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #3b82f6, stop:1 #2563eb);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 600;
            }
            
            #primaryButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #2563eb, stop:1 #1d4ed8);
            }
            
            #usersTable {
                background-color: white;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                alternate-background-color: #f9fafb;
            }
            
            #usersTable::item {
                padding: 10px;
                border: none;
            }
            
            QHeaderView::section {
                background-color: #f3f4f6;
                padding: 12px;
                border: none;
                font-weight: bold;
                color: #374151;
            }
            
            #statsFrame {
                background-color: white;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 15px;
            }
            
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
            
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)


class UserDialog(QDialog):
    """Dialogue pour créer/modifier un utilisateur"""
    
    def __init__(self, parent=None, user=None, settings_manager=None):
        super().__init__(parent)
        
        self.user = user
        self.settings_manager = settings_manager or SettingsManager()
        self.is_edit_mode = user is not None
        
        self.setWindowTitle("Modifier utilisateur" if self.is_edit_mode else "Nouvel utilisateur")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout(self)
        
        # Formulaire
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        
        # Nom d'utilisateur
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Nom d'utilisateur")
        
        # Email
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("email@exemple.com")
        
        # Rôle
        self.role_combo = QComboBox()
        self.role_combo.addItems(["ADMIN", "GERANT", "CAISSIER", "STOCKIST", "ACCOUNTANT"])
        
        # Mot de passe (seulement pour création)
        if not self.is_edit_mode:
            self.password_input = QLineEdit()
            self.password_input.setPlaceholderText("Mot de passe")
            self.password_input.setEchoMode(QLineEdit.Password)
            
            self.confirm_password_input = QLineEdit()
            self.confirm_password_input.setPlaceholderText("Confirmer le mot de passe")
            self.confirm_password_input.setEchoMode(QLineEdit.Password)
        
        # Statut
        self.active_checkbox = QCheckBox("Actif")
        self.active_checkbox.setChecked(True)
        
        # Ajouter les champs
        form.addRow("Nom d'utilisateur*:", self.username_input)
        form.addRow("Email:", self.email_input)
        form.addRow("Rôle*:", self.role_combo)
        
        if not self.is_edit_mode:
            form.addRow("Mot de passe*:", self.password_input)
            form.addRow("Confirmation*:", self.confirm_password_input)
        
        form.addRow("Statut:", self.active_checkbox)
        
        layout.addLayout(form)
        
        # Pré-remplir si modification
        if self.is_edit_mode:
            self.username_input.setText(user.username)
            self.email_input.setText(user.email or "")
            self.role_combo.setCurrentText(user.role or "USER")
            self.active_checkbox.setChecked(user.active)
        
        # Boutons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.validate_and_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def validate_and_save(self):
        """Valide et sauvegarde l'utilisateur"""
        from core.security import get_password_hash
        from core.database import SessionLocal
        
        username = self.username_input.text().strip()
        role = self.role_combo.currentText()
        
        if not username:
            QMessageBox.warning(self, "Validation", "Le nom d'utilisateur est obligatoire!")
            return
        
        if not self.is_edit_mode:
            password = self.password_input.text()
            confirm = self.confirm_password_input.text()
            
            if not password:
                QMessageBox.warning(self, "Validation", "Le mot de passe est obligatoire!")
                return
            
            if password != confirm:
                QMessageBox.warning(self, "Validation", "Les mots de passe ne correspondent pas!")
                return
        
        try:
            db = SessionLocal()
            
            if self.is_edit_mode:
                # Modification
                user = db.query(User).get(self.user.id)
                if user:
                    user.username = username
                    user.email = self.email_input.text().strip() or None
                    user.role = role
                    user.active = self.active_checkbox.isChecked()
            else:
                # Création
                new_user = User(
                    username=username,
                    email=self.email_input.text().strip() or None,
                    role=role,
                    hashed_password=get_password_hash(self.password_input.text()),
                    active=self.active_checkbox.isChecked()
                )
                db.add(new_user)
            
            db.commit()
            db.close()
            
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la sauvegarde: {str(e)}")
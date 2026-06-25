# main_window.py
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QApplication,
    QMessageBox
)
from PySide6.QtCore import Qt
from ui.views.dashboard_view import DashboardView
from ui.views.sale_view import SaleView
from ui.views.stock_view import StockView
from ui.views.admin_view import AdminView
from ui.views.settings_view import SettingsView
from ui.views.proforma_invoice_view import EnhancedProformaInvoiceView as ProformaInvoiceView
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import QSize
from ui.views.lock_screen import LockScreen
from utils.settings_manager import SettingsManager
from ui.icons.icon_manager import IconManager
from utils.resource_path import resource_path


class MainWindow(QMainWindow):
    def __init__(self, user_data, theme=None):
        super().__init__()
        self.user_data = user_data
        self.theme = theme
        
        # Initialiser le gestionnaire de paramètres
        self.settings_manager = SettingsManager()
        
        # Écouter les changements de paramètres
        self.settings_manager.settings_changed.connect(self.on_settings_changed)
        
        # Définir les noms séparés
        self.app_name = "Gestion de stock"
        self.company_name = self.settings_manager.get_setting("company_name")
        
        # Appliquer le titre de la fenêtre
        self.setWindowTitle(f"{self.company_name} – {self.app_name}")
        # Taille minimale réduite pour supporter les petits écrans (1366×768)
        self.setMinimumSize(900, 600)

        self.menu_expanded_width = 220
        self.menu_collapsed_width = 60
        self.menu_collapsed = False

        self._build_ui()
        self._apply_role_permissions()
        self.apply_light_theme()
       
        # Appliquer le thème si fourni
        if theme:
            self.apply_external_theme()
            
        # Appliquer le logo et le nom
        self.apply_company_logo_and_name()

    def _build_ui(self):
        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)

        # ===== HEADER =====
        header = QWidget()
        header.setObjectName("Header")

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 10, 20, 10)
        header_layout.setSpacing(15)

        # Logo / Nom de l'entreprise - Conteneur pour logo + texte
        self.logo_container = QWidget()
        self.logo_container.setObjectName("LogoContainer")
        logo_container_layout = QHBoxLayout(self.logo_container)
        logo_container_layout.setContentsMargins(0, 0, 0, 0)
        logo_container_layout.setSpacing(10)
        
        # Label pour le logo (image)
        self.logo_image_label = QLabel()
        self.logo_image_label.setObjectName("LogoImage")
        self.logo_image_label.setFixedSize(40, 40)  # Taille fixe pour le logo
        
        # Label pour le nom de l'entreprise
        self.logo_text_label = QLabel(self.company_name)
        self.logo_text_label.setObjectName("LogoText")
        
        # Ajouter les deux au conteneur
        logo_container_layout.addWidget(self.logo_image_label)
        logo_container_layout.addWidget(self.logo_text_label)
        
        # Ajouter le conteneur au header
        header_layout.addWidget(self.logo_container)

        # Titre dynamique de la page
        self.page_title = QLabel("Vente")
        self.page_title.setObjectName("PageTitle")

        # Infos utilisateur
        user_info = QLabel(
            f"{self.user_data.get('username', 'Utilisateur')} · {self.user_data.get('role', 'USER').upper()}"
        )
        user_info.setObjectName("UserInfo")
        user_info.setAlignment(Qt.AlignRight | Qt.AlignVCenter)


        # Bouton déconnexion
        logout_btn = QPushButton("Vérouiller")
        logout_btn.setObjectName("LogoutButton")
        logout_btn.clicked.connect(self.lock_session)

        # Assemblage
        header_layout.addWidget(self.page_title)
        header_layout.addStretch()
        header_layout.addWidget(user_info)
        header_layout.addWidget(logout_btn)

        # ===== CORPS =====
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)

        # --- MENU LATÉRAL ---
        self.menu = QWidget()
        self.menu.setObjectName("SideMenu")
        self.menu.setFixedWidth(self.menu_expanded_width)

        menu_layout = QVBoxLayout(self.menu)
        menu_layout.setAlignment(Qt.AlignTop)
        menu_layout.setContentsMargins(8, 12, 8, 12)
        menu_layout.setSpacing(6)

        # Bouton toggle
        self.btn_toggle = QPushButton("☰")
        self.btn_toggle.setObjectName("ToggleMenu")
        self.btn_toggle.setFixedHeight(40)
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        menu_layout.addWidget(self.btn_toggle)

        # Boutons menu
        self.btn_dashboard = self._create_menu_button(
            "Dashboard", "btn_dashboard", IconManager.get_menu_icon("dashboard")
        )
        self.btn_sale = self._create_menu_button(
            "Vente", "btn_sale", IconManager.get_menu_icon("sale")
        )
        self.btn_stock = self._create_menu_button(
            "Stock", "btn_stock", IconManager.get_menu_icon("stock")
        )
        self.btn_proforma = self._create_menu_button(
            "Proformas", "btn_proforma", IconManager.get_menu_icon("receipt")
        )
        
        self.btn_admin = self._create_menu_button(
            "Admin", "btn_admin", IconManager.get_menu_icon("admin")
        )
        self.btn_settings = self._create_menu_button(
            "Paramètres", "btn_settings", IconManager.get_menu_icon("settings")
        )

        menu_layout.addWidget(self.btn_dashboard)
        menu_layout.addWidget(self.btn_sale)
        menu_layout.addWidget(self.btn_stock)
        menu_layout.addWidget(self.btn_proforma)
        menu_layout.addWidget(self.btn_admin)
        menu_layout.addWidget(self.btn_settings)
        menu_layout.addStretch()

        # --- CONTENU ---
        self.stack = QStackedWidget()
        
        # Instanciation des vues
        self.sale_view = SaleView(self.user_data)
        self.stock_view = StockView(self.user_data)
        self.proforma_view = ProformaInvoiceView(self.user_data.get('id'))
        self.admin_view = AdminView(self.user_data)
        self.dashboard_view = DashboardView(self.user_data)
        self.settings_view = SettingsView(self.user_data, self.settings_manager)
        
        
        self.stack.addWidget(self.dashboard_view)
        self.stack.addWidget(self.sale_view)
        self.stack.addWidget(self.stock_view)
        self.stack.addWidget(self.proforma_view)
   
        self.stack.addWidget(self.admin_view)
        self.stack.addWidget(self.settings_view)
        
        # Connexions menu
        self.btn_dashboard.clicked.connect(
            lambda: self._switch_view(self.dashboard_view, "Dashboard")
        )
        self.btn_sale.clicked.connect(
            lambda: self._switch_view(self.sale_view, "Vente")
        )
        self.btn_stock.clicked.connect(
            lambda: self._switch_view(self.stock_view, "Stock")
        )
        self.btn_proforma.clicked.connect(
            lambda: self._switch_view(self.proforma_view, "Factures Proforma")
        )
       
        self.btn_admin.clicked.connect(
            lambda: self._switch_view(self.admin_view, "Administration")
        )
        self.btn_settings.clicked.connect(
            lambda: self._check_and_switch_to_settings()
        )

        self.btn_toggle.clicked.connect(self._toggle_menu)

        body_layout.addWidget(self.menu)
        body_layout.addWidget(self.stack, 1)

        # ===== ASSEMBLAGE =====
        root_layout.addWidget(header)
        root_layout.addWidget(body)
        self.setCentralWidget(central)
        
    def _check_and_switch_to_settings(self):
        """Vérifie les permissions avant d'accéder aux paramètres"""
        role = self.user_data.get('role', '').upper()
        
        if role == "ADMIN":
            self._switch_view(self.settings_view, "Paramètres")
        else:
            QMessageBox.warning(
                self,
                "Accès refusé",
                "Cette section est réservée aux administrateurs.\n"
                f"Votre rôle: {role}"
            )
            # Revenir au dashboard
            self._switch_view(self.dashboard_view, "Dashboard")
    
    def _apply_role_permissions(self):
        """Applique les permissions basées sur le rôle de l'utilisateur"""
        role = self.user_data.get('role', '').upper()
        
        btn_sale = self.findChild(QPushButton, "btn_sale")
        btn_stock = self.findChild(QPushButton, "btn_stock")
        
        btn_admin = self.findChild(QPushButton, "btn_admin")
        btn_dashboard = self.findChild(QPushButton, "btn_dashboard")
        btn_settings = self.findChild(QPushButton, "btn_settings")
        
        # Cacher tous les boutons par défaut
        btn_dashboard.show()
        btn_sale.hide()
        btn_stock.hide()
        btn_admin.hide()
        btn_settings.hide()

        if role == "CAISSIER":
            btn_sale.show()
            # CAISSIER: PAS d'accès aux documents, stock, admin, paramètres
            self.stack.setCurrentWidget(self.dashboard_view)

        elif role == "GERANT":
            btn_sale.show()
            btn_stock.show()
      
            # GERANT: PAS d'accès aux paramètres
            self.stack.setCurrentWidget(self.dashboard_view)

        elif role == "ADMIN":
            btn_sale.show()
            btn_stock.show()
            btn_admin.show()
            btn_settings.show()
            self.stack.setCurrentWidget(self.dashboard_view)

        else:
            # Rôle inconnu - afficher seulement le dashboard
            self.stack.setCurrentWidget(self.dashboard_view)
    
    def _switch_view(self, view, title):
        """Change la vue actuelle"""
        self.stack.setCurrentWidget(view)
        self.page_title.setText(title)
        # Rafraîchir la vue quand on y accède
        if hasattr(view, 'refresh'):
            view.refresh()
        # 🆕 Rafraîchir spécifiquement la vue documents
        if hasattr(view, 'load_all_documents'):
            view.load_all_documents()
            
    def lock_session(self):
        dialog = LockScreen(
            username=self.user_data.get("username", ""),
            parent=self
        )
        result = dialog.exec()
        if result:
            print("Session déverrouillée")
            
    def _toggle_menu(self):
        """Affiche/masque le menu latéral"""
        self.menu_collapsed = not self.menu_collapsed

        if self.menu_collapsed:
            self.menu.setFixedWidth(self.menu_collapsed_width)
            for btn in self.menu.findChildren(QPushButton):
                if btn.property("fullText"):
                    btn.setText("")
                    btn.setToolTip(btn.property("fullText"))
        else:
            self.menu.setFixedWidth(self.menu_expanded_width)
            for btn in self.menu.findChildren(QPushButton):
                if btn.property("fullText"):
                    btn.setText(btn.property("fullText"))
                    btn.setToolTip("")

    def _create_menu_button(self, text, object_name, icon_path=None):
        """Crée un bouton de menu avec icône"""
        btn = QPushButton(text)
        btn.setObjectName(object_name)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(44)
        btn.setIconSize(QSize(22, 22))
        btn.setProperty("fullText", text)

        if icon_path:
            btn.setIcon(QIcon(icon_path))

        return btn
    
    def on_settings_changed(self, new_settings):
        """Méthode appelée quand les paramètres changent"""
        # Mettre à jour le nom de l'entreprise
        if "company_name" in new_settings:
            self.update_company_name(new_settings["company_name"])
        
        # Mettre à jour le logo si nécessaire
        if "company_logo" in new_settings:
            self.apply_company_logo_and_name()
        
        # Rafraîchir toutes les vues
        self.refresh_all_views()
        
    def refresh_all_views(self):
        """Rafraîchit toutes les vues pour appliquer les nouveaux paramètres"""
        if hasattr(self.dashboard_view, 'refresh'):
            self.dashboard_view.refresh()
        if hasattr(self.sale_view, 'refresh'):
            self.sale_view.refresh()
        if hasattr(self.stock_view, 'refresh'):
            self.stock_view.refresh()
        
        if hasattr(self.admin_view, 'refresh'):
            self.admin_view.refresh()
    
    def apply_external_theme(self):
        """Appliquer un thème externe depuis theme_manager"""
        try:
            from ui.themes.theme_manager import load_theme
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app and self.theme:
                load_theme(app, self.theme)
        except ImportError:
            print("theme_manager non disponible, utilisation du thème par défaut")
        except Exception as e:
            print(f"Erreur lors du chargement du thème: {e}")
    
    def apply_light_theme(self):
        """Applique le thème light."""
        theme_file = resource_path("ui/themes/main.qss")

        try:
            with open(theme_file, 'r', encoding='utf-8') as f:
                self.setStyleSheet(f.read())
                return
        except FileNotFoundError:
            print(f"Thème main.qss non trouvé : {theme_file}")
        except Exception as e:
            print(f"Erreur lors du chargement du thème : {e}")

        self.setStyleSheet("")
        self.setStyleSheet("")
    
    def apply_company_logo_and_name(self):
        """Applique le logo ET le nom de l'entreprise"""
        logo_path = self.settings_manager.get_logo_path()
        
        # Toujours afficher le nom de l'entreprise
        self.logo_text_label.setText(self.company_name)
        
        if logo_path:
            try:
                pixmap = QPixmap(logo_path)
                if not pixmap.isNull():
                    # Redimensionner l'image pour s'adapter au label
                    scaled_pixmap = pixmap.scaled(
                        self.logo_image_label.width(),
                        self.logo_image_label.height(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    
                    # Centrer le pixmap dans le label
                    self.logo_image_label.setAlignment(Qt.AlignCenter)
                    self.logo_image_label.setPixmap(scaled_pixmap)
                    
                    # Afficher le label d'image
                    self.logo_image_label.show()
                    
                    print(f"✓ Logo chargé: {logo_path}")
                    return
            except Exception as e:
                print(f"Erreur lors du chargement du logo: {e}")
        
        # Si pas de logo ou erreur, cacher le label d'image
        self.logo_image_label.clear()
        self.logo_image_label.hide()
        print("ℹ Affichage du nom de l'entreprise sans logo")
    
    def update_company_name(self, company_name):
        """Met à jour le nom de l'entreprise dans le header et le titre"""
        self.company_name = company_name
        self.logo_text_label.setText(company_name)
        self.setWindowTitle(f"{company_name} – {self.app_name}")
        
        # Rafraîchir l'affichage du logo (au cas où le chemin a changé)
        self.apply_company_logo_and_name()

    def logout(self):
        """Retour à la page de connexion"""
        from ui.views.login_view import LoginView

        # Créer et afficher la fenêtre de connexion
        self.login_view = LoginView()
        self.login_view.show()

        # Cacher la fenêtre actuelle
        self.close()
        
    def get_user_info(self):
        """Retourne les informations utilisateur"""
        return {
            'username': self.user_data.get('username', ''),
            'role': self.user_data.get('role', ''),
            'email': self.user_data.get('email', ''),
            'id': self.user_data.get('id')
        }
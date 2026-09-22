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
from ui.views.invoice_register_view import InvoiceRegisterView
from ui.views.stock_view import StockView
from ui.views.admin_view import AdminView
from ui.views.settings_view import SettingsView
from ui.views.treasury_view import TreasuryView
from ui.views.proforma_invoice_view import EnhancedProformaInvoiceView
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import QSize
from ui.views.lock_screen import LockScreen
from utils.settings_manager import SettingsManager
from ui.icons.icon_manager import IconManager
from utils.resource_path import resource_path
from core.permissions import (
    can,
    is_known_role,
    normalize_role,
    role_display_name,
)

import logging

logger = logging.getLogger("korgo_pro")

# Association bouton de menu <-> permission (source unique : core.permissions).
# (attribut du bouton, permission, attribut de la vue, titre affiché)
MENU_ENTRIES = (
    ("btn_dashboard", "view_dashboard", "dashboard_view", "Tableau de bord"),
    ("btn_sale", "create_sales", "sale_view", "Vente"),
    ("btn_register", "view_invoice_register", "register_view",
     "Registre des factures clients"),
    ("btn_proforma", "manage_proformas", "proforma_view", "Factures Pro Forma"),
    ("btn_stock", "view_stock", "stock_view", "Stock"),
    ("btn_treasury", "view_treasury", "treasury_view", "Trésorerie"),
    ("btn_admin", "access_admin", "admin_view", "Administration"),
    ("btn_settings", "manage_settings", "settings_view", "Paramètres"),
)


class MainWindow(QMainWindow):
    def __init__(self, user_data, theme=None):
        super().__init__()
        self.user_data = user_data
        self.theme = theme
        
        # Initialiser le gestionnaire de paramètres
        self.settings_manager = SettingsManager()

        # Définir les noms séparés
        self.app_name = "Gestion de stock"
        self.company_name = self.settings_manager.get_setting("company_name")

        # Appliquer le titre de la fenêtre
        self.setWindowTitle(f"{self.company_name} – {self.app_name}")
        # Taille minimale adaptée aux petits écrans (1024×768 minimum)
        self.setMinimumSize(800, 500)

        self.menu_expanded_width = 220
        self.menu_collapsed_width = 60
        self.menu_collapsed = False

        try:
            self._build_ui()
        except Exception:
            # Ne pas laisser une fenêtre partiellement construite connectée
            # au signal global (sinon elle plante à chaque settings_changed
            # et pollue l'application) : déconnexion puis re-propagation.
            try:
                self.settings_manager.settings_changed.disconnect(
                    self.on_settings_changed)
            except (RuntimeError, TypeError):
                pass
            raise
        self.settings_manager.settings_changed.connect(self.on_settings_changed)
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
        header_layout.setContentsMargins(10, 8, 10, 8)
        header_layout.setSpacing(10)

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
        self.header_user_info = QLabel(
            f"{self.user_data.get('username', 'Utilisateur')} · {self.user_data.get('role', 'USER').upper()}"
        )
        self.header_user_info.setObjectName("UserInfo")
        self.header_user_info.setAlignment(Qt.AlignRight | Qt.AlignVCenter)


        # Bouton déconnexion
        logout_btn = QPushButton("Vérouiller")
        logout_btn.setObjectName("LogoutButton")
        logout_btn.clicked.connect(self.lock_session)

        # Assemblage
        header_layout.addWidget(self.page_title)
        header_layout.addStretch()
        header_layout.addWidget(self.header_user_info)
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
        self.btn_toggle.setFixedHeight(36)
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        menu_layout.addWidget(self.btn_toggle)

        # Boutons menu
        self.btn_dashboard = self._create_menu_button(
            "Dashboard", "btn_dashboard", IconManager.get_menu_icon("dashboard")
        )
        self.btn_sale = self._create_menu_button(
            "Vente", "btn_sale", IconManager.get_menu_icon("sale")
        )
        self.btn_proforma = self._create_menu_button(
            "Document", "btn_proforma", IconManager.get_menu_icon("document")
        )
        self.btn_stock = self._create_menu_button(
            "Stock", "btn_stock", IconManager.get_menu_icon("stock")
        )
        self.btn_register = self._create_menu_button(
            "Registre factures", "btn_register", IconManager.get_menu_icon("receipt")
        )
        self.btn_treasury = self._create_menu_button(
            "Trésorerie", "btn_treasury", IconManager.get_menu_icon("treasury")
        )
        self.btn_admin = self._create_menu_button(
            "Admin", "btn_admin", IconManager.get_menu_icon("admin")
        )
        self.btn_settings = self._create_menu_button(
            "Paramètres", "btn_settings", IconManager.get_menu_icon("settings")
        )

        menu_layout.addWidget(self.btn_dashboard)
        menu_layout.addWidget(self.btn_sale)
        menu_layout.addWidget(self.btn_register)
        menu_layout.addWidget(self.btn_proforma)
        menu_layout.addWidget(self.btn_stock)
        menu_layout.addWidget(self.btn_treasury)
        menu_layout.addWidget(self.btn_admin)
        menu_layout.addWidget(self.btn_settings)
        menu_layout.addStretch()

        # --- CONTENU ---
        self.stack = QStackedWidget()
        
        # Instanciation des vues : seules les vues autoris?es par le r?le sont
        # construites, ? partir de la source unique ``core.permissions``
        # (voir MENU_ENTRIES). Une vue interdite n'est donc jamais instanci?e,
        # ce qui ?vite tout message d'erreur pendant la construction de la
        # fen?tre principale et tout ?cran ? moiti? initialis?.
        role = normalize_role(self.user_data.get("role"))
        factories = {
            "dashboard_view": lambda: DashboardView(self.user_data),
            "sale_view": lambda: SaleView(self.user_data),
            "register_view": lambda: InvoiceRegisterView(self.user_data),
            "proforma_view": lambda: EnhancedProformaInvoiceView(
                current_user_id=self.user_data.get('id')),
            "stock_view": lambda: StockView(self.user_data),
            "treasury_view": lambda: TreasuryView(self.user_data),
            "admin_view": lambda: AdminView(self.user_data),
            "settings_view": lambda: SettingsView(
                self.user_data, self.settings_manager),
        }

        self.views = {}
        for attr, permission, view_attr, title in MENU_ENTRIES:
            button = getattr(self, attr)
            # Le tableau de bord est l'?cran d'accueil : toujours disponible.
            if not (view_attr == "dashboard_view" or can(role, permission)):
                continue

            view = factories[view_attr]()
            setattr(self, view_attr, view)
            self.views[view_attr] = view
            self.stack.addWidget(view)

            if view_attr == "settings_view":
                button.clicked.connect(self._check_and_switch_to_settings)
            else:
                button.clicked.connect(
                    lambda _checked=False, v=view, t=title: self._switch_view(v, t)
                )

        self.btn_toggle.clicked.connect(self._toggle_menu)

        body_layout.addWidget(self.menu)
        body_layout.addWidget(self.stack, 1)

        # ===== ASSEMBLAGE =====
        root_layout.addWidget(header)
        root_layout.addWidget(body)
        self.setCentralWidget(central)
        
    def _check_and_switch_to_settings(self):
        """Vérifie les permissions avant d'accéder aux paramètres."""
        role = normalize_role(self.user_data.get("role"))
        settings_view = self.views.get("settings_view")

        if settings_view is not None and can(role, "manage_settings"):
            self._switch_view(settings_view, "Paramètres")
        else:
            QMessageBox.warning(
                self,
                "Accès refusé",
                "Cette section est réservée aux administrateurs.\n"
                f"Votre rôle : {role_display_name(role) or role}"
            )
            # Revenir au dashboard
            self._switch_view(self.views["dashboard_view"], "Dashboard")

    def _apply_role_permissions(self):
        """Applique les permissions de navigation du rôle connecté.

        Source unique : ``core.permissions`` (voir ``MENU_ENTRIES``). Un bouton
        de menu n'est visible que si le rôle possède la permission associée :
        le menu et la matrice de référence ne peuvent plus diverger.
        """
        role = normalize_role(self.user_data.get("role"))

        if not is_known_role(role):
            logger.warning(
                "Rôle '%s' non reconnu : navigation réduite au tableau de bord "
                "(voir core/permissions.py).", self.user_data.get("role"))

        for attr, permission, _view_attr, _title in MENU_ENTRIES:
            button = getattr(self, attr, None)
            if button is None:
                button = self.findChild(QPushButton, attr)
            if button is None:
                continue
            button.setVisible(can(role, permission))

        # Le tableau de bord est la vue d'accueil de tous les rôles (la
        # permission ``view_dashboard`` leur est accordée sans exception).
        self.stack.setCurrentWidget(self.views["dashboard_view"])

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
            
    def resizeEvent(self, event):
        """Adapte le menu et le header à la largeur de la fenêtre"""
        super().resizeEvent(event)
        width = self.width()
        
        # Ajuster la largeur du menu proportionnellement
        if not self.menu_collapsed:
            menu_w = min(self.menu_expanded_width, max(140, width // 5))
            self.menu.setFixedWidth(menu_w)
        
        # Masquer/afficher les infos utilisateur dans le header si trop étroit
        if hasattr(self, 'header_user_info'):
            self.header_user_info.setVisible(width > 900)
    
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
        btn.setFixedHeight(38)
        btn.setIconSize(QSize(20, 20))
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
        """Rafraîchit toutes les vues pour appliquer les nouveaux paramètres.

        Protection anti-gel : chaque vue est rafraîchie indépendamment
        (getattr + try/except) afin qu'un échec sur l'une ne bloque ni ne
        plante les autres, et qu'une vue absente (fenêtre partiellement
        construite) ne lève jamais d'AttributeError.
        """
        for attr in ("dashboard_view", "sale_view", "stock_view", "admin_view"):
            view = getattr(self, attr, None)
            if view is None:
                continue
            try:
                if hasattr(view, 'refresh'):
                    view.refresh()
            except Exception as e:
                print(f"[WARN] Rafraîchissement de {attr} échoué : {e}")
    
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
                    
                    print(f"[OK] Logo charge: {logo_path}")
                    return
            except Exception as e:
                print(f"Erreur lors du chargement du logo: {e}")
        
        # Si pas de logo ou erreur, cacher le label d'image
        self.logo_image_label.clear()
        self.logo_image_label.hide()
        print("[INFO] Affichage du nom de l'entreprise sans logo")
    
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
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QHeaderView, QMessageBox, QDialog,
    QLabel, QFrame, QComboBox, QGroupBox, QCheckBox, QDateEdit,
    QFormLayout, QTabWidget, QScrollArea, QGridLayout, QToolButton, QStyle,
    QTextEdit, QFileDialog, QSplitter, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QDate, QDateTime, QThread, QTimer, QEvent
from PySide6.QtGui import QIcon, QFont, QColor, QPixmap, QIntValidator, QDoubleValidator
import hashlib
import random
import string
from datetime import datetime
import json
from core.models.user import User
from core.database import SessionLocal, engine
from datetime import datetime, timedelta
from core.log_manager import LogManager
from core.database_manager import DatabaseManager
from core.sale_log_manager import SaleLogManager
from ui.views.sys_logs_dialog import SysLogsDialog
from ui.loading import LoadingOverlay
from utils.settings_manager import SettingsManager
# Source unique des rôles et permissions (partagée avec le frontend web).
from core.permissions import (
    available_roles,
    describe_roles,
    normalize_role,
    permission_label,
    permission_labels,
    role_description,
    role_display_name,
)
import os

class DiscordBackupWorker(QThread):
    """Thread d'envoi du backup base de données sur un webhook Discord (pas de gel de l'UI)."""

    finished = Signal(dict)

    def __init__(self, db_manager, webhook_url, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.webhook_url = webhook_url

    def run(self):
        result = self.db_manager.backup_to_discord(self.webhook_url)
        self.finished.emit(result)


class DbInfoWorker(QThread):
    """Thread de collecte des informations base de données.

    Sur PostgreSQL/Supabase, get_database_info() fait plusieurs allers-retours
    réseau ; l'exécuter dans le thread UI gelait l'interface (« Ne répond pas »).
    """

    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager

    def run(self):
        try:
            self.finished.emit(self.db_manager.get_database_info())
        except Exception as e:
            self.failed.emit(str(e))


class ActivitiesWorker(QThread):
    """Journal système : requêtes hors du thread UI.

    get_logs() + get_statistics() coûtent 2 allers-retours réseau (~300 ms à
    147 ms de RTT) et étaient exécutés à l'ouverture de l'onglet, au clic sur
    « Filtrer » et à chaque page — dans le thread UI.
    """

    loaded = Signal(dict)
    failed = Signal(str)

    def __init__(self, log_manager, filters, limit, offset, parent=None):
        super().__init__(parent)
        self.log_manager = log_manager
        self.filters = filters
        self.limit = limit
        self.offset = offset

    def run(self):
        try:
            result = self.log_manager.get_logs(
                filters=self.filters if self.filters else None,
                limit=self.limit,
                offset=self.offset,
            )
            stats = self.log_manager.get_statistics()
            self.loaded.emit({"result": result, "stats": stats})
        except Exception as e:  # noqa: BLE001 - signal d'échec dédié
            self.failed.emit(str(e))


class SaleLogsWorker(QThread):
    """Journal des ventes : requêtes hors du thread UI (même principe)."""

    loaded = Signal(dict)
    failed = Signal(str)

    def __init__(self, sale_log_manager, filters, limit, offset, parent=None):
        super().__init__(parent)
        self.sale_log_manager = sale_log_manager
        self.filters = filters
        self.limit = limit
        self.offset = offset

    def run(self):
        try:
            result = self.sale_log_manager.get_sale_logs(
                **self.filters, limit=self.limit, offset=self.offset)
            stats = self.sale_log_manager.get_sale_statistics()
            self.loaded.emit({"result": result, "stats": stats})
        except Exception as e:  # noqa: BLE001 - signal d'échec dédié
            self.failed.emit(str(e))


class AdminView(QWidget):
    """Vue d'administration des utilisateurs"""
    
    # Signaux
    user_created = Signal(dict)
    user_updated = Signal(dict)
    user_deleted = Signal(int)
    password_reset = Signal(dict)
    role_changed = Signal(dict)
    
    def __init__(self, current_user):
        super().__init__()
        self.setWindowTitle("Korgo - Administration")
        self.setMinimumSize(800, 500)  # Taille minimale, s'adapte à l'écran
        self.current_user = current_user
        self.db_session = SessionLocal()
        self.style = self.style()
        self.apply_light_theme()
        
        # Initialiser les gestionnaires
        self.log_manager = LogManager()
        self.db_manager = DatabaseManager()
        self.sale_log_manager = SaleLogManager()
        self.settings_manager = SettingsManager()
        
        # Rôles et permissions : source unique core.permissions (le web s'y
        # adosse également). Ne pas redéfinir de matrice ici.
        self.roles_dict = describe_roles()

        # Rôles proposés à la création d'un utilisateur
        self.available_roles = available_roles()

        # Permissions disponibles : (libellé, clé, description)
        self.permissions_list = permission_labels()

        # Responsivité de l'onglet « Rôles & Permissions » : le nombre de
        # colonnes de rôles est recalculé selon la largeur réellement offerte
        # (voir _adapt_roles_tab). Le timer évite un recalcul par pixel.
        self.roles_scroll = None
        self._roles_grid = None
        self._role_groups = []
        self._roles_columns = 0
        self._roles_resize_timer = QTimer(self)
        self._roles_resize_timer.setSingleShot(True)
        self._roles_resize_timer.setInterval(120)
        self._roles_resize_timer.timeout.connect(self._adapt_roles_tab)

        # Charger les utilisateurs depuis la base de données
        self.users = []
        self.filtered_users = []
        self.load_users_from_db()
        
        # Pagination pour les logs
        self.current_logs_page = 0
        self.logs_per_page = 50
        self.current_sale_logs_page = 0
        self.sale_logs_per_page = 50

        # Workers de chargement (anti-gel) : les requêtes réseau partent en
        # arrière-plan ; le thread UI ne fait que le rendu des résultats.
        self._activities_worker = None
        self._activities_pending = False
        self._sale_logs_worker = None
        self._sale_logs_pending = False

        self.init_ui()
        
    def load_users_from_db(self):
        """Charger les utilisateurs depuis la base de données"""
        try:
            self.users = self.db_session.query(User).order_by(User.created_at.desc()).all()
            self.filtered_users = self.users.copy()
        except Exception as e:
            print(f"Erreur lors du chargement des utilisateurs: {e}")
            self.users = []
            self.filtered_users = []
        
    def init_ui(self):
        """Initialisation de l'interface utilisateur"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Création d'onglets
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("tabWidget")
        
        # Onglet 1: Liste des utilisateurs
        self.users_tab = QWidget()
        self.setup_users_tab()
        self.tab_widget.addTab(self.users_tab, "Utilisateurs")
        
        # Onglet 2: Rôles et permissions
        self.roles_tab = QWidget()
        self.setup_roles_tab()
        self.tab_widget.addTab(self.roles_tab, "Rôles & Permissions")
        
        # Onglet 3: Journal d'activité (version réelle)
        self.activity_tab = QWidget()
        self.setup_activity_tab()
        self.tab_widget.addTab(self.activity_tab, "Journal Système")
        
        # Onglet 4: Journal des ventes (NOUVEAU)
        self.sale_logs_tab = QWidget()
        self.setup_sale_logs_tab()
        self.tab_widget.addTab(self.sale_logs_tab, "Journal Ventes")
        
        # Onglet 5: Base de données
        self.db_tab = QWidget()
        self.setup_database_tab()
        self.tab_widget.addTab(self.db_tab, "Base de données")
        
        main_layout.addWidget(self.tab_widget)
        
        # Charger les données
        self.load_users()
        self.update_role_stats()
        
        # Journaliser l'ouverture de l'admin
        self.log_activity(
            user_id=self.get_current_user_id(),
            username=self.get_current_username(),
            action="Accès administration",
            details="Ouverture du panneau d'administration"
        )
    
    # ==================== CONTENU DÉFILANT DES ONGLETS ====================
    def _add_scrollable_content(self, tab, content_name):
        """Placer le contenu d'un onglet d'administration dans une zone défilante.

        POURQUOI
        Les écrans d'administration (tableau de 9 colonnes, barres de filtres)
        cumulent une largeur minimale de 1200 à 2000 px. Sans zone défilante,
        ce minimum remonte jusqu'à la fenêtre principale : sur un écran de
        1366 px elle ne peut plus rétrécir et la partie droite devient
        inaccessible — l'onglet « Rôles & Permissions » apparaît rogné, sans
        aucune barre de défilement pour atteindre les colonnes hors champ.

        La politique ``Ignored`` empêche ce minimum de remonter : le contenu
        reste atteignable par les barres de défilement, quelle que soit la
        taille de la fenêtre.

        Retourne ``(layout_du_contenu, zone_defilante, layout_de_l_onglet)`` :
        le contenu défilant (tableaux, filtres) va dans le premier, seuls les
        éléments qui doivent rester visibles (barres d'action) vont dans le
        troisième.
        """
        scroll = QScrollArea(tab)
        scroll.setObjectName(f"{content_name}Scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("border: none; background-color: transparent;")
        scroll.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        
        content = QWidget()
        content.setObjectName(content_name)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll.setWidget(content)
        
        outer_layout = QVBoxLayout(tab)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)
        
        return content_layout, scroll, outer_layout
    
    # ==================== ONGLET UTILISATEURS ====================
    def setup_users_tab(self):
        """Configurer l'onglet des utilisateurs"""
        layout, _users_scroll, _users_outer = self._add_scrollable_content(
            self.users_tab, "usersTabContent"
        )
        
        # Barre d'outils
        toolbar = QFrame()
        toolbar.setObjectName("toolbarFrame")
        toolbar_layout = QHBoxLayout(toolbar)
        
        # Recherche
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Rechercher un utilisateur...")
        self.search_input.setObjectName("searchInput")
        self.search_input.textChanged.connect(self.filter_users)
        
        search_icon = QLabel()
        search_icon.setPixmap(self.style.standardIcon(QStyle.SP_FileDialogContentsView).pixmap(16, 16))
        
        # Filtres
        self.role_filter = QComboBox()
        self.role_filter.addItem("Tous les rôles")
        for role_key, role_data in self.roles_dict.items():
            self.role_filter.addItem(role_data["name"])
        self.role_filter.currentTextChanged.connect(self.filter_users)
        
        self.status_filter = QComboBox()
        self.status_filter.addItem("Tous les statuts")
        self.status_filter.addItems(["Actif", "Inactif"])
        self.status_filter.currentTextChanged.connect(self.filter_users)
        
        # Boutons d'action
        self.add_user_btn = QPushButton("Créer un utilisateur")
        self.add_user_btn.setIcon(self.style.standardIcon(QStyle.SP_FileDialogNewFolder))
        self.add_user_btn.setObjectName("addButton")
        self.add_user_btn.clicked.connect(self.show_create_user_dialog)
        
        self.export_btn = QPushButton("Exporter")
        self.export_btn.setIcon(self.style.standardIcon(QStyle.SP_DialogSaveButton))
        self.export_btn.setObjectName("exportButton")
        self.export_btn.clicked.connect(self.export_users)
        
        self.refresh_btn = QPushButton("Actualiser")
        self.refresh_btn.setIcon(self.style.standardIcon(QStyle.SP_BrowserReload))
        self.refresh_btn.setObjectName("refreshButton")
        self.refresh_btn.clicked.connect(self.refresh_data)
        
        toolbar_layout.addWidget(search_icon)
        toolbar_layout.addWidget(self.search_input, 2)
        toolbar_layout.addWidget(QLabel("Rôle:"))
        toolbar_layout.addWidget(self.role_filter)
        toolbar_layout.addWidget(QLabel("Statut:"))
        toolbar_layout.addWidget(self.status_filter)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.export_btn)
        toolbar_layout.addWidget(self.refresh_btn)
        toolbar_layout.addWidget(self.add_user_btn)
        
        layout.addWidget(toolbar)
        
        # Tableau des utilisateurs
        self.users_table = QTableWidget()
        self.users_table.setObjectName("usersTable")
        self.users_table.setColumnCount(9)
        self.users_table.setHorizontalHeaderLabels([
            "ID", "Nom d'utilisateur", "Email", "Rôle", "Statut", 
            "Date création", "Dernière connexion", "Permissions", "Actions"
        ])
        
        # Configuration du tableau
        header = self.users_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        self.users_table.setColumnWidth(0, 60)
        self.users_table.setColumnWidth(1, 150)
        self.users_table.setColumnWidth(2, 200)
        self.users_table.setColumnWidth(3, 120)
        self.users_table.setColumnWidth(4, 100)
        self.users_table.setColumnWidth(5, 120)
        self.users_table.setColumnWidth(6, 140)
        self.users_table.setColumnWidth(7, 180)
        self.users_table.setColumnWidth(8, 280)
        
        self.users_table.verticalHeader().setVisible(False)
        self.users_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.users_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        layout.addWidget(self.users_table)
        
        # Panel de statistiques
        stats_frame = QFrame()
        stats_frame.setObjectName("statsFrame")
        stats_layout = QHBoxLayout(stats_frame)
        
        self.total_users_label = QLabel("Total: 0")
        self.active_users_label = QLabel("Actifs: 0")
        self.inactive_users_label = QLabel("Inactifs: 0")
        self.admins_label = QLabel("Administrateurs: 0")
        self.gerants_label = QLabel("Gérants: 0")
        self.cashiers_label = QLabel("Caissiers: 0")
        
        for label in [self.total_users_label, self.active_users_label, 
                     self.inactive_users_label, self.admins_label,
                     self.gerants_label, self.cashiers_label]:
            label.setObjectName("statItem")
            stats_layout.addWidget(label)
        
        stats_layout.addStretch()
        
        layout.addWidget(stats_frame)
    
    # ==================== ONGLET RÔLES ET PERMISSIONS ====================
    #: Largeur minimale d'un groupe de rôle : en dessous, le repliement en
    #: moins de colonnes (puis la zone défilante) prend le relais plutôt que de
    #: rogner les libellés des cases à cocher.
    ROLE_GROUP_MIN_WIDTH = 250

    #: Réservation forfaitaire (marges de l'onglet + barre de défilement) pour
    #: éviter qu'une barre de défilement qui apparaît ne retire une colonne,
    #: ne disparaisse, etc. (oscillation entre N et N-1 colonnes).
    ROLES_TAB_RESERVE = 40

    def setup_roles_tab(self):
        """Configurer l'onglet des rôles et permissions.

        Le contenu (un groupe de cases à cocher par rôle) vit dans une zone
        défilante et son nombre de colonnes s'adapte à la largeur disponible
        (``_adapt_roles_tab``) : rien n'est rogné sur un écran étroit. Les
        boutons d'action restent hors de la zone défilante afin d'être
        joignables quelle que soit la taille de la fenêtre.
        """
        container_layout, self.roles_scroll, layout = self._add_scrollable_content(
            self.roles_tab, "rolesTabContent"
        )
        
        # La largeur réellement disponible n'est connue qu'à l'affichage de
        # l'onglet : on se recale sur chaque redimensionnement du viewport.
        self.roles_scroll.viewport().installEventFilter(self)
        
        # Description
        desc_label = QLabel("Définir les permissions pour chaque rôle d'utilisateur")
        desc_label.setObjectName("descriptionLabel")
        desc_label.setWordWrap(True)
        container_layout.addWidget(desc_label)
        
        # Grid pour les rôles : colonnes recalculées dans _adapt_roles_tab
        self._roles_grid = QGridLayout()
        self._roles_grid.setSpacing(16)
        self._roles_grid.setContentsMargins(0, 0, 0, 0)
        container_layout.addLayout(self._roles_grid)
        container_layout.addStretch()
        
        self._build_role_groups()
        
        # Bouton de sauvegarde
        save_perms_btn = QPushButton("Enregistrer les permissions")
        save_perms_btn.setIcon(self.style.standardIcon(QStyle.SP_DialogSaveButton))
        save_perms_btn.setObjectName("saveButton")
        save_perms_btn.clicked.connect(self.save_permissions)
        
        # Bouton de réinitialisation
        reset_perms_btn = QPushButton("Réinitialiser aux valeurs par défaut")
        reset_perms_btn.setIcon(self.style.standardIcon(QStyle.SP_BrowserReload))
        reset_perms_btn.setObjectName("resetButton")
        reset_perms_btn.clicked.connect(self.reset_permissions_to_default)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(reset_perms_btn)
        button_layout.addWidget(save_perms_btn)
        
        layout.addLayout(button_layout)
        
        # Première disposition (ré-évaluée à chaque redimensionnement)
        self._adapt_roles_tab()
    
    def _build_role_groups(self):
        """Créer un groupe de cases à cocher par rôle (sans le positionner).
        
        Séparé de :meth:`setup_roles_tab` pour pouvoir reconstruire le contenu
        après une réinitialisation sans réinstaller un ``QLayout`` sur l'onglet :
        Qt refuse la seconde installation et l'écran restait alors figé sur
        l'état précédent.
        """
        self._role_groups = []
        
        # Rôles à configurer
        for role_key, role_data in self.roles_dict.items():
            # Groupe pour chaque rôle
            role_group = QGroupBox(role_data["name"])
            role_group.setObjectName("roleGroup")
            role_group.setMinimumWidth(self.ROLE_GROUP_MIN_WIDTH)
            role_layout = QVBoxLayout(role_group)
            
            # Description du rôle (multi-lignes : le groupe ne s'élargit plus
            # pour tenir la description sur une seule ligne)
            role_desc_label = QLabel(role_data["description"])
            role_desc_label.setObjectName("roleDesc")
            role_desc_label.setWordWrap(True)
            role_layout.addWidget(role_desc_label)
            
            # Permissions
            for perm_name, perm_key, perm_desc in self.permissions_list:
                chk = QCheckBox(perm_name)
                chk.setObjectName(f"perm_{role_key}_{perm_key}")
                chk.setChecked(role_data["permissions"].get(perm_key, False))
                chk.setToolTip(perm_desc)
                
                # Désactiver pour admin (tout coché)
                if role_key == "ADMIN":
                    chk.setEnabled(False)
                else:
                    chk.stateChanged.connect(
                        lambda state, rk=role_key, pk=perm_key: 
                        self.update_permission_in_dict(rk, pk, bool(state))
                    )
                
                role_layout.addWidget(chk)
            
            role_layout.addStretch()
            self._role_groups.append(role_group)
    
    def _adapt_roles_tab(self):
        """Répartir les groupes de rôles selon la largeur réellement offerte.
        
        Nombre de colonnes = largeur utile // largeur minimale d'une colonne,
        borné entre 1 et le nombre de rôles. Le même écran s'affiche donc en
        5 colonnes sur un grand moniteur comme en 2 ou 1 colonne sur un écran
        étroit, sans jamais rogner une case à cocher (la zone défilante prenant
        le relais si nécessaire).
        """
        if self._roles_grid is None or not self._role_groups:
            return
        
        # Référence : la largeur de l'onglet, et non celle du viewport. Cette
        # dernière varie avec la barre de défilement : s'y référer ferait
        # osciller le nombre de colonnes (barre qui apparaît -> une colonne en
        # moins -> barre qui disparaît -> ...).
        width = self.roles_tab.width()
        if width <= 0:
            width = self.width()
        if width <= 0:
            return
        
        # Largeur réellement nécessaire à une colonne : les libellés des cases
        # à cocher varient avec la police et le DPI de l'écran.
        column_width = self.ROLE_GROUP_MIN_WIDTH
        for group in self._role_groups:
            column_width = max(column_width, group.minimumSizeHint().width())
        
        spacing = self._roles_grid.spacing()
        usable = width - self.ROLES_TAB_RESERVE + spacing
        columns = max(1, min(len(self._role_groups),
                             int(usable // (column_width + spacing))))
        
        if columns == self._roles_columns:
            return
        self._roles_columns = columns
        
        # Retirer les groupes du grid sans les détruire : ils sont replacés
        # juste après avec le nouveau nombre de colonnes.
        while self._roles_grid.count():
            self._roles_grid.takeAt(0)
        
        for index, group in enumerate(self._role_groups):
            self._roles_grid.addWidget(group, index // columns, index % columns)
    
    def _rebuild_role_groups(self):
        """Reconstruire les cases à cocher de l'onglet depuis ``roles_dict``.
        
        Remplace l'ancien rappel de :meth:`setup_roles_tab` (qui tentait
        d'installer un second ``QVBoxLayout`` sur l'onglet) : seuls les groupes
        de rôles sont recréés, le reste de l'onglet est conservé.
        """
        if self._roles_grid is None:
            return
        
        while self._roles_grid.count():
            item = self._roles_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        
        self._role_groups = []
        self._roles_columns = 0
        self._build_role_groups()
        self._adapt_roles_tab()
    
    def resizeEvent(self, event):
        """Ré-agencer les colonnes de rôles (un seul recalcul par rafale)."""
        super().resizeEvent(event)
        self._schedule_roles_adapt()
    
    def eventFilter(self, obj, event):
        """Recaler les colonnes dès que la zone défilante change de largeur.
        
        L'onglet « Rôles & Permissions » n'est pas l'onglet courant au
        démarrage : sa largeur réelle n'est connue qu'à son affichage (et à
        chaque redimensionnement), d'où le suivi du viewport.
        """
        if (getattr(self, "roles_scroll", None) is not None
                and obj is self.roles_scroll.viewport()
                and event.type() == QEvent.Resize):
            self._schedule_roles_adapt()
        return super().eventFilter(obj, event)
    
    def _schedule_roles_adapt(self):
        """Programmer le recalcul des colonnes de rôles (anti-rafale)."""
        timer = getattr(self, "_roles_resize_timer", None)
        if timer is None:
            return
        
        if timer.isActive():
            timer.stop()
        timer.start()
    
    def update_permission_in_dict(self, role_key, permission_key, enabled):
        """Mettre à jour une permission dans le dictionnaire"""
        if role_key in self.roles_dict and "permissions" in self.roles_dict[role_key]:
            self.roles_dict[role_key]["permissions"][permission_key] = enabled
    
    # ==================== ONGLET JOURNAL SYSTÈME ====================
    def setup_activity_tab(self):
        """Configurer l'onglet du journal d'activité système"""
        layout, _activity_scroll, _activity_outer = self._add_scrollable_content(
            self.activity_tab, "activityTabContent"
        )
        
        # Barre d'outils du journal
        toolbar = QFrame()
        toolbar_layout = QHBoxLayout(toolbar)
        
        # Filtres
        self.username_filter = QLineEdit()
        self.username_filter.setPlaceholderText("Nom d'utilisateur...")
        
        self.action_filter = QComboBox()
        self.action_filter.addItem("Toutes les actions")
        self.action_filter.addItems([
            "Connexion", "Déconnexion", "Création utilisateur", "Modification utilisateur",
            "Suppression utilisateur", "Changement mot de passe", "Modification rôle",
            "Export données", "Modification permissions", "Backup base données",
            "Restauration base données", "Optimisation base données", "Accès administration",
            "Consultation base données", "Exécution SQL", "Nettoyage logs", "Autre"
        ])
        
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate().addDays(-30))
        self.start_date.setCalendarPopup(True)
        
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        
        filter_btn = QPushButton("Filtrer")
        filter_btn.clicked.connect(self.filter_activities)
        
        clear_btn = QPushButton("Effacer les filtres")
        clear_btn.clicked.connect(self.clear_activity_filters)
        
        cleanup_btn = QPushButton("Nettoyer logs > 30 jours")
        cleanup_btn.clicked.connect(self.cleanup_old_logs)
        
        system_logs_btn = QPushButton("📄 Journaux système (fichiers)")
        system_logs_btn.setObjectName("systemLogsBtn")
        system_logs_btn.setCursor(Qt.PointingHandCursor)
        system_logs_btn.setToolTip(
            "Consulter et exporter les fichiers de logs / rapports de diagnostic "
            "générés par l'application (utile en cas de bug)."
        )
        system_logs_btn.clicked.connect(self.open_system_logs_dialog)

        toolbar_layout.addWidget(system_logs_btn)
        toolbar_layout.addWidget(QLabel("Utilisateur:"))
        toolbar_layout.addWidget(self.username_filter)
        toolbar_layout.addWidget(QLabel("Action:"))
        toolbar_layout.addWidget(self.action_filter)
        toolbar_layout.addWidget(QLabel("Du:"))
        toolbar_layout.addWidget(self.start_date)
        toolbar_layout.addWidget(QLabel("Au:"))
        toolbar_layout.addWidget(self.end_date)
        toolbar_layout.addWidget(filter_btn)
        toolbar_layout.addWidget(clear_btn)
        toolbar_layout.addWidget(cleanup_btn)
        toolbar_layout.addStretch()
        
        layout.addWidget(toolbar)
        
        # Statistiques des logs
        stats_frame = QFrame()
        stats_layout = QHBoxLayout(stats_frame)
        self.logs_stats_label = QLabel()
        stats_layout.addWidget(self.logs_stats_label)
        stats_layout.addStretch()
        layout.addWidget(stats_frame)
        
        # Journal
        self.activity_table = QTableWidget()
        self.activity_table.setObjectName("activityTable")
        self.activity_table.setColumnCount(6)
        self.activity_table.setHorizontalHeaderLabels([
            "ID", "Date/Heure", "Utilisateur", "Action", "Détails", "IP"
        ])
        
        self.activity_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.activity_table.verticalHeader().setVisible(False)
        
        layout.addWidget(self.activity_table)
        # Voile anti-gel posé sur le tableau (latence Supabase visible sans
        # bloquer les filtres de la barre d'outils).
        self._activities_overlay = LoadingOverlay(
            self.activity_table, "Chargement du journal…")
        
        # Pagination
        pagination_frame = QFrame()
        pagination_layout = QHBoxLayout(pagination_frame)
        
        self.prev_page_btn = QPushButton("◀ Précédent")
        self.prev_page_btn.clicked.connect(self.previous_logs_page)
        
        self.next_page_btn = QPushButton("Suivant ▶")
        self.next_page_btn.clicked.connect(self.next_logs_page)
        
        self.page_label = QLabel("Page 1")
        
        pagination_layout.addWidget(self.prev_page_btn)
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addWidget(self.next_page_btn)
        pagination_layout.addStretch()
        
        layout.addWidget(pagination_frame)
        
        # Charger les activités réelles
        self.load_real_activities()
    
    def load_real_activities(self):
        """Prépare les filtres puis lance le chargement dans un worker.

        get_logs() + get_statistics() coûtent 2 requêtes réseau (~300 ms) :
        exécutées dans le thread UI (bouton « Filtrer », pagination,
        ouverture de l'onglet), elles gelaient la fenêtre.
        """
        filters = {}

        username = self.username_filter.text().strip()
        if username:
            filters['username'] = username

        action = self.action_filter.currentText()
        if action != "Toutes les actions":
            filters['action'] = action

        start_date = self.start_date.date().toPython()
        end_date = self.end_date.date().toPython()
        if start_date:
            filters['start_date'] = datetime.combine(start_date, datetime.min.time())
        if end_date:
            filters['end_date'] = datetime.combine(end_date, datetime.max.time())

        if (self._activities_worker is not None
                and self._activities_worker.isRunning()):
            # Chargement en cours : on relancera à la fin (filtres récents).
            self._activities_pending = True
            return
        self._activities_worker = ActivitiesWorker(
            self.log_manager, filters, self.logs_per_page,
            self.current_logs_page * self.logs_per_page, parent=self)
        self._activities_worker.loaded.connect(self._render_activities)
        self._activities_worker.failed.connect(self._on_activities_error)
        self._activities_worker.finished.connect(self._on_activities_finished)
        self._activities_overlay.start()
        self._activities_worker.start()

    def _on_activities_finished(self):
        if self._activities_pending:
            self._activities_pending = False
            self.load_real_activities()

    def _on_activities_error(self, message):
        self._activities_overlay.stop()
        QMessageBox.warning(self, "Erreur",
                            f"Impossible de charger les logs: {message}")

    def _render_activities(self, payload):
        """Rendu du journal système (aucune requête : données du worker)."""
        self._activities_overlay.stop()
        result = payload['result']
        if result['success']:
            logs = result['logs']
            total = result['total']
            
            total_pages = (total + self.logs_per_page - 1) // self.logs_per_page if total > 0 else 1
            self.page_label.setText(f"Page {self.current_logs_page + 1}/{max(1, total_pages)}")
            self.prev_page_btn.setEnabled(self.current_logs_page > 0)
            self.next_page_btn.setEnabled((self.current_logs_page + 1) * self.logs_per_page < total)
            
            self.activity_table.setRowCount(len(logs))
            for row, log in enumerate(logs):
                id_item = QTableWidgetItem(str(log.id))
                id_item.setTextAlignment(Qt.AlignCenter)
                self.activity_table.setItem(row, 0, id_item)
                
                date_item = QTableWidgetItem(log.created_at.strftime("%d/%m/%Y %H:%M:%S"))
                date_item.setTextAlignment(Qt.AlignCenter)
                self.activity_table.setItem(row, 1, date_item)
                
                user_item = QTableWidgetItem(log.username)
                self.activity_table.setItem(row, 2, user_item)
                
                action_item = QTableWidgetItem(log.action)
                action_item.setTextAlignment(Qt.AlignCenter)
                
                if "Connexion" in log.action:
                    action_item.setForeground(QColor(0, 123, 255))
                elif "Suppression" in log.action:
                    action_item.setForeground(QColor(220, 53, 69))
                elif "Création" in log.action:
                    action_item.setForeground(QColor(40, 167, 69))
                elif "Backup" in log.action or "Restauration" in log.action:
                    action_item.setForeground(QColor(255, 193, 7))
                
                self.activity_table.setItem(row, 3, action_item)
                
                details_text = log.details if log.details else ""
                details_item = QTableWidgetItem(details_text)
                details_item.setToolTip(details_text)
                self.activity_table.setItem(row, 4, details_item)
                
                ip_item = QTableWidgetItem(log.ip_address or "N/A")
                ip_item.setTextAlignment(Qt.AlignCenter)
                self.activity_table.setItem(row, 5, ip_item)
            
            self.update_logs_statistics(payload['stats'])
        else:
            QMessageBox.warning(self, "Erreur", f"Impossible de charger les logs: {result.get('error')}")
    
    def update_logs_statistics(self, stats=None):
        """Mettre à jour les statistiques des logs système.

        `stats` est collecté par le worker ; `None` → requête directe.
        """
        if stats is None:
            stats = self.log_manager.get_statistics()
        if stats['success']:
            self.logs_stats_label.setText(
                f"📊 Total: {stats['total_logs']} logs | "
                f"📅 Aujourd'hui: {stats['today_logs']} | "
                f"👥 Utilisateurs actifs: {len(stats['users_stats'])}"
            )
    
    def cleanup_old_logs(self):
        """Nettoyer les vieux logs système"""
        reply = QMessageBox.question(
            self,
            "Nettoyage des logs",
            "Supprimer les logs de plus de 30 jours ?\nCette action est irréversible.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            result = self.log_manager.clear_old_logs(days=30)
            if result['success']:
                self.current_logs_page = 0
                self.load_real_activities()
                QMessageBox.information(self, "Succès", result['message'])
                
                self.log_activity(
                    user_id=self.get_current_user_id(),
                    username=self.get_current_username(),
                    action="Nettoyage logs",
                    details=f"Suppression des logs système de plus de 30 jours ({result['deleted_count']} logs)"
                )
            else:
                QMessageBox.critical(self, "Erreur", result['error'])
    
    def filter_activities(self):
        """Filtrer les activités système"""
        self.current_logs_page = 0
        self.load_real_activities()
    
    def clear_activity_filters(self):
        """Effacer les filtres d'activité système"""
        self.username_filter.clear()
        self.action_filter.setCurrentIndex(0)
        self.start_date.setDate(QDate.currentDate().addDays(-30))
        self.end_date.setDate(QDate.currentDate())
        self.filter_activities()
    
    def previous_logs_page(self):
        """Page précédente des logs système"""
        if self.current_logs_page > 0:
            self.current_logs_page -= 1
            self.load_real_activities()
    
    def next_logs_page(self):
        """Page suivante des logs système"""
        self.current_logs_page += 1
        self.load_real_activities()
    
    # ==================== ONGLET JOURNAL DES VENTES (NOUVEAU) ====================
    def setup_sale_logs_tab(self):
        """Configurer l'onglet du journal des ventes"""
        layout, _sale_logs_scroll, _sale_logs_outer = self._add_scrollable_content(
            self.sale_logs_tab, "saleLogsTabContent"
        )
        
        # Barre d'outils
        toolbar = QFrame()
        toolbar_layout = QHBoxLayout(toolbar)
        
        # Filtres
        self.sale_number_filter = QLineEdit()
        self.sale_number_filter.setPlaceholderText("N° vente...")
        
        self.sale_action_filter = QComboBox()
        self.sale_action_filter.addItem("Toutes les actions")
        self.sale_action_filter.addItems(["CREATE", "CANCEL", "REFUND", "PRINT"])
        
        self.sale_cashier_filter = QLineEdit()
        self.sale_cashier_filter.setPlaceholderText("Nom caissier...")
        
        self.sale_customer_filter = QLineEdit()
        self.sale_customer_filter.setPlaceholderText("Nom client...")
        
        self.sale_start_date = QDateEdit()
        self.sale_start_date.setDate(QDate.currentDate().addDays(-30))
        self.sale_start_date.setCalendarPopup(True)
        
        self.sale_end_date = QDateEdit()
        self.sale_end_date.setDate(QDate.currentDate())
        self.sale_end_date.setCalendarPopup(True)
        
        filter_btn = QPushButton("Filtrer")
        filter_btn.clicked.connect(self.filter_sale_logs)
        
        clear_btn = QPushButton("Effacer")
        clear_btn.clicked.connect(self.clear_sale_logs_filters)
        
        # Statistiques
        stats_btn = QPushButton("Statistiques")
        stats_btn.clicked.connect(self.show_sale_statistics)
        
        toolbar_layout.addWidget(QLabel("N° Vente:"))
        toolbar_layout.addWidget(self.sale_number_filter)
        toolbar_layout.addWidget(QLabel("Action:"))
        toolbar_layout.addWidget(self.sale_action_filter)
        toolbar_layout.addWidget(QLabel("Caissier:"))
        toolbar_layout.addWidget(self.sale_cashier_filter)
        toolbar_layout.addWidget(QLabel("Client:"))
        toolbar_layout.addWidget(self.sale_customer_filter)
        toolbar_layout.addWidget(QLabel("Du:"))
        toolbar_layout.addWidget(self.sale_start_date)
        toolbar_layout.addWidget(QLabel("Au:"))
        toolbar_layout.addWidget(self.sale_end_date)
        toolbar_layout.addWidget(filter_btn)
        toolbar_layout.addWidget(clear_btn)
        toolbar_layout.addWidget(stats_btn)
        toolbar_layout.addStretch()
        
        layout.addWidget(toolbar)
        
        # Statistiques des ventes
        stats_frame = QFrame()
        stats_layout = QHBoxLayout(stats_frame)
        self.sale_stats_label = QLabel()
        stats_layout.addWidget(self.sale_stats_label)
        stats_layout.addStretch()
        layout.addWidget(stats_frame)
        
        # Tableau des logs de ventes
        self.sale_logs_table = QTableWidget()
        self.sale_logs_table.setObjectName("saleLogsTable")
        self.sale_logs_table.setColumnCount(11)
        self.sale_logs_table.setHorizontalHeaderLabels([
            "ID", "Date/Heure", "N° Vente", "Action", "Caissier", "Rôle",
            "Client", "Montant", "Paiement", "Détails", "IP"
        ])
        
        header = self.sale_logs_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.Stretch)
        header.setSectionResizeMode(10, QHeaderView.ResizeToContents)
        
        self.sale_logs_table.verticalHeader().setVisible(False)
        self.sale_logs_table.setAlternatingRowColors(True)
        
        layout.addWidget(self.sale_logs_table)
        # Voile anti-gel posé sur le tableau (latence Supabase visible sans
        # bloquer les filtres de la barre d'outils).
        self._sale_logs_overlay = LoadingOverlay(
            self.sale_logs_table, "Chargement des logs de ventes…")
        
        # Pagination
        pagination_frame = QFrame()
        pagination_layout = QHBoxLayout(pagination_frame)
        
        self.sale_prev_page_btn = QPushButton("◀ Précédent")
        self.sale_prev_page_btn.clicked.connect(self.previous_sale_logs_page)
        
        self.sale_next_page_btn = QPushButton("Suivant ▶")
        self.sale_next_page_btn.clicked.connect(self.next_sale_logs_page)
        
        self.sale_page_label = QLabel("Page 1")
        
        pagination_layout.addWidget(self.sale_prev_page_btn)
        pagination_layout.addWidget(self.sale_page_label)
        pagination_layout.addWidget(self.sale_next_page_btn)
        pagination_layout.addStretch()
        
        layout.addWidget(pagination_frame)
        
        # Charger les logs de ventes
        self.load_sale_logs()
    
    def load_sale_logs(self):
        """Prépare les filtres puis lance le chargement dans un worker.

        get_sale_logs() + get_sale_statistics() sortent du thread UI : le
        thread ne fait que le rendu (`_render_sale_logs`).
        """
        filters = {}

        sale_number = self.sale_number_filter.text().strip()
        if sale_number:
            filters['sale_number'] = sale_number

        action = self.sale_action_filter.currentText()
        if action != "Toutes les actions":
            filters['action'] = action

        username = self.sale_cashier_filter.text().strip()
        if username:
            filters['username'] = username

        customer_name = self.sale_customer_filter.text().strip()
        if customer_name:
            filters['customer_name'] = customer_name

        start_date = self.sale_start_date.date().toPython()
        if start_date:
            filters['start_date'] = datetime.combine(start_date, datetime.min.time())

        end_date = self.sale_end_date.date().toPython()
        if end_date:
            filters['end_date'] = datetime.combine(end_date, datetime.max.time())

        if (self._sale_logs_worker is not None
                and self._sale_logs_worker.isRunning()):
            # Chargement en cours : on relancera à la fin (filtres récents).
            self._sale_logs_pending = True
            return
        self._sale_logs_worker = SaleLogsWorker(
            self.sale_log_manager, filters, self.sale_logs_per_page,
            self.current_sale_logs_page * self.sale_logs_per_page, parent=self)
        self._sale_logs_worker.loaded.connect(self._render_sale_logs)
        self._sale_logs_worker.failed.connect(self._on_sale_logs_error)
        self._sale_logs_worker.finished.connect(self._on_sale_logs_finished)
        self._sale_logs_overlay.start()
        self._sale_logs_worker.start()

    def _on_sale_logs_finished(self):
        if self._sale_logs_pending:
            self._sale_logs_pending = False
            self.load_sale_logs()

    def _on_sale_logs_error(self, message):
        self._sale_logs_overlay.stop()
        QMessageBox.warning(
            self, "Erreur",
            f"Impossible de charger les logs de ventes: {message}")

    def _render_sale_logs(self, payload):
        """Rendu du journal des ventes (aucune requête : données du worker)."""
        self._sale_logs_overlay.stop()
        result = payload['result']
        if result['success']:
            logs = result['logs']
            total = result['total']
            
            total_pages = (total + self.sale_logs_per_page - 1) // self.sale_logs_per_page if total > 0 else 1
            self.sale_page_label.setText(f"Page {self.current_sale_logs_page + 1}/{max(1, total_pages)}")
            self.sale_prev_page_btn.setEnabled(self.current_sale_logs_page > 0)
            self.sale_next_page_btn.setEnabled((self.current_sale_logs_page + 1) * self.sale_logs_per_page < total)
            
            self.sale_logs_table.setRowCount(len(logs))
            
            for row, log in enumerate(logs):
                # ID
                id_item = QTableWidgetItem(str(log.id))
                id_item.setTextAlignment(Qt.AlignCenter)
                self.sale_logs_table.setItem(row, 0, id_item)
                
                # Date/Heure
                date_item = QTableWidgetItem(log.created_at.strftime("%d/%m/%Y %H:%M:%S"))
                date_item.setTextAlignment(Qt.AlignCenter)
                self.sale_logs_table.setItem(row, 1, date_item)
                
                # N° Vente
                sale_item = QTableWidgetItem(log.sale_number)
                self.sale_logs_table.setItem(row, 2, sale_item)
                
                # Action avec couleur
                action_item = QTableWidgetItem(log.action)
                action_item.setTextAlignment(Qt.AlignCenter)
                if log.action == "CREATE":
                    action_item.setForeground(QColor(40, 167, 69))
                    action_item.setToolTip("Vente créée")
                elif log.action == "CANCEL":
                    action_item.setForeground(QColor(220, 53, 69))
                    action_item.setToolTip("Vente annulée")
                elif log.action == "REFUND":
                    action_item.setForeground(QColor(255, 193, 7))
                    action_item.setToolTip("Remboursement")
                elif log.action == "DELETE":
                    action_item.setForeground(QColor(255, 0, 0))
                    action_item.setToolTip("Vente supprimée définitivement")
                elif log.action == "PAID":
                    action_item.setForeground(QColor(0, 123, 255))
                    action_item.setToolTip("Vente à crédit encaissée en espèces")
                elif log.action == "PRINT":
                    action_item.setForeground(QColor(0, 123, 255))
                    action_item.setToolTip("Facture imprimée")
                self.sale_logs_table.setItem(row, 3, action_item)
                
                # Caissier
                cashier_item = QTableWidgetItem(log.username)
                self.sale_logs_table.setItem(row, 4, cashier_item)
                
                # Rôle
                role_item = QTableWidgetItem(log.user_role)
                role_item.setTextAlignment(Qt.AlignCenter)
                if log.user_role == "ADMIN":
                    role_item.setForeground(QColor(220, 53, 69))
                elif log.user_role == "GERANT":
                    role_item.setForeground(QColor(0, 123, 255))
                else:
                    role_item.setForeground(QColor(40, 167, 69))
                self.sale_logs_table.setItem(row, 5, role_item)
                
                # Client
                customer_item = QTableWidgetItem(log.customer_name or "Client général")
                self.sale_logs_table.setItem(row, 6, customer_item)
                
                # Montant
                amount_item = QTableWidgetItem(f"{log.total_amount:,.0f} FCFA")
                amount_item.setTextAlignment(Qt.AlignRight)
                amount_item.setForeground(QColor(0, 123, 255))
                self.sale_logs_table.setItem(row, 7, amount_item)
                
                # Paiement
                payment_item = QTableWidgetItem(log.payment_method or "-")
                payment_item.setTextAlignment(Qt.AlignCenter)
                self.sale_logs_table.setItem(row, 8, payment_item)
                
                # Détails
                details_item = QTableWidgetItem(log.details or "")
                details_item.setToolTip(log.details or "")
                self.sale_logs_table.setItem(row, 9, details_item)
                
                # IP
                ip_item = QTableWidgetItem(log.ip_address or "N/A")
                ip_item.setTextAlignment(Qt.AlignCenter)
                self.sale_logs_table.setItem(row, 10, ip_item)
            
            # Mettre à jour les statistiques
            self.update_sale_stats(payload['stats'])
        else:
            QMessageBox.warning(self, "Erreur", f"Impossible de charger les logs de ventes: {result.get('error')}")
    
    def update_sale_stats(self, stats=None):
        """Mettre à jour les statistiques des ventes.

        `stats` est collecté par le worker ; `None` → requête directe.
        """
        if stats is None:
            stats = self.sale_log_manager.get_sale_statistics()
        if stats['success']:
            self.sale_stats_label.setText(
                f"📊 Total logs: {stats['total_sale_logs']} | "
                f"📅 Ventes aujourd'hui: {stats['today_sales_count']} | "
                f"💰 Montant aujourd'hui: {stats['today_sales_amount']:,.0f} FCFA"
            )
    
    def filter_sale_logs(self):
        """Filtrer les logs de ventes"""
        self.current_sale_logs_page = 0
        self.load_sale_logs()
    
    def clear_sale_logs_filters(self):
        """Effacer les filtres des logs de ventes"""
        self.sale_number_filter.clear()
        self.sale_action_filter.setCurrentIndex(0)
        self.sale_cashier_filter.clear()
        self.sale_customer_filter.clear()
        self.sale_start_date.setDate(QDate.currentDate().addDays(-30))
        self.sale_end_date.setDate(QDate.currentDate())
        self.filter_sale_logs()
    
    def previous_sale_logs_page(self):
        """Page précédente des logs de ventes"""
        if self.current_sale_logs_page > 0:
            self.current_sale_logs_page -= 1
            self.load_sale_logs()
    
    def next_sale_logs_page(self):
        """Page suivante des logs de ventes"""
        self.current_sale_logs_page += 1
        self.load_sale_logs()
    
    def show_sale_statistics(self):
        """Afficher les statistiques détaillées des ventes dans une boîte de dialogue"""
        stats = self.sale_log_manager.get_sale_statistics()
        
        if not stats['success']:
            QMessageBox.critical(self, "Erreur", stats.get('error', 'Erreur inconnue'))
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Statistiques des ventes")
        dialog.setMinimumWidth(500)
        dialog.setMinimumHeight(400)
        
        layout = QVBoxLayout(dialog)
        
        # Titre
        title = QLabel("📊 STATISTIQUES DES VENTES")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1f2937; padding: 10px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Scroll area
        scroll = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # Statistiques générales
        general_group = QGroupBox("Général")
        general_layout = QFormLayout()
        
        total_logs_label = QLabel(f"{stats['total_sale_logs']:,}")
        today_sales_label = QLabel(f"{stats['today_sales_count']:,}")
        today_amount_label = QLabel(f"{stats['today_sales_amount']:,.0f} FCFA")
        
        general_layout.addRow("Total des opérations:", total_logs_label)
        general_layout.addRow("Ventes aujourd'hui:", today_sales_label)
        general_layout.addRow("Montant des ventes aujourd'hui:", today_amount_label)
        
        general_group.setLayout(general_layout)
        scroll_layout.addWidget(general_group)
        
        # Statistiques par action
        actions_group = QGroupBox("Par action")
        actions_layout = QVBoxLayout()
        
        for action, count in stats.get('actions_stats', {}).items():
            action_label = QLabel(f"{action}: {count} fois")
            if action == "CREATE":
                action_label.setStyleSheet("color: #10b981; font-weight: bold;")
            elif action == "CANCEL":
                action_label.setStyleSheet("color: #ef4444;")
            elif action == "REFUND":
                action_label.setStyleSheet("color: #f59e0b;")
            elif action == "DELETE":
                action_label.setStyleSheet("color: #ff0000;")
            elif action == "PAID":
                action_label.setStyleSheet("color: #007bff;")
            actions_layout.addWidget(action_label)
        
        actions_group.setLayout(actions_layout)
        scroll_layout.addWidget(actions_group)
        
        # Statistiques par utilisateur
        users_group = QGroupBox("Par caissier")
        users_layout = QVBoxLayout()
        
        for username, count in stats.get('users_stats', {}).items():
            user_label = QLabel(f"{username}: {count} opérations")
            users_layout.addWidget(user_label)
        
        users_group.setLayout(users_layout)
        scroll_layout.addWidget(users_group)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        # Bouton fermer
        close_btn = QPushButton("Fermer")
        close_btn.clicked.connect(dialog.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-weight: bold;
                margin: 10px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        layout.addWidget(close_btn)
        
        dialog.exec()
    
    # ==================== ONGLET BASE DE DONNÉES ====================
    def setup_database_tab(self):
        """Configurer l'onglet de gestion de la base de données"""
        layout = QVBoxLayout(self.db_tab)
        
        scroll = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # Section: Informations
        info_group = QGroupBox("Informations base de données")
        info_layout = QFormLayout()
        
        self.db_type_label = QLabel()
        self.db_name_label = QLabel()
        self.db_size_label = QLabel()
        self.db_tables_label = QLabel()
        
        refresh_info_btn = QPushButton("Actualiser")
        refresh_info_btn.clicked.connect(self.refresh_database_info)
        
        info_layout.addRow("Type:", self.db_type_label)
        info_layout.addRow("Base:", self.db_name_label)
        info_layout.addRow("Taille:", self.db_size_label)
        info_layout.addRow("Tables:", self.db_tables_label)
        info_layout.addRow("", refresh_info_btn)
        
        info_group.setLayout(info_layout)
        scroll_layout.addWidget(info_group)
        
        # Section: Backup/Restauration
        backup_group = QGroupBox("Backup & Restauration")
        backup_layout = QVBoxLayout()
        
        backup_path_layout = QHBoxLayout()
        self.backup_path = QLineEdit()
        self.backup_path.setPlaceholderText("Chemin du backup...")
        browse_backup_btn = QPushButton("Parcourir")
        browse_backup_btn.clicked.connect(lambda: self.browse_file(self.backup_path, save=True))
        
        backup_path_layout.addWidget(self.backup_path)
        backup_path_layout.addWidget(browse_backup_btn)
        
        backup_btn = QPushButton("Créer un backup")
        backup_btn.clicked.connect(self.create_backup)
        
        restore_layout = QHBoxLayout()
        self.restore_path = QLineEdit()
        self.restore_path.setPlaceholderText("Chemin du backup à restaurer...")
        browse_restore_btn = QPushButton("Parcourir")
        browse_restore_btn.clicked.connect(lambda: self.browse_file(self.restore_path, save=False))
        
        restore_layout.addWidget(self.restore_path)
        restore_layout.addWidget(browse_restore_btn)
        
        restore_btn = QPushButton("Restaurer")
        restore_btn.clicked.connect(self.restore_backup)
        
        backup_layout.addWidget(QLabel("Nouveau backup:"))
        backup_layout.addLayout(backup_path_layout)
        backup_layout.addWidget(backup_btn)
        backup_layout.addWidget(QLabel("Restaurer depuis:"))
        backup_layout.addLayout(restore_layout)
        backup_layout.addWidget(restore_btn)
        
        backup_group.setLayout(backup_layout)
        scroll_layout.addWidget(backup_group)
        
        # Section: Backup Discord
        discord_group = QGroupBox("Backup vers Discord")
        discord_layout = QVBoxLayout()

        discord_hint = QLabel(
            "Envoyez une copie de la base de données sur un serveur Discord via un webhook.\n"
            "Créez un webhook dans : Paramètres du salon → Intégrations → Webhooks."
        )
        discord_hint.setWordWrap(True)

        self.discord_webhook = QLineEdit()
        self.discord_webhook.setPlaceholderText("https://discord.com/api/webhooks/...")
        # Le webhook est lu depuis les paramètres (company_settings.json, non
        # versionné car il contient un secret) — aucun fallback codé en dur.
        self.discord_webhook.setText(self.settings_manager.get_setting("discord_webhook_url") or "")

        discord_btn = QPushButton("Sauvegarder vers Discord")
        discord_btn.clicked.connect(self.backup_to_discord)
        self.discord_backup_btn = discord_btn

        discord_layout.addWidget(discord_hint)
        discord_layout.addWidget(QLabel("URL du webhook Discord:"))
        discord_layout.addWidget(self.discord_webhook)
        discord_layout.addWidget(discord_btn)

        discord_group.setLayout(discord_layout)
        scroll_layout.addWidget(discord_group)

        # Section: Maintenance
        maintenance_group = QGroupBox("Maintenance")
        maintenance_layout = QVBoxLayout()
        
        vacuum_btn = QPushButton("Optimiser la base de données (VACUUM)")
        vacuum_btn.clicked.connect(self.vacuum_database)
        
        maintenance_layout.addWidget(vacuum_btn)
        maintenance_group.setLayout(maintenance_layout)
        scroll_layout.addWidget(maintenance_group)
        
        # Section: Consultation des tables
        tables_group = QGroupBox("Consulter les tables")
        tables_layout = QVBoxLayout()
        
        table_selector_layout = QHBoxLayout()
        self.table_combo = QComboBox()
        self.table_combo.addItems(["users", "activity_logs", "sale_logs", "sales", "products", "customers"])
        self.table_combo.currentTextChanged.connect(self.load_table_data)
        
        self.table_limit = QLineEdit("100")
        self.table_limit.setValidator(QIntValidator(1, 1000))
        self.table_limit.setMaximumWidth(80)
        
        load_table_btn = QPushButton("Charger")
        load_table_btn.clicked.connect(self.load_table_data)
        
        table_selector_layout.addWidget(QLabel("Table:"))
        table_selector_layout.addWidget(self.table_combo)
        table_selector_layout.addWidget(QLabel("Limite:"))
        table_selector_layout.addWidget(self.table_limit)
        table_selector_layout.addWidget(load_table_btn)
        table_selector_layout.addStretch()
        
        self.table_data_view = QTableWidget()
        
        tables_layout.addLayout(table_selector_layout)
        tables_layout.addWidget(self.table_data_view)
        
        tables_group.setLayout(tables_layout)
        scroll_layout.addWidget(tables_group)
        
        # Section: SQL Personnalisé
        sql_group = QGroupBox("Exécuter SQL (Lecture seulement)")
        sql_layout = QVBoxLayout()
        
        self.sql_input = QTextEdit()
        self.sql_input.setPlaceholderText("SELECT * FROM users WHERE ...")
        self.sql_input.setMaximumHeight(100)
        
        execute_sql_btn = QPushButton("Exécuter")
        execute_sql_btn.clicked.connect(self.execute_custom_sql)
        
        self.sql_result_view = QTableWidget()
        
        sql_layout.addWidget(self.sql_input)
        sql_layout.addWidget(execute_sql_btn)
        sql_layout.addWidget(self.sql_result_view)
        
        sql_group.setLayout(sql_layout)
        scroll_layout.addWidget(sql_group)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        self.refresh_database_info()
    
    def refresh_database_info(self):
        """Actualiser les informations de la base de données (asynchrone, sans geler l'UI)."""
        # Évite les workers multiples si l'utilisateur clique plusieurs fois
        if getattr(self, "_db_info_worker", None) and self._db_info_worker.isRunning():
            return

        self.db_type_label.setText("Chargement…")

        self._db_info_worker = DbInfoWorker(self.db_manager, self)
        self._db_info_worker.finished.connect(self._on_db_info_loaded)
        self._db_info_worker.failed.connect(self._on_db_info_failed)
        self._db_info_worker.start()

    def _on_db_info_loaded(self, info):
        """Affiche les informations base de données collectées en arrière-plan."""
        self.db_type_label.setText(info['engine'])
        self.db_name_label.setText(info['database'])

        total_size = info.get('total_size', 0)
        if total_size:
            if total_size < 1024:
                size_str = f"{total_size} B"
            elif total_size < 1024 * 1024:
                size_str = f"{total_size / 1024:.2f} KB"
            else:
                size_str = f"{total_size / (1024 * 1024):.2f} MB"
            self.db_size_label.setText(size_str)
        else:
            # SQLite : taille du fichier ; sinon inconnue
            db_url = str(engine.url)
            if db_url.startswith("sqlite:///"):
                db_path = db_url.replace("sqlite:///", "")
                if os.path.exists(db_path):
                    size = os.path.getsize(db_path)
                    if size < 1024:
                        size_str = f"{size} B"
                    elif size < 1024 * 1024:
                        size_str = f"{size / 1024:.2f} KB"
                    else:
                        size_str = f"{size / (1024 * 1024):.2f} MB"
                    self.db_size_label.setText(size_str)

        self.db_tables_label.setText(f"{len(info['tables'])} tables")

        self.log_activity(
            user_id=self.get_current_user_id(),
            username=self.get_current_username(),
            action="Consultation base données",
            details="Informations base de données consultées"
        )

    def _on_db_info_failed(self, error):
        """Erreur lors de la collecte des informations base de données."""
        self.db_type_label.setText("Erreur")
        self.db_tables_label.setText("—")
        QMessageBox.critical(self, "Erreur", f"Impossible de lire les informations de la base : {error}")
    
    def browse_file(self, line_edit, save=True):
        """Ouvrir un dialogue pour choisir un fichier"""
        # PostgreSQL/Supabase produit des backups JSON ; SQLite produit des .db.
        filters = (
            "Backups (*.json *.db *.sqlite *.bak);;"
            "Export JSON (*.json);;"
            "Base SQLite (*.db *.sqlite);;"
            "Tous les fichiers (*.*)"
        )
        if save:
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Choisir l'emplacement du backup",
                "",
                filters
            )
        else:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Choisir le fichier de backup",
                "",
                filters
            )

        if path:
            line_edit.setText(path)
    
    def create_backup(self):
        """Créer un backup de la base de données"""
        backup_path = self.backup_path.text().strip()
        if not backup_path:
            QMessageBox.warning(self, "Erreur", "Veuillez spécifier un chemin pour le backup")
            return
        
        result = self.db_manager.backup_database(backup_path)
        
        if result['success']:
            QMessageBox.information(self, "Succès", result['message'])
            
            self.log_activity(
                user_id=self.get_current_user_id(),
                username=self.get_current_username(),
                action="Backup base données",
                details=f"Backup créé: {backup_path} ({result.get('size', 0)} bytes)"
            )
        else:
            QMessageBox.critical(self, "Erreur", result['message'])
    
    def backup_to_discord(self):
        """Envoyer un backup de la base de données sur un serveur Discord (webhook)."""
        webhook_url = self.discord_webhook.text().strip()
        if not webhook_url:
            QMessageBox.warning(self, "Erreur", "Veuillez saisir l'URL du webhook Discord.")
            return

        if not webhook_url.lower().startswith("http"):
            QMessageBox.warning(self, "Erreur", "L'URL du webhook Discord doit commencer par http(s).")
            return

        # Mémoriser l'URL du webhook dans les paramètres
        self.settings_manager.set_setting("discord_webhook_url", webhook_url)

        # Désactiver le bouton pendant l'envoi
        self.discord_backup_btn.setEnabled(False)
        self.discord_backup_btn.setText("Envoi en cours...")

        def on_finished(result):
            self.discord_backup_btn.setEnabled(True)
            self.discord_backup_btn.setText("Sauvegarder vers Discord")

            if result.get('success'):
                QMessageBox.information(
                    self,
                    "Succès",
                    f"{result.get('message')}\nFichier : {result.get('filename')} "
                    f"({result.get('size', 0) / 1024:.2f} Ko)",
                )
                self.log_activity(
                    user_id=self.get_current_user_id(),
                    username=self.get_current_username(),
                    action="Backup base données",
                    details=f"Backup Discord envoyé: {result.get('filename')} "
                            f"({result.get('size', 0)} bytes)",
                )
            else:
                QMessageBox.critical(self, "Erreur", result.get('message', 'Erreur inconnue'))

        worker = DiscordBackupWorker(self.db_manager, webhook_url, self)
        worker.finished.connect(on_finished)
        worker.start()

    def restore_backup(self):
        """Restaurer un backup"""
        backup_path = self.restore_path.text().strip()
        if not backup_path:
            QMessageBox.warning(self, "Erreur", "Veuillez spécifier le fichier de backup")
            return

        if not os.path.exists(backup_path):
            QMessageBox.warning(self, "Erreur", f"Fichier introuvable :\n{backup_path}")
            return

        reply = QMessageBox.question(
            self,
            "Confirmation",
            "⚠️ ATTENTION: La restauration va remplacer les données des tables "
            "contenues dans le backup.\n"
            "Les autres tables de la base sont conservées.\n\n"
            "Formats acceptés : export JSON (.json) ou base SQLite (.db).\n\n"
            "Continuer ?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            result = self.db_manager.restore_database(backup_path)
            
            if result['success']:
                QMessageBox.information(self, "Succès", result['message'])
                
                self.log_activity(
                    user_id=self.get_current_user_id(),
                    username=self.get_current_username(),
                    action="Restauration base données",
                    details=f"Base restaurée depuis: {backup_path}"
                )
                
                self.load_users_from_db()
                self.load_real_activities()
                self.load_sale_logs()
                self.refresh_database_info()
                self.filter_users()
            else:
                QMessageBox.critical(self, "Erreur", result['message'])
    
    def vacuum_database(self):
        """Optimiser la base de données"""
        reply = QMessageBox.question(
            self,
            "Optimisation",
            "Optimiser la base de données (VACUUM) ?\n"
            "Cela peut prendre quelques secondes.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            result = self.db_manager.vacuum_database()
            
            if result['success']:
                QMessageBox.information(self, "Succès", result['message'])
                
                self.log_activity(
                    user_id=self.get_current_user_id(),
                    username=self.get_current_username(),
                    action="Optimisation base données",
                    details="VACUUM exécuté avec succès"
                )
            else:
                QMessageBox.critical(self, "Erreur", result['message'])
    
    def load_table_data(self):
        """Charger les données d'une table"""
        table_name = self.table_combo.currentText()
        limit = int(self.table_limit.text()) if self.table_limit.text().isdigit() else 100
        
        result = self.db_manager.get_table_data(table_name, limit=limit)
        
        if result['success']:
            data = result['data']
            
            if data:
                columns = list(data[0].keys())
                self.table_data_view.setColumnCount(len(columns))
                self.table_data_view.setHorizontalHeaderLabels(columns)
                self.table_data_view.setRowCount(len(data))
                
                for row, record in enumerate(data):
                    for col, key in enumerate(columns):
                        value = str(record.get(key, ''))
                        item = QTableWidgetItem(value)
                        self.table_data_view.setItem(row, col, item)
                
                self.table_data_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            else:
                self.table_data_view.setRowCount(0)
                self.table_data_view.setColumnCount(1)
                self.table_data_view.setHorizontalHeaderLabels(["Aucune donnée"])
                
            QMessageBox.information(
                self,
                "Information",
                f"{len(data)} enregistrements chargés sur {result['total']} total"
            )
        else:
            QMessageBox.critical(self, "Erreur", result['message'])
    
    def execute_custom_sql(self):
        """Exécuter une requête SQL personnalisée"""
        sql_query = self.sql_input.toPlainText().strip()
        
        if not sql_query:
            QMessageBox.warning(self, "Erreur", "Veuillez saisir une requête SQL")
            return
        
        if not sql_query.upper().strip().startswith('SELECT'):
            QMessageBox.warning(self, "Erreur", "Seules les requêtes SELECT sont autorisées pour des raisons de sécurité")
            return
        
        result = self.db_manager.execute_sql(sql_query)
        
        if result['success']:
            if 'data' in result and result['data']:
                columns = result['columns']
                self.sql_result_view.setColumnCount(len(columns))
                self.sql_result_view.setHorizontalHeaderLabels(columns)
                self.sql_result_view.setRowCount(len(result['data']))
                
                for row, record in enumerate(result['data']):
                    for col, key in enumerate(columns):
                        value = str(record.get(key, ''))
                        item = QTableWidgetItem(value)
                        self.sql_result_view.setItem(row, col, item)
                
                self.sql_result_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
                
                QMessageBox.information(
                    self,
                    "Succès",
                    f"{result['row_count']} enregistrements retournés"
                )
                
                self.log_activity(
                    user_id=self.get_current_user_id(),
                    username=self.get_current_username(),
                    action="Exécution SQL",
                    details=f"SELECT exécuté: {sql_query[:100]}"
                )
            else:
                self.sql_result_view.setRowCount(0)
                self.sql_result_view.setColumnCount(1)
                self.sql_result_view.setHorizontalHeaderLabels(["Aucun résultat"])
                QMessageBox.information(self, "Information", "Aucun résultat retourné")
        else:
            QMessageBox.critical(self, "Erreur SQL", result['message'])
    
    # ==================== GESTION DES UTILISATEURS ====================
    def load_users(self):
        """Charger les utilisateurs dans le tableau"""
        self.users_table.setRowCount(len(self.filtered_users))
        
        for row, user in enumerate(self.filtered_users):
            id_item = QTableWidgetItem(str(user.id))
            id_item.setTextAlignment(Qt.AlignCenter)
            self.users_table.setItem(row, 0, id_item)
            
            username_item = QTableWidgetItem(user.username)
            self.users_table.setItem(row, 1, username_item)
            
            email_text = user.email if user.email else "Non défini"
            email_item = QTableWidgetItem(email_text)
            self.users_table.setItem(row, 2, email_item)
            
            role_display = self.get_role_display_name(user.role)
            role_item = QTableWidgetItem(role_display)
            role_item.setTextAlignment(Qt.AlignCenter)
            
            if user.role == "ADMIN":
                role_item.setForeground(QColor(220, 53, 69))
            elif user.role == "GERANT":
                role_item.setForeground(QColor(0, 123, 255))
            else:
                role_item.setForeground(QColor(40, 167, 69))
                
            self.users_table.setItem(row, 3, role_item)
            
            status_icon = "✓" if user.active else "✗"
            status_text = f"{status_icon} {'Actif' if user.active else 'Inactif'}"
            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignCenter)
            
            if user.active:
                status_item.setForeground(QColor(40, 167, 69))
            else:
                status_item.setForeground(QColor(220, 53, 69))
                
            self.users_table.setItem(row, 4, status_item)
            
            created_date = user.created_at.strftime("%d/%m/%Y %H:%M") if user.created_at else "N/A"
            date_item = QTableWidgetItem(created_date)
            date_item.setTextAlignment(Qt.AlignCenter)
            self.users_table.setItem(row, 5, date_item)
            
            if user.last_login:
                last_login = user.last_login.strftime("%d/%m/%Y %H:%M")
            else:
                last_login = "Jamais"
            login_item = QTableWidgetItem(last_login)
            login_item.setTextAlignment(Qt.AlignCenter)
            self.users_table.setItem(row, 6, login_item)
            
            permissions = self.get_role_permissions(user.role)
            active_perms = sum(1 for p in permissions.values() if p)
            total_perms = len(permissions)
            perms_text = f"{active_perms}/{total_perms} permissions"
            perms_item = QTableWidgetItem(perms_text)
            perms_item.setTextAlignment(Qt.AlignCenter)
            perms_item.setToolTip(self.get_permissions_tooltip(permissions))
            self.users_table.setItem(row, 7, perms_item)
            
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)
            actions_layout.setSpacing(10)
            
            edit_btn = QPushButton()
            edit_btn.setIcon(self.style.standardIcon(QStyle.SP_FileIcon))
            edit_btn.setToolTip("Modifier l'utilisateur")
            edit_btn.clicked.connect(lambda _, u=user: self.edit_user(u))
            
            toggle_btn = QPushButton()
            if user.active:
                toggle_btn.setIcon(self.style.standardIcon(QStyle.SP_DialogCancelButton))
                toggle_btn.setToolTip("Désactiver le compte")
            else:
                toggle_btn.setIcon(self.style.standardIcon(QStyle.SP_DialogOkButton))
                toggle_btn.setToolTip("Activer le compte")
            toggle_btn.clicked.connect(lambda _, u=user: self.toggle_user_status(u))
            
            reset_btn = QPushButton()
            reset_btn.setIcon(self.style.standardIcon(QStyle.SP_BrowserReload))
            reset_btn.setToolTip("Réinitialiser le mot de passe")
            reset_btn.clicked.connect(lambda _, u=user: self.reset_password(u))
            
            perms_btn = QPushButton()
            perms_btn.setIcon(self.style.standardIcon(QStyle.SP_FileDialogInfoView))
            perms_btn.setToolTip("Voir les permissions")
            perms_btn.clicked.connect(lambda _, u=user: self.view_user_permissions(u))
            
            delete_btn = QPushButton()
            delete_btn.setIcon(self.style.standardIcon(QStyle.SP_TrashIcon))
            delete_btn.setToolTip("Supprimer l'utilisateur")
            delete_btn.clicked.connect(lambda _, u=user: self.delete_user(u))
            
            actions_layout.addWidget(edit_btn)
            actions_layout.addWidget(toggle_btn)
            actions_layout.addWidget(reset_btn)
            actions_layout.addWidget(perms_btn)
            actions_layout.addWidget(delete_btn)
            actions_layout.setAlignment(Qt.AlignCenter)
            
            self.users_table.setCellWidget(row, 8, actions_widget)
    
    def get_role_display_name(self, role_key):
        """Libellé lisible d'un rôle (source unique : core.permissions)."""
        return role_display_name(role_key)
    
    def get_role_permissions(self, role_key):
        """Permissions d'un rôle, toutes clés présentes (booléens)."""
        role = self.roles_dict.get(role_key)
        if role is not None:
            return role.get("permissions", {})
        from core.permissions import permission_flags
        return permission_flags(role_key)
    
    def filter_users(self):
        """Filtrer les utilisateurs"""
        search_text = self.search_input.text().lower()
        role_filter = self.role_filter.currentText()
        status_filter = self.status_filter.currentText()
        
        self.filtered_users = []
        
        for user in self.users:
            email_text = user.email.lower() if user.email else ""
            matches_search = (search_text in user.username.lower() or 
                            search_text in email_text)
            
            role_display = self.get_role_display_name(user.role)
            matches_role = (role_filter == "Tous les rôles" or 
                          role_display == role_filter)
            
            if status_filter == "Actif":
                matches_status = user.active
            elif status_filter == "Inactif":
                matches_status = not user.active
            else:
                matches_status = True
            
            if matches_search and matches_role and matches_status:
                self.filtered_users.append(user)
        
        self.load_users()
        self.update_role_stats()
    
    def update_role_stats(self):
        """Mettre à jour les statistiques"""
        total = len(self.users)
        active = sum(1 for u in self.users if u.active)
        inactive = total - active
        
        admins = sum(1 for u in self.users if u.role == "ADMIN")
        gerants = sum(1 for u in self.users if u.role == "GERANT")
        cashiers = sum(1 for u in self.users if u.role == "CAISSIER")
        
        self.total_users_label.setText(f"Total: {total}")
        self.active_users_label.setText(f"✓ Actifs: {active}")
        self.inactive_users_label.setText(f"✗ Inactifs: {inactive}")
        self.admins_label.setText(f"Administrateurs: {admins}")
        self.gerants_label.setText(f"Gérants: {gerants}")
        self.cashiers_label.setText(f"Caissiers: {cashiers}")
    
    def show_create_user_dialog(self):
        """Créer un utilisateur — EXCLUSIVEMENT via Supabase Auth.

        Le compte est créé dans auth.users (Supabase), puis son profil
        public.users est généré automatiquement par le trigger PostgreSQL.
        Si Supabase refuse l'opération, AUCUN utilisateur n'est créé : il ne
        peut donc jamais exister de compte local sans accès Supabase.
        """
        from ui.views.admin_view import UserDialog
        dialog = UserDialog(self, mode="create", style=self.style,
                           available_roles=self.available_roles,
                           roles_dict=self.roles_dict)
        if not dialog.exec():
            return

        user_data = dialog.get_user_data()
        email = (user_data.get("email") or "").strip().lower()

        # Supabase Auth utilise l'email comme identifiant de connexion :
        # il n'est donc plus optionnel.
        if not email:
            QMessageBox.warning(
                self, "Email obligatoire",
                "Un email est obligatoire : Supabase Auth l'utilise comme\n"
                "identifiant de connexion (applications desktop et web).")
            return

        from core.supabase_auth import provision_auth_user, supabase_available

        if not supabase_available(self.db_session):
            QMessageBox.warning(
                self, "Supabase requis",
                "La création d'utilisateur est rattachée exclusivement à\n"
                "Supabase Auth et la base active ne permet pas de le joindre.\n\n"
                "Vérifiez la variable DATABASE_URL (projet Supabase).")
            return

        try:
            # 1) Compte Supabase Auth : source de vérité (email + mot de passe).
            ok, message = provision_auth_user(
                self.db_session, email, user_data["temp_password"],
                username=user_data["username"], role=user_data["role"],
                active=True, must_change_password=True)
            if not ok:
                self.db_session.rollback()
                QMessageBox.critical(
                    self, "Création refusée par Supabase Auth",
                    f"Aucun utilisateur n'a été créé.\n\n{message}")
                return

            # 2) Le trigger Supabase a créé le profil : on le recharge pour
            #    appliquer exactement le username et le rôle demandés.
            self.db_session.flush()
            new_user = (self.db_session.query(User)
                        .filter(User.email == email).first())
            if new_user is None:
                self.db_session.rollback()
                QMessageBox.critical(
                    self, "Synchronisation incomplète",
                    "Le compte Supabase Auth a été créé mais le profil\n"
                    "public.users n'a pas été généré (trigger absent ?).\n"
                    "Exécutez _apply_users_supabase_only.py puis réessayez.")
                return

            new_user.username = user_data["username"]
            new_user.role = user_data["role"]
            new_user.active = True
            new_user.must_change_password = True
            self.db_session.commit()

            self.load_users_from_db()

            self.user_created.emit({
                "id": new_user.id,
                "username": new_user.username,
                "email": new_user.email,
                "role": new_user.role
            })

            self.log_activity(
                user_id=self.get_current_user_id(),
                username=self.get_current_username(),
                action="Création utilisateur",
                details=f"Création de {new_user.username} (Rôle: {new_user.role})"
            )

            self.filter_users()

            QMessageBox.information(
                self,
                "Succès",
                f"Utilisateur {new_user.username} créé avec succès!\n"
                f"Mot de passe temporaire: {user_data['temp_password']}\n\n"
                f"Compte Supabase Auth provisionné ({email}).\n"
                "Connexion valable sur l'application desktop ET web.")

        except Exception as e:
            self.db_session.rollback()
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la création: {str(e)}")

    
    def edit_user(self, user):
        """Modifier un utilisateur (profil propagé depuis Supabase Auth)."""
        from ui.views.admin_view import UserDialog
        dialog = UserDialog(self, mode="edit", user=user, style=self.style,
                           available_roles=self.available_roles,
                           roles_dict=self.roles_dict)
        if not dialog.exec():
            return

        user_data = dialog.get_user_data()
        new_email = (user_data.get("email") or "").strip().lower()

        if not new_email:
            QMessageBox.warning(
                self, "Email obligatoire",
                "L'email est obligatoire : c'est l'identifiant Supabase Auth.")
            return

        from core.supabase_auth import supabase_available, update_auth_profile

        if not supabase_available(self.db_session):
            QMessageBox.warning(
                self, "Supabase requis",
                "La modification des utilisateurs est rattachée exclusivement\n"
                "à Supabase Auth.")
            return

        old_role = user.role
        old_email = user.email

        try:
            # Une seule écriture (Supabase Auth) : le trigger propage ensuite
            # username / rôle / email vers le profil public.users.
            ok, message = update_auth_profile(
                self.db_session, old_email,
                username=user_data["username"], role=user_data["role"],
                new_email=new_email if new_email != old_email else None)
            if not ok:
                self.db_session.rollback()
                QMessageBox.critical(self, "Échec Supabase Auth",
                                     f"Modification annulée.\n\n{message}")
                return
            self.db_session.commit()

            self.db_session.expire_all()
            self.load_users_from_db()

            self.user_updated.emit({
                "id": user.id,
                "username": user_data["username"],
                "email": new_email,
                "role": user_data["role"]
            })

            role_change = (f" (Rôle: {old_role} → {user_data['role']})"
                           if old_role != user_data["role"] else "")
            self.log_activity(
                user_id=self.get_current_user_id(),
                username=self.get_current_username(),
                action="Modification utilisateur",
                details=f"Modification de {user_data['username']}{role_change}"
            )

            self.filter_users()

            QMessageBox.information(
                self, "Succès",
                "Utilisateur modifié avec succès!\n"
                "Profil synchronisé depuis Supabase Auth.")

        except Exception as e:
            self.db_session.rollback()
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la modification: {str(e)}")

    
    def toggle_user_status(self, user):
        """Activer/désactiver un utilisateur (statut porté par Supabase Auth)."""
        action = "désactiver" if user.active else "activer"
        target_active = not bool(user.active)

        reply = QMessageBox.question(
            self, "Confirmation",
            f"Êtes-vous sûr de vouloir {action} l'utilisateur '{user.username}' ?\n\n"
            "Le statut est appliqué dans Supabase Auth : la connexion sera\n"
            "refusée sur l'application desktop ET web (le mot de passe est conservé).",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        from core.supabase_auth import set_auth_active, supabase_available

        if not supabase_available(self.db_session):
            QMessageBox.warning(
                self, "Supabase requis",
                "Le statut des comptes est rattaché exclusivement à Supabase Auth.")
            return

        try:
            ok, message = set_auth_active(self.db_session, user.email, target_active)
            if not ok:
                self.db_session.rollback()
                QMessageBox.critical(self, "Échec Supabase Auth",
                                     f"Statut inchangé.\n\n{message}")
                return

            # Le trigger synchronise public.users.active : rien à écrire ici.
            self.db_session.commit()
            self.db_session.expire_all()
            self.load_users_from_db()

            status = "activé" if target_active else "désactivé"

            self.log_activity(
                user_id=self.get_current_user_id(),
                username=self.get_current_username(),
                action="Changement statut utilisateur",
                details=f"{'Activation' if target_active else 'Désactivation'} de {user.username}"
            )

            self.filter_users()

            QMessageBox.information(self, "Succès", f"Utilisateur {status} avec succès!")

        except Exception as e:
            self.db_session.rollback()
            QMessageBox.critical(self, "Erreur", f"Erreur lors du changement de statut: {str(e)}")

    
    def reset_password(self, user):
        """Réinitialiser le mot de passe (Supabase Auth = source de vérité)."""
        reply = QMessageBox.question(
            self, "Réinitialisation du mot de passe",
            f"Générer un nouveau mot de passe temporaire pour '{user.username}' ?\n"
            "L'utilisateur devra le changer à sa prochaine connexion.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        temp_password = self.generate_temp_password()

        from core.supabase_auth import supabase_available, update_auth_password

        if not supabase_available(self.db_session):
            QMessageBox.warning(
                self, "Supabase requis",
                "Les mots de passe sont gérés exclusivement par Supabase Auth.")
            return

        try:
            ok, message = update_auth_password(
                self.db_session, user.email, temp_password,
                must_change_password=True)
            if not ok:
                self.db_session.rollback()
                QMessageBox.critical(self, "Échec Supabase Auth",
                                     f"Mot de passe inchangé.\n\n{message}")
                return

            user.must_change_password = True
            self.db_session.commit()

            self.log_activity(
                user_id=self.get_current_user_id(),
                username=self.get_current_username(),
                action="Réinitialisation mot de passe",
                details=f"Réinitialisation du mot de passe de {user.username}"
            )

            QMessageBox.information(
                self,
                "Mot de passe temporaire",
                f"Mot de passe temporaire pour {user.username}:\n\n"
                f"{temp_password}\n\n"
                "Copiez ce mot de passe et donnez-le à l'utilisateur.\n"
                "Il devra le changer à sa prochaine connexion.\n\n"
                "Ce mot de passe est valable sur l'application desktop ET web."
            )

            self.password_reset.emit({
                "user_id": user.id,
                "username": user.username
            })

        except Exception as e:
            self.db_session.rollback()
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la réinitialisation: {str(e)}")

    
    def change_user_password(self, user):
        """Modifier le mot de passe d'un utilisateur (pour admin)"""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Modifier le mot de passe - {user.username}")
        dialog.setMinimumWidth(450)
        
        layout = QVBoxLayout(dialog)
        
        # Formulaire
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight)
        
        new_password_input = QLineEdit()
        new_password_input.setEchoMode(QLineEdit.Password)
        new_password_input.setMinimumHeight(36)
        new_password_input.setPlaceholderText("Nouveau mot de passe")
        
        confirm_password_input = QLineEdit()
        confirm_password_input.setEchoMode(QLineEdit.Password)
        confirm_password_input.setMinimumHeight(36)
        confirm_password_input.setPlaceholderText("Confirmer le mot de passe")
        
        form_layout.addRow("Nouveau mot de passe:", new_password_input)
        form_layout.addRow("Confirmer:", confirm_password_input)
        
        layout.addLayout(form_layout)
        
        # Boutons
        button_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("Annuler")
        cancel_btn.clicked.connect(dialog.reject)
        
        save_btn = QPushButton("Modifier le mot de passe")
        save_btn.clicked.connect(lambda: self._save_new_password(dialog, user, new_password_input.text(), confirm_password_input.text()))
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
        
        dialog.exec()
    
    def _save_new_password(self, dialog, user, new_password, confirm_password):
        """Sauvegarde le nouveau mot de passe dans Supabase Auth."""
        if not new_password or not confirm_password:
            QMessageBox.warning(dialog, "Erreur", "Veuillez remplir tous les champs.")
            return

        if new_password != confirm_password:
            QMessageBox.warning(dialog, "Erreur", "Les mots de passe ne correspondent pas.")
            return

        if len(new_password) < 6:
            QMessageBox.warning(dialog, "Erreur", "Le mot de passe doit contenir au moins 6 caractères.")
            return

        from core.supabase_auth import supabase_available, update_auth_password

        if not supabase_available(self.db_session):
            QMessageBox.warning(
                dialog, "Supabase requis",
                "Les mots de passe sont gérés exclusivement par Supabase Auth.")
            return

        try:
            ok, message = update_auth_password(
                self.db_session, user.email, new_password,
                must_change_password=False)
            if not ok:
                self.db_session.rollback()
                QMessageBox.critical(dialog, "Échec Supabase Auth",
                                     f"Mot de passe inchangé.\n\n{message}")
                return

            user.must_change_password = False
            self.db_session.commit()

            self.log_activity(
                user_id=self.get_current_user_id(),
                username=self.get_current_username(),
                action="Modification mot de passe",
                details=f"Modification du mot de passe de {user.username} par l'administrateur"
            )

            QMessageBox.information(
                dialog,
                "Succès",
                f"Mot de passe de {user.username} modifié avec succès!\n"
                "Le nouveau mot de passe est actif sur l'application desktop ET web.")

            dialog.accept()

        except Exception as e:
            self.db_session.rollback()
            QMessageBox.critical(dialog, "Erreur", f"Erreur lors de la modification: {str(e)}")

    
    def view_user_permissions(self, user):
        """Afficher les permissions d'un utilisateur"""
        from ui.views.admin_view import PermissionsDialog
        permissions = self.get_role_permissions(user.role)
        
        dialog = PermissionsDialog(self, user, permissions=permissions, 
                                  roles_dict=self.roles_dict, style=self.style)
        dialog.exec()
    
    def delete_user(self, user):
        """Supprimer un utilisateur (compte Supabase Auth, puis profil)."""
        current_username = self.get_current_username()
        current_user_id = self.get_current_user_id()

        if user.username == current_username:
            QMessageBox.warning(self, "Impossible", "Vous ne pouvez pas supprimer votre propre compte.")
            return

        if user.role == "ADMIN":
            admin_count = self.db_session.query(User).filter(User.role == "ADMIN").count()
            if admin_count <= 1:
                QMessageBox.warning(
                    self,
                    "Impossible",
                    "Impossible de supprimer le dernier administrateur.\n"
                    "Créez un autre administrateur avant de supprimer celui-ci."
                )
                return

        reply = QMessageBox.question(
            self, "Confirmation",
            f"Êtes-vous sûr de vouloir supprimer définitivement l'utilisateur '{user.username}' ?\n"
            f"Rôle: {user.role}\n"
            "Le compte Supabase Auth et son profil seront supprimés.\n"
            "Cette action est irréversible.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        from core.supabase_auth import delete_auth_user, supabase_available

        if not supabase_available(self.db_session):
            QMessageBox.warning(
                self, "Supabase requis",
                "La suppression des utilisateurs est rattachée exclusivement\n"
                "à Supabase Auth.")
            return

        user_id = user.id
        username = user.username
        user_role = user.role
        user_email = user.email

        try:
            self.log_activity(
                user_id=current_user_id,
                username=current_username,
                action="Suppression utilisateur",
                details=f"Suppression de {username} (ID: {user_id}, Rôle: {user_role})"
            )

            # 1) Supabase Auth : le trigger `on_auth_user_deleted` supprime le profil.
            ok, message = delete_auth_user(self.db_session, user_email)
            if not ok:
                self.db_session.rollback()
                QMessageBox.critical(self, "Échec Supabase Auth",
                                     f"Suppression annulée.\n\n{message}")
                return
            self.db_session.commit()

            # 2) Base sans trigger (déploiement non migré) : profil restant.
            self.db_session.expire_all()
            leftover = (self.db_session.query(User)
                        .filter(User.id == user_id).first())
            if leftover is not None:
                self.db_session.delete(leftover)
                self.db_session.commit()

            self.load_users_from_db()

            self.user_deleted.emit(user_id)

            self.filter_users()

            QMessageBox.information(
                self, "Succès",
                f"Utilisateur {username} ({user_role}) supprimé avec succès!\n"
                "Compte Supabase Auth retiré (accès web et desktop supprimés).")

        except Exception as e:
            self.db_session.rollback()
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la suppression: {str(e)}")

    
    def save_permissions(self):
        """Sauvegarder les permissions des rôles"""
        try:
            with open("roles_permissions.json", "w") as f:
                json.dump(self.roles_dict, f, indent=4, ensure_ascii=False)
            
            self.log_activity(
                user_id=self.get_current_user_id(),
                username=self.get_current_username(),
                action="Modification permissions",
                details="Permissions des rôles modifiées"
            )
            
            QMessageBox.information(self, "Succès", "Permissions sauvegardées avec succès!")
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la sauvegarde: {str(e)}")
    
    def reset_permissions_to_default(self):
        """Réinitialiser les permissions aux valeurs par défaut"""
        reply = QMessageBox.question(
            self, "Réinitialisation",
            "Êtes-vous sûr de vouloir réinitialiser toutes les permissions aux valeurs par défaut ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Retour à la matrice de référence (core.permissions), sans copie
            # locale : impossible de diverger de la source unique.
            self.roles_dict = describe_roles()
            
            self.log_activity(
                user_id=self.get_current_user_id(),
                username=self.get_current_username(),
                action="Réinitialisation permissions",
                details="Permissions réinitialisées aux valeurs par défaut"
            )
            
            # Reconstruire uniquement le contenu de la grille : réinstaller un
            # QVBoxLayout sur l'onglet (ancien appel à setup_roles_tab) était
            # refusé par Qt et laissait l'écran figé sur les anciennes cases.
            self._rebuild_role_groups()
            QMessageBox.information(self, "Succès", "Permissions réinitialisées aux valeurs par défaut!")
    
    def export_users(self):
        """Exporter la liste des utilisateurs"""
        try:
            export_data = []
            for user in self.filtered_users:
                export_data.append({
                    "ID": user.id,
                    "Nom d'utilisateur": user.username,
                    "Email": user.email if user.email else "",
                    "Rôle": self.get_role_display_name(user.role),
                    "Statut": "Actif" if user.active else "Inactif",
                    "Date création": user.created_at.strftime("%Y-%m-%d %H:%M") if user.created_at else "",
                    "Dernière connexion": user.last_login.strftime("%Y-%m-%d %H:%M") if user.last_login else "Jamais"
                })
            
            filename = f"users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, "w") as f:
                json.dump(export_data, f, indent=4, ensure_ascii=False)
            
            self.log_activity(
                user_id=self.get_current_user_id(),
                username=self.get_current_username(),
                action="Export données",
                details=f"Export de {len(export_data)} utilisateurs vers {filename}"
            )
            
            QMessageBox.information(self, "Export réussi", f"{len(export_data)} utilisateurs exportés vers {filename}")
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur d'export", f"Erreur lors de l'export: {str(e)}")
    
    def refresh_data(self):
        """Actualiser les données depuis la base"""
        try:
            self.load_users_from_db()
            self.filter_users()
            self.load_real_activities()
            self.load_sale_logs()
            self.refresh_database_info()
            QMessageBox.information(self, "Actualisation", "Données actualisées depuis la base de données.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de l'actualisation: {str(e)}")
    
    
    def generate_temp_password(self, length=10):
        letters = string.ascii_letters.replace('l', '').replace('I', '').replace('O', '')
        digits = string.digits.replace('0', '').replace('1', '')
        
        password = ''.join(random.choice(letters) for _ in range(8))
        password += ''.join(random.choice(digits) for _ in range(2))
        
        password_list = list(password)
        random.shuffle(password_list)
        return ''.join(password_list)
    
    def get_permissions_tooltip(self, permissions):
        active = [self.get_permission_name(key) for key, value in permissions.items() if value]
        if active:
            return "Permissions actives:\n• " + "\n• ".join(active)
        return "Aucune permission active"
    
    def get_permission_name(self, perm_key):
        """Libellé d'une permission (source unique : core.permissions)."""
        return permission_label(perm_key)
    
    def open_system_logs_dialog(self):
        """Ouvre le dialogue de consultation / export des journaux système (fichiers)."""
        dialog = SysLogsDialog(self.window())
        dialog.show()

    def log_activity(self, user_id, username, action, details=None, ip_address=None):
        return self.log_manager.add_log(
            user_id=user_id,
            username=username,
            action=action,
            details=details,
            ip_address=ip_address
        )
    
    def get_current_user_id(self):
        if isinstance(self.current_user, dict):
            return self.current_user.get('id')
        elif hasattr(self.current_user, 'id'):
            return self.current_user.id
        return None
    
    def get_current_username(self):
        if isinstance(self.current_user, dict):
            return self.current_user.get('username', 'unknown')
        elif hasattr(self.current_user, 'username'):
            return self.current_user.username
        return 'unknown'
    
    def apply_light_theme(self):
        import os
        possible_paths = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "themes", "admin.qss"),
        ]
        
        for path in possible_paths:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.setStyleSheet(f.read())
                    return
            except FileNotFoundError:
                continue


# ==================== CLASSES DE DIALOGUES ====================
class UserDialog(QDialog):
    """Dialogue pour créer/modifier un utilisateur"""
    
    def __init__(self, parent=None, mode="create", user=None, style=None, 
                 available_roles=None, roles_dict=None):
        super().__init__(parent)
        
        self.mode = mode
        self.user = user
        self.style = style or parent.style() if parent else QStyle()
        # Le paramètre prime (AdminView passe la liste canonique) ; le repli
        # utilise aussi la source unique pour ne jamais proposer GERANT.
        from core.permissions import available_roles as _available_roles
        self.available_roles = list(available_roles or _available_roles())
        self.roles_dict = roles_dict or {}
        
        self.setWindowTitle("Créer un utilisateur" if mode == "create" else "Modifier l'utilisateur")
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout(self)
        
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight)
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Nom d'utilisateur")
        
        self.email_input = QLineEdit()
        # L'email est l'identifiant Supabase Auth : il est obligatoire.
        self.email_input.setPlaceholderText("email@exemple.com (obligatoire)")
        
        self.role_combo = QComboBox()
        self.role_desc_label = QLabel()
        self.role_desc_label.setWordWrap(True)
        self.role_desc_label.setObjectName("roleDescLabel")
        
        for role_key in self.available_roles:
            role_name = self.roles_dict.get(role_key, {}).get("name", role_key)
            self.role_combo.addItem(role_name, role_key)
        
        self.role_combo.currentIndexChanged.connect(self.update_role_description)
        
        if mode == "create":
            # Option pour utiliser un mot de passe personnalisé
            self.use_custom_password = QCheckBox("Utiliser un mot de passe personnalisé")
            self.use_custom_password.toggled.connect(self.toggle_custom_password)
            
            # Mot de passe temporaire généré automatiquement
            self.password_label = QLabel("Mot de passe temporaire:")
            self.password_display = QLineEdit()
            self.password_display.setReadOnly(True)
            self.password_display.setStyleSheet("background-color: #f8f9fa;")
            
            self.temp_password = self.generate_temp_password()
            self.password_display.setText(self.temp_password)
            
            copy_btn = QPushButton("Copier")
            copy_btn.setIcon(self.style.standardIcon(QStyle.SP_FileDialogDetailedView))
            copy_btn.clicked.connect(self.copy_password)
            
            password_layout = QHBoxLayout()
            password_layout.addWidget(self.password_display)
            password_layout.addWidget(copy_btn)
            
            # Nouveau mot de passe personnalisé
            self.custom_password_label = QLabel("Nouveau mot de passe:")
            self.custom_password_input = QLineEdit()
            self.custom_password_input.setEchoMode(QLineEdit.Password)
            self.custom_password_input.setPlaceholderText("Laisser vide pour utiliser le mot de passe temporaire")
            self.custom_password_input.setEnabled(False)
            
            self.confirm_password_label = QLabel("Confirmer le mot de passe:")
            self.confirm_password_input = QLineEdit()
            self.confirm_password_input.setEchoMode(QLineEdit.Password)
            self.confirm_password_input.setPlaceholderText("Confirmer le mot de passe")
            self.confirm_password_input.setEnabled(False)
        
        if user:
            self.username_input.setText(user.username)
            self.email_input.setText(user.email if user.email else "")
            
            # Sélection par clé canonique (et non par libellé) : un rôle hérité
            # conserve sa valeur au lieu d'être réécrit silencieusement.
            target = normalize_role(user.role)
            index = self.role_combo.findData(target)
            if index < 0 and target:
                # Rôle hors matrice : on l'expose explicitement pour que
                # l'administrateur voie ce qu'il modifie.
                self.role_combo.addItem(role_display_name(user.role), target)
                index = self.role_combo.count() - 1
            if index >= 0:
                self.role_combo.setCurrentIndex(index)
        
        self.update_role_description()
        
        form_layout.addRow("Nom d'utilisateur:", self.username_input)
        form_layout.addRow("Email:", self.email_input)
        form_layout.addRow("Rôle:", self.role_combo)
        form_layout.addRow("", self.role_desc_label)
        
        if mode == "create":
            form_layout.addRow(self.use_custom_password)
            form_layout.addRow(self.password_label)
            form_layout.addRow(password_layout)
            form_layout.addRow(self.custom_password_label)
            form_layout.addRow(self.custom_password_input)
            form_layout.addRow(self.confirm_password_label)
            form_layout.addRow(self.confirm_password_input)
        
        layout.addLayout(form_layout)
        
        if mode == "create":
            validation_info = QLabel("Le mot de passe doit être changé à la première connexion.")
            validation_info.setObjectName("validationInfo")
            layout.addWidget(validation_info)
        
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("Enregistrer")
        save_btn.setIcon(self.style.standardIcon(QStyle.SP_DialogSaveButton))
        save_btn.setObjectName("saveButton")
        save_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("Annuler")
        cancel_btn.setIcon(self.style.standardIcon(QStyle.SP_DialogCancelButton))
        cancel_btn.setObjectName("cancelButton")
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
    
    def toggle_custom_password(self, checked):
        """Activer/désactiver le mode mot de passe personnalisé"""
        self.password_display.setEnabled(not checked)
        self.custom_password_input.setEnabled(checked)
        self.confirm_password_input.setEnabled(checked)
        
        if not checked:
            self.custom_password_input.clear()
            self.confirm_password_input.clear()
    
    def update_role_description(self):
        role_key = self.role_combo.currentData()
        if role_key and role_key in self.roles_dict:
            description = self.roles_dict[role_key].get(
                "description", role_description(role_key))
            self.role_desc_label.setText(description)
        else:
            self.role_desc_label.setText("")
    
    def get_user_data(self):
        email = self.email_input.text().strip()
        if email == "":
            email = None
        
        role_key = self.role_combo.currentData()
        
        # Déterminer le mot de passe à utiliser
        temp_password = getattr(self, 'temp_password', None)
        
        if self.mode == "create" and hasattr(self, 'use_custom_password'):
            if self.use_custom_password.isChecked():
                custom_password = self.custom_password_input.text()
                if custom_password:
                    temp_password = custom_password
        
        return {
            "username": self.username_input.text(),
            "email": email,
            "role": role_key or self.role_combo.currentText(),
            "temp_password": temp_password
        }
    
    def generate_temp_password(self, length=10):
        letters = string.ascii_letters.replace('l', '').replace('I', '').replace('O', '')
        digits = string.digits.replace('0', '').replace('1', '')
        
        password = ''.join(random.choice(letters) for _ in range(8))
        password += ''.join(random.choice(digits) for _ in range(2))
        
        password_list = list(password)
        random.shuffle(password_list)
        return ''.join(password_list)
    
    def copy_password(self):
        try:
            import pyperclip
            pyperclip.copy(self.temp_password)
        except ImportError:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(self.temp_password)
        QMessageBox.information(self, "Copié", "Mot de passe copié dans le presse-papier!")


class PermissionsDialog(QDialog):
    """Dialogue pour afficher les permissions d'un utilisateur"""
    
    def __init__(self, parent=None, user=None, permissions=None, roles_dict=None, style=None):
        super().__init__(parent)
        
        self.user = user
        self.permissions = permissions or {}
        self.roles_dict = roles_dict or {}
        self.style = style or parent.style() if parent else QStyle()
        self.setWindowTitle(f"Permissions - {user.username}")
        self.setMinimumSize(600, 500)
        
        layout = QVBoxLayout(self)
        
        header_layout = QHBoxLayout()
        
        user_icon = QLabel()
        user_icon.setPixmap(self.style.standardIcon(QStyle.SP_ComputerIcon).pixmap(32, 32))
        
        user_info = QLabel(f"<b>{user.username}</b><br>{user.email or 'Pas de email'}")
        user_info.setObjectName("userInfo")
        
        _role_display_name = self.roles_dict.get(user.role, {}).get(
            "name") or role_display_name(user.role)
        role_label = QLabel(f"Rôle: {_role_display_name}")
        role_label.setObjectName("roleLabel")
        
        header_layout.addWidget(user_icon)
        header_layout.addWidget(user_info)
        header_layout.addStretch()
        header_layout.addWidget(role_label)
        
        layout.addLayout(header_layout)
        
        permissions_frame = QFrame()
        permissions_frame.setObjectName("permissionsFrame")
        permissions_layout = QVBoxLayout(permissions_frame)
        
        perms_title = QLabel("Permissions attribuées:")
        perms_title.setObjectName("permsTitle")
        permissions_layout.addWidget(perms_title)
        
        permissions_list = permission_labels()
        
        for perm_name, perm_key, perm_desc in permissions_list:
            perm_layout = QHBoxLayout()
            
            status_icon = QLabel()
            if self.permissions.get(perm_key, False):
                status_icon.setPixmap(self.style.standardIcon(QStyle.SP_DialogApplyButton).pixmap(16, 16))
                status_text = "Autorisé"
            else:
                status_icon.setPixmap(self.style.standardIcon(QStyle.SP_DialogCancelButton).pixmap(16, 16))
                status_text = "Non autorisé"
            
            perm_label = QLabel(f"<b>{perm_name}</b><br><small>{perm_desc}</small>")
            perm_label.setWordWrap(True)
            
            status_label = QLabel(status_text)
            
            perm_layout.addWidget(status_icon)
            perm_layout.addWidget(perm_label, 1)
            perm_layout.addWidget(status_label)
            
            permissions_layout.addLayout(perm_layout)
        
        total_perms = len(self.permissions)
        active_perms = sum(1 for p in self.permissions.values() if p)
        
        stats_label = QLabel(f"<b>{active_perms}/{total_perms}</b> permissions actives")
        stats_label.setObjectName("statsLabel")
        stats_label.setAlignment(Qt.AlignCenter)
        permissions_layout.addWidget(stats_label)
        
        layout.addWidget(permissions_frame)
        
        button_layout = QHBoxLayout()
        
        close_btn = QPushButton("Fermer")
        close_btn.setIcon(self.style.standardIcon(QStyle.SP_DialogCloseButton))
        close_btn.clicked.connect(self.reject)
        
        if parent and user.role != "ADMIN":
            modify_btn = QPushButton("Modifier le rôle")
            modify_btn.setIcon(self.style.standardIcon(QStyle.SP_FileIcon))
            modify_btn.clicked.connect(lambda: self.modify_user_role(parent, user))
            button_layout.addWidget(modify_btn)
        
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def modify_user_role(self, admin_view, user):
        self.reject()
        admin_view.edit_user(user)
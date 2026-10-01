from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QLabel, QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QMargins 
from PySide6.QtCore import QDateTime, QThread, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QBrush
from PySide6.QtWidgets import QGraphicsDropShadowEffect

# Import différé de QtCharts (très lourd au chargement)
# Les imports sont faits dans setup_chart() et le rendu du graphe.

from core.database import SessionLocal
from sqlalchemy import func, desc
from sqlalchemy.orm import joinedload
from collections import defaultdict
from datetime import datetime, timedelta

# IMPORTS COMPLETS DES MODÈLES
from core.models.sale_models import Sale, SaleItem, Customer, Payment, SaleReturn
from core.models.stock_models import Product
from core.models.user import User

# IMPORT DU SETTINGS MANAGER
from utils.settings_manager import SettingsManager
from ui.loading import LoadingOverlay


class DashboardDataWorker(QThread):
    """Collecte les donnees du tableau de bord hors du thread de l'interface.

    Chaque requete est un aller-retour reseau vers Supabase : les executer dans
    le slot du QTimer (30 s) gelait la fenetre ~1 s a chaque passage. Le worker
    ne touche AUCUN widget : il renvoie des valeurs Python simples, le rendu
    restant dans le thread UI (voir `DashboardView._apply_data`).
    """

    data_ready = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            payload = self.collect()
        except Exception as exc:                   # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.data_ready.emit(payload)

    @staticmethod
    def collect():
        """Execute les requetes et renvoie un dictionnaire de valeurs brutes."""
        db = SessionLocal()
        try:
            now = datetime.now()
            today = now.date()
            start_of_day = datetime.combine(today, datetime.min.time())
            start_of_month = datetime(today.year, today.month, 1)

            total_today = db.query(func.sum(Sale.total_amount)).filter(
                Sale.sale_date >= start_of_day,
                Sale.sale_status == "COMPLETED"
            ).scalar() or 0

            total_month = db.query(func.sum(Sale.total_amount)).filter(
                Sale.sale_date >= start_of_month,
                Sale.sale_status == "COMPLETED"
            ).scalar() or 0

            active_customers = db.query(func.count(Customer.id)).filter(
                Customer.active == True                    # noqa: E712
            ).scalar() or 0

            low_stock = db.query(func.count(Product.id)).filter(
                Product.quantity <= Product.min_stock,
                Product.active == True                     # noqa: E712
            ).scalar() or 0

            # Graphe : totaux journaliers des 30 derniers jours (1 requete).
            daily_totals = defaultdict(float)
            for sale_date, amount in db.query(
                    Sale.sale_date, Sale.total_amount).filter(
                    Sale.sale_date >= now - timedelta(days=30),
                    Sale.sale_date <= now,
                    Sale.sale_status == "COMPLETED").all():
                if sale_date:
                    daily_totals[sale_date.date()] += float(amount or 0)

            # Produits les plus vendus des 7 derniers jours.
            top_products = db.query(
                Product.name,
                func.sum(SaleItem.quantity).label("total_quantity"),
                func.sum(SaleItem.line_total).label("total_revenue")
            ).join(SaleItem, SaleItem.product_id == Product.id) \
             .join(Sale, Sale.id == SaleItem.sale_id) \
             .filter(
                Sale.sale_date >= now - timedelta(days=7),
                Sale.sale_status == "COMPLETED"
            ).group_by(Product.id, Product.name) \
             .order_by(desc("total_quantity")).limit(5).all()

            # 10 dernieres ventes (hors annulations). Attention :
            # `Customer.full_name` est un @property Python (pas une colonne) :
            # on charge le client avec joinedload et on compose en Python.
            recent_sales = db.query(Sale) \
             .options(joinedload(Sale.customer)) \
             .filter(Sale.sale_status != "CANCELLED") \
             .order_by(desc(Sale.sale_date)).limit(10).all()

            return {
                "total_today": float(total_today or 0),
                "total_month": float(total_month or 0),
                "active_customers": int(active_customers or 0),
                "low_stock": int(low_stock or 0),
                "chart": dict(daily_totals),
                "top_products": [
                    (name, int(quantity or 0), float(revenue or 0))
                    for name, quantity, revenue in top_products
                ],
                "recent_sales": [
                    (s.sale_number, s.sale_date,
                     s.customer.full_name if s.customer else "—",
                     s.payment_status)
                    for s in recent_sales
                ],
            }
        finally:
            db.close()


class DashboardView(QWidget):
    def __init__(self, user_data):
        super().__init__()
        self.user_data = user_data  # Peut être un dict ou un objet User
        # Initialiser le gestionnaire de paramètres (Singleton garanti par __new__)
        self.settings_manager = SettingsManager()
        self.init_ui()
        self.setup_chart()
        self.apply_light_theme()
        #: Worker de collecte en cours (voir `load_real_data`).
        self._data_worker = None
        self._data_loaded = False
        # Voile anti-gel : affiché seulement au premier chargement (cartes
        # vides) ; les rafraîchissements de 30 s ne font que changer le libellé.
        self._overlay = LoadingOverlay(
            self, "Chargement du tableau de bord…")
        self.load_real_data()
        # Timer pour rafraîchir les données périodiquement
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(30000)  # Rafraîchir toutes les 30 secondes
        
    def init_ui(self):
        # Disposition principale
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # Logo et nom de l'entreprise
        company_info = self.settings_manager.get_company_info()
        company_name = company_info.get('name', 'Entreprise')
        company_logo_path = self.settings_manager.get_logo_path()
        
        logo_label = QLabel()
        if company_logo_path:
            from PySide6.QtGui import QPixmap
            pixmap = QPixmap(company_logo_path)
            if not pixmap.isNull():
                logo_label.setPixmap(pixmap.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            # Fallback: afficher les initiales
            from PySide6.QtCore import QSize
            
            class SimpleLogo(QLabel):
                def __init__(self, text):
                    super().__init__()
                    self.text = text
                    self.setFixedSize(40, 40)
                    
                def paintEvent(self, event):
                    painter = QPainter(self)
                    painter.setRenderHint(QPainter.Antialiasing)
                    painter.setBrush(QBrush(QColor("#3B82F6")))
                    painter.setPen(Qt.NoPen)
                    painter.drawEllipse(0, 0, 40, 40)
                    painter.setPen(Qt.white)
                    painter.setFont(QFont("Arial", 14, QFont.Bold))
                    painter.drawText(self.rect(), Qt.AlignCenter, self.text[0] if self.text else "E")
                    
            logo_label = SimpleLogo(company_name)
        
        # Informations de l'entreprise
        company_layout = QVBoxLayout()
        company_layout.setSpacing(2)
        
        self.company_name_label = QLabel(company_name)
        self.company_name_label.setObjectName("companyName")
        
        company_address = company_info.get('address', '')
        if company_address:
            self.company_address_label = QLabel(company_address)
            self.company_address_label.setObjectName("companyAddress")
            company_layout.addWidget(self.company_address_label)
            
        company_layout.addWidget(self.company_name_label)
        
        # Informations utilisateur
        user_layout = QVBoxLayout()
        user_layout.setSpacing(2)
        
        # Récupérer le nom d'utilisateur
        username = "Utilisateur"
        if isinstance(self.user_data, dict):
            username = self.user_data.get('username', 'Utilisateur')
        elif hasattr(self.user_data, 'username'):
            username = self.user_data.username
        
        self.user_label = QLabel(f"Connecté en tant que : {username}")
        self.user_label.setObjectName("userInfo")
        
        # Date et heure actuelle
        from PySide6.QtCore import QDate
        current_date = QDate.currentDate().toString("dddd d MMMM yyyy")
        self.date_label = QLabel(current_date)
        self.date_label.setObjectName("currentDate")
        
        user_layout.addWidget(self.user_label)
        user_layout.addWidget(self.date_label)
        
        # Ligne séparatrice
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("color: #E5E7EB;")
        main_layout.addWidget(separator)
        
        # Disposition pour les cartes de statistiques
        stats_layout = QGridLayout()
        stats_layout.setSpacing(20)
        
        # Carte : Ventes du jour
        self.total_sales_card = self.create_stat_card("Ventes du jour", "0 FCFA")
        stats_layout.addWidget(self.total_sales_card, 0, 0)
        
        # Carte : Ventes du mois
        self.month_sales_card = self.create_stat_card("Ventes du mois", "0 FCFA")
        stats_layout.addWidget(self.month_sales_card, 0, 1)
        
        # Carte : Clients actifs
        self.active_customers_card = self.create_stat_card("Clients actifs", "0")
        stats_layout.addWidget(self.active_customers_card, 0, 2)
        
        # Carte : Produits en stock bas
        self.low_stock_card = self.create_stat_card("Stock bas", "0")
        stats_layout.addWidget(self.low_stock_card, 0, 3)
        
        main_layout.addLayout(stats_layout)
        
        # Section graphiques et tableaux
        charts_tables_layout = QHBoxLayout()
        charts_tables_layout.setSpacing(20)
        
        # Colonne gauche - Graphique des revenus (plus grande)
        left_column_layout = QVBoxLayout()
        left_column_layout.setSpacing(10)
        
        chart_header_layout = QHBoxLayout()
        
        chart_label = QLabel("Revenu des 30 derniers jours")
        chart_label.setObjectName("sectionTitle")
        chart_header_layout.addWidget(chart_label)
        
        # Indicateur de mise à jour
        self.update_label = QLabel("Dernière mise à jour: --:--")
        self.update_label.setObjectName("updateLabel")
        chart_header_layout.addWidget(self.update_label, alignment=Qt.AlignRight)
        
        left_column_layout.addLayout(chart_header_layout)
        
        # Conteneur du graphique (plus grand)
        chart_container_frame = QFrame()
        chart_container_frame.setObjectName("chartContainer")
        chart_container_frame.setMinimumHeight(400)
        chart_container_frame.setStyleSheet("""
            #chartContainer {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
            }
        """)
        
        chart_internal_layout = QVBoxLayout(chart_container_frame)
        chart_internal_layout.setContentsMargins(0, 0, 0, 0)
        # QChartView sera créé dans setup_chart() (import QtCharts différé)
        self.chart_view = None
        # Réservation d'espace pour le graphique
        chart_internal_layout.addWidget(QFrame())
        self._chart_container_layout = chart_internal_layout
        
        left_column_layout.addWidget(chart_container_frame)
        
        # Légende sous le graphique
        legend_layout = QHBoxLayout()
        legend_layout.setAlignment(Qt.AlignCenter)
        
        legend_color = QLabel()
        legend_color.setFixedSize(20, 20)
        legend_color.setStyleSheet("background-color: #3B82F6; border-radius: 3px;")
        
        # Utiliser la devise depuis les paramètres
        currency = self.settings_manager.get_setting('currency', 'FCFA')
        legend_text = QLabel(f"Revenu quotidien ({currency})")
        legend_text.setObjectName("legendText")
        
        legend_layout.addWidget(legend_color)
        legend_layout.addWidget(legend_text)
        legend_layout.addStretch()
        
        left_column_layout.addLayout(legend_layout)
        
        charts_tables_layout.addLayout(left_column_layout, 2)  # 2/3 de largeur
        
        # Colonne droite - Produits les plus vendus et ventes récentes
        right_column_layout = QVBoxLayout()
        right_column_layout.setSpacing(20)
        
        # Section produits les plus vendus
        top_products_container = QFrame()
        top_products_container.setObjectName("topProductsContainer")
        top_products_container.setStyleSheet("""
            #topProductsContainer {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        top_products_layout = QVBoxLayout(top_products_container)
        top_products_title = QLabel("Top 5 produits (7 jours)")
        top_products_title.setObjectName("sectionTitle")
        top_products_layout.addWidget(top_products_title)
        
        self.top_products_table = QTableWidget()
        self.top_products_table.setObjectName("productsTable")
        self.top_products_table.setColumnCount(4)
        self.top_products_table.setHorizontalHeaderLabels(["#", "Produit", "Qté", "Revenu"])
        # Politique de redimensionnement des colonnes
        header = self.top_products_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # # : taille automatique
        header.setSectionResizeMode(1, QHeaderView.Stretch)            # Produit : prend tout l'espace
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Qté : taille automatique
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Revenu : taille automatique
        self.top_products_table.setMinimumHeight(150)
        self.top_products_table.setAlternatingRowColors(True)
        self.top_products_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.top_products_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.top_products_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.top_products_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        top_products_layout.addWidget(self.top_products_table)
        right_column_layout.addWidget(top_products_container)
        
        # Section ventes récentes
        recent_sales_container = QFrame()
        recent_sales_container.setObjectName("recentSalesContainer")
        recent_sales_container.setStyleSheet("""
            #recentSalesContainer {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        recent_sales_layout = QVBoxLayout(recent_sales_container)
        recent_sales_title = QLabel("10 dernières ventes")
        recent_sales_title.setObjectName("sectionTitle")
        recent_sales_layout.addWidget(recent_sales_title)
        
        self.recent_sales_table = QTableWidget()
        self.recent_sales_table.setObjectName("salesTable")
        self.recent_sales_table.setColumnCount(4)
        self.recent_sales_table.setHorizontalHeaderLabels(["N° Vente", "Date", "Client", "Statut"])
        # Politique de redimensionnement des colonnes
        header = self.recent_sales_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # N° Vente : taille auto
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Date : taille auto
        header.setSectionResizeMode(2, QHeaderView.Stretch)            # Client : prend l'espace
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Statut : taille auto
        self.recent_sales_table.setMinimumHeight(200)
        self.recent_sales_table.setAlternatingRowColors(True)
        self.recent_sales_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.recent_sales_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.recent_sales_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.recent_sales_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        recent_sales_layout.addWidget(self.recent_sales_table)
        right_column_layout.addWidget(recent_sales_container)
        
        charts_tables_layout.addLayout(right_column_layout, 1)  # 1/3 de largeur
        
        main_layout.addLayout(charts_tables_layout)
        
        self.setLayout(main_layout)
        
    def apply_shadow(self, widget, blur=20, x=0, y=6, color=QColor(0, 0, 0, 80)):
        shadow = QGraphicsDropShadowEffect(widget)
        shadow.setBlurRadius(blur)
        shadow.setOffset(x, y)
        shadow.setColor(color)
        widget.setGraphicsEffect(shadow)
    
    def create_stat_card(self, title, value):
        # Crée une carte de statistique
        card_frame = QFrame()
        card_frame.setObjectName("statCard")
        card_frame.setMinimumHeight(100)
        self.apply_shadow(card_frame)
        card_layout = QVBoxLayout(card_frame)
        card_layout.setAlignment(Qt.AlignCenter)
        
        card_title_label = QLabel(title)
        card_title_label.setObjectName("statTitle")
        card_value_label = QLabel(value)
        card_value_label.setObjectName("statValue")
        
        card_layout.addWidget(card_title_label)
        card_layout.addWidget(card_value_label)
        
        return card_frame
        
    def setup_chart(self):
        """Configure le graphique avec les axes (import QtCharts différé)"""
        from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis, QDateTimeAxis
        
        # Créer le QChartView maintenant (import QtCharts chargé)
        self.chart_view = QChartView()
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setStyleSheet("background-color: transparent;")
        # Remplacer le placeholder par le vrai QChartView
        if hasattr(self, '_chart_container_layout'):
            placeholder = self._chart_container_layout.itemAt(0)
            if placeholder and placeholder.widget():
                placeholder.widget().deleteLater()
            self._chart_container_layout.insertWidget(0, self.chart_view)
        
        self.chart = QChart()
        self.chart.setBackgroundBrush(Qt.transparent)
        self.chart.setAnimationOptions(QChart.SeriesAnimations)
        self.chart.setMargins(QMargins(0, 0, 0, 0))
        
        # Crée les axes
        self.date_axis = QDateTimeAxis()
        self.date_axis.setFormat("dd MMM")
        self.date_axis.setTitleText("Date")
        self.date_axis.setTitleFont(QFont("Arial", 10, QFont.Bold))
        self.date_axis.setLabelsFont(QFont("Arial", 9))
        self.date_axis.setTickCount(6)
        
        self.value_axis = QValueAxis()
        # Utiliser la devise depuis les paramètres
        currency = self.settings_manager.get_setting('currency', 'FCFA')
        self.value_axis.setTitleText(f"Revenu ({currency})")
        self.value_axis.setLabelFormat("%'d")
        self.value_axis.setTitleFont(QFont("Arial", 10, QFont.Bold))
        self.value_axis.setLabelsFont(QFont("Arial", 9))
        
        # Ajoute les axes au graphique
        self.chart.addAxis(self.date_axis, Qt.AlignBottom)
        self.chart.addAxis(self.value_axis, Qt.AlignLeft)
        
        # Cache la légende
        self.chart.legend().hide()
        
        self.chart_view.setChart(self.chart)
    
    
    def load_real_data(self):
        """Demande une collecte en arriere-plan (aucune requete dans le thread UI).

        Le QTimer de 30 s et l'ouverture de l'ecran passent par ici : la fenetre
        ne se fige donc plus pendant que les donnees sont lues.
        """
        worker = self._data_worker
        if worker is not None and worker.isRunning():
            # Collecte precedente encore en cours : on ne les empile pas.
            return
        self._data_worker = DashboardDataWorker(self)
        self._data_worker.data_ready.connect(self._apply_data)
        self._data_worker.failed.connect(self._on_data_error)
        if self._data_loaded:
            # Données déjà affichées : retour discret, pas de voile clignotant.
            self.update_label.setText("Actualisation…")
        else:
            self._overlay.start()
        self._data_worker.start()

    # ------------------------------------------------------------------
    # Rendu (thread UI) : uniquement de l'affichage, aucune requete.
    # ------------------------------------------------------------------
    def _apply_data(self, data):
        """Applique les donnees collectees par `DashboardDataWorker`."""
        self._data_loaded = True
        self._overlay.stop()
        currency = self.settings_manager.get_setting('currency', 'FCFA')
        self.update_label.setText(
            f"Dernière mise à jour: {datetime.now().strftime('%H:%M:%S')}")

        self.update_card_value(
            self.total_sales_card, f"{data['total_today']:,.0f} {currency}")
        self.update_card_value(
            self.month_sales_card, f"{data['total_month']:,.0f} {currency}")
        self.update_card_value(
            self.active_customers_card, f"{data['active_customers']}")
        self.update_card_value(self.low_stock_card, f"{data['low_stock']}")

        self._render_chart(data.get("chart") or {})
        self._render_top_products(data.get("top_products") or [], currency)
        self._render_recent_sales(data.get("recent_sales") or [])

    def _on_data_error(self, message):
        """Connexion indisponible : on l'affiche au lieu de figer la fenetre."""
        self._overlay.stop()
        print(f"Erreur lors du chargement des données: {message}")
        self.update_label.setText("Dernière mise à jour: échec de connexion")

    def _render_chart(self, daily_totals):
        """Trace le graphe des 30 derniers jours (rendu seul, sans requete)."""
        from PySide6.QtCharts import QLineSeries

        self.chart.removeAllSeries()

        revenue_series = QLineSeries()
        revenue_series.setName("Revenu quotidien")
        pen = QPen(QColor(59, 130, 246))
        pen.setWidth(3)
        pen.setStyle(Qt.SolidLine)
        revenue_series.setPen(pen)

        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        max_value = 0
        for i in range(31):
            current_date = start_date + timedelta(days=i)
            total = float(daily_totals.get(current_date.date(), 0) or 0)
            revenue_series.append(
                QDateTime(current_date).toMSecsSinceEpoch(), total)
            max_value = max(max_value, total)

        # Si pas de données réelles, pas de graphique (éviter données de démo)
        if max_value == 0:
            self.chart_view.update()
            return

        self.chart.addSeries(revenue_series)
        revenue_series.attachAxis(self.date_axis)
        revenue_series.attachAxis(self.value_axis)

        self.date_axis.setRange(QDateTime(start_date), QDateTime(end_date))
        self.value_axis.setRange(0, max_value * 1.2)

        revenue_series.setPointsVisible(True)
        revenue_series.setPointLabelsVisible(True)
        revenue_series.setPointLabelsFormat("@yPoint")

        self.chart_view.update()

    def _render_top_products(self, rows, currency):
        """Remplit le tableau des produits les plus vendus."""
        self.top_products_table.setRowCount(len(rows))
        for row, (name, quantity, revenue) in enumerate(rows):
            self.top_products_table.setItem(
                row, 0, QTableWidgetItem(str(row + 1)))
            self.top_products_table.setItem(row, 1, QTableWidgetItem(str(name)))
            self.top_products_table.setItem(row, 2, QTableWidgetItem(f"{quantity}"))
            self.top_products_table.setItem(
                row, 3, QTableWidgetItem(f"{revenue:,.0f} {currency}"))

    def _render_recent_sales(self, rows):
        """Remplit le tableau des ventes récentes (statuts colorés)."""
        status_map = {
            "PAID": "Payé",
            "PENDING": "En attente",
            "PARTIAL": "Partiel",
            "CANCELLED": "Annulé",
        }
        status_colors = {
            "PAID": QColor(220, 252, 231),      # Vert clair
            "PENDING": QColor(254, 226, 226),   # Rouge clair
            "PARTIAL": QColor(254, 249, 195),   # Jaune clair
            "CANCELLED": QColor(229, 231, 235),  # Gris clair
        }

        self.recent_sales_table.setRowCount(len(rows))
        for row, (number, sale_date, customer_name, status) in enumerate(rows):
            self.recent_sales_table.setItem(
                row, 0, QTableWidgetItem(number or ""))
            self.recent_sales_table.setItem(
                row, 1,
                QTableWidgetItem(sale_date.strftime("%d/%m/%Y %H:%M")
                                 if sale_date else "-"))
            self.recent_sales_table.setItem(
                row, 2, QTableWidgetItem(customer_name or "Non renseigné"))

            status_item = QTableWidgetItem(status_map.get(status, status or "-"))
            status_item.setTextAlignment(Qt.AlignCenter)
            color = status_colors.get(status)
            if color is not None:
                status_item.setBackground(color)
            self.recent_sales_table.setItem(row, 3, status_item)
    
    def update_card_value(self, card_frame, new_value):
        """Met à jour la valeur d'une carte de statistique"""
        layout = card_frame.layout()
        if layout and layout.count() >= 2:
            value_label = layout.itemAt(1).widget()
            if value_label:
                value_label.setText(new_value)
    
    def refresh_data(self):
        """Rafraîchit toutes les données"""
        try:
            # Mettre à jour la date
            from PySide6.QtCore import QDate
            current_date = QDate.currentDate().toString("dddd d MMMM yyyy")
            self.date_label.setText(current_date)
            
            self.load_real_data()
        except Exception as e:
            print(f"Erreur lors du rafraîchissement: {e}")
    
    def closeEvent(self, event):
        """Arrêter le timer (et le worker) lors de la fermeture"""
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()
        # Un QThread detruit pendant son execution fait planter Qt : on lui
        # laisse le temps de finir (la requete est bornee cote base).
        worker = getattr(self, "_data_worker", None)
        if worker is not None and worker.isRunning():
            worker.wait(2000)
        super().closeEvent(event)
    
    def apply_light_theme(self):
        """Applique le thème clair"""
        import os
        
        # Chercher dans différents chemins possibles
        possible_paths = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "themes", "dashboard.qss"),
        ]
        
        for path in possible_paths:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.setStyleSheet(f.read())
                    return
            except FileNotFoundError:
                continue
        
        # Fallback au thème système avec un style minimal
        self.setStyleSheet("""
            /* En-tête */
            #companyName {
                font-size: 20px;
                color: #111827;
                font-weight: bold;
            }
            
            #companyAddress {
                font-size: 12px;
                color: #6B7280;
            }
            
            #userInfo {
                font-size: 14px;
                color: #374151;
                font-weight: 500;
            }
            
            #currentDate {
                font-size: 12px;
                color: #6B7280;
                font-style: italic;
            }
            
            /* Cartes de statistiques */
            #statCard {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 15px;
            }
            
            #statTitle {
                font-size: 14px;
                color: #6B7280;
                font-weight: 500;
            }
            
            #statValue {
                font-size: 24px;
                color: #111827;
                font-weight: bold;
            }
            
            #sectionTitle {
                font-size: 18px;
                color: #111827;
                font-weight: bold;
            }
            
            #updateLabel {
                font-size: 12px;
                color: #6B7280;
                font-style: italic;
            }
            
            QTableWidget {
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                background-color: white;
                alternate-background-color: #F9FAFB;
            }
            
            QTableWidget::item {
                padding: 8px;
                border: none;
            }
            
            QHeaderView::section {
                background-color: #F3F4F6;
                padding: 10px;
                border: none;
                font-weight: bold;
                color: #374151;
            }
            
            #topProductsContainer, #recentSalesContainer {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 10px;
            }
            
            #chartContainer {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
            }
            
            #legendText {
                font-size: 12px;
                color: #6B7280;
                font-weight: 500;
            }
        """)
    
    def refresh(self):
        """Méthode pour rafraîchir la vue depuis MainWindow"""
        self.refresh_data()
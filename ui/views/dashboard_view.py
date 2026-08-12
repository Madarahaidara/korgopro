from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QLabel, QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QMargins 
from PySide6.QtCore import QDateTime
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QBrush
from PySide6.QtWidgets import QGraphicsDropShadowEffect

# Import différé de QtCharts (très lourd au chargement)
# Les imports sont faits dans setup_chart() et load_chart_data()

from core.database import SessionLocal
from sqlalchemy import func, desc
from datetime import datetime, timedelta

# IMPORTS COMPLETS DES MODÈLES
from core.models.sale_models import Sale, SaleItem, Customer, Payment, SaleReturn
from core.models.stock_models import Product
from core.models.user import User

# IMPORT DU SETTINGS MANAGER
from utils.settings_manager import SettingsManager


class DashboardView(QWidget):
    def __init__(self, user_data):
        super().__init__()
        self.user_data = user_data  # Peut être un dict ou un objet User
        # Initialiser le gestionnaire de paramètres (Singleton garanti par __new__)
        self.settings_manager = SettingsManager()
        self.init_ui()
        self.setup_chart()
        self.apply_light_theme()
        self.load_real_data()
        self.debug_sales_data()
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
        try:
            self.company_name_label.setAccessibleName("Nom de la société")
            self.company_name_label.setAccessibleDescription(f"Nom de la société: {company_name}")
        except Exception:
            pass
        
        company_address = company_info.get('address', '')
        if company_address:
            self.company_address_label = QLabel(company_address)
            self.company_address_label.setObjectName("companyAddress")
            try:
                self.company_address_label.setAccessibleName("Adresse de la société")
                self.company_address_label.setAccessibleDescription(company_address)
            except Exception:
                pass
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
        try:
            self.user_label.setAccessibleName("Utilisateur connecté")
            self.user_label.setAccessibleDescription(f"Connecté en tant que {username}")
        except Exception:
            pass
        
        # Date et heure actuelle
        from PySide6.QtCore import QDate
        current_date = QDate.currentDate().toString("dddd d MMMM yyyy")
        self.date_label = QLabel(current_date)
        self.date_label.setObjectName("currentDate")
        try:
            self.date_label.setAccessibleName("Date actuelle")
            self.date_label.setAccessibleDescription(current_date)
        except Exception:
            pass
        
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
        try:
            chart_container_frame.setAccessibleName("Conteneur du graphique")
            chart_container_frame.setAccessibleDescription("Conteneur affichant le graphique des revenus des 30 derniers jours")
        except Exception:
            pass
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
        try:
            self.top_products_table.setAccessibleName("Table des produits les plus vendus")
            self.top_products_table.setAccessibleDescription("Table listant les produits les plus vendus et le revenu associé")
        except Exception:
            pass
        self.top_products_table.setColumnCount(3)
        self.top_products_table.setHorizontalHeaderLabels(["Produit", "Quantité", "Revenu"])
        self.top_products_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.top_products_table.setMinimumHeight(150)
        self.top_products_table.setAlternatingRowColors(True)
        self.top_products_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.top_products_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
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
        try:
            self.recent_sales_table.setAccessibleName("Table des ventes récentes")
            self.recent_sales_table.setAccessibleDescription("Liste des dernières ventes avec numéro, client et statut")
        except Exception:
            pass
        self.recent_sales_table.setColumnCount(3)
        self.recent_sales_table.setHorizontalHeaderLabels(["N° Vente", "Client", "Statut"])
        self.recent_sales_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.recent_sales_table.setMinimumHeight(200)
        self.recent_sales_table.setAlternatingRowColors(True)
        self.recent_sales_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.recent_sales_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
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
    
    def _get_db_session(self):
        """Crée une session DB fraîche pour chaque appel (pas de session persistante)"""
        return SessionLocal()
    
    def load_real_data(self):
        """Charge les données réelles depuis la base de données"""
        db = self._get_db_session()
        try:
            # Mettre à jour l'heure de mise à jour
            update_time = datetime.now().strftime("%H:%M:%S")
            self.update_label.setText(f"Dernière mise à jour: {update_time}")
            
            # 1. Calculer les ventes du jour
            today = datetime.now().date()
            start_of_day = datetime.combine(today, datetime.min.time())
            
            total_today = db.query(func.sum(Sale.total_amount)).filter(
                Sale.sale_date >= start_of_day,
                Sale.sale_status == "COMPLETED"
            ).scalar() or 0
            
            # Utiliser la devise depuis les paramètres
            currency = self.settings_manager.get_setting('currency', 'FCFA')
            # Mettre à jour la carte des ventes du jour
            self.update_card_value(self.total_sales_card, f"{total_today:,.0f} {currency}")
            
            # 2. Calculer les ventes du mois
            start_of_month = datetime(today.year, today.month, 1)
            
            total_month = db.query(func.sum(Sale.total_amount)).filter(
                Sale.sale_date >= start_of_month,
                Sale.sale_status == "COMPLETED"
            ).scalar() or 0
            
            # Mettre à jour la carte des ventes du mois
            self.update_card_value(self.month_sales_card, f"{total_month:,.0f} {currency}")
            
            # 3. Nombre de clients actifs
            active_customers = db.query(func.count(Customer.id)).filter(
                Customer.active == True
            ).scalar() or 0
            
            self.update_card_value(self.active_customers_card, f"{active_customers}")
            
            # 4. Produits en stock bas
            low_stock_products = db.query(func.count(Product.id)).filter(
                Product.quantity <= Product.min_stock,
                Product.active == True
            ).scalar() or 0
            
            self.update_card_value(self.low_stock_card, f"{low_stock_products}")
            
            # 5. Charger le graphique des 30 derniers jours
            self.load_chart_data(db)
            
            # 6. Charger les produits les plus vendus
            self.load_top_products(db)
            
            # 7. Charger les ventes récentes
            self.load_recent_sales(db)
            
        except Exception as e:
            print(f"Erreur lors du chargement des données: {e}")
        finally:
            db.close()
    
    def update_card_value(self, card_frame, new_value):
        """Met à jour la valeur d'une carte de statistique"""
        layout = card_frame.layout()
        if layout and layout.count() >= 2:
            value_label = layout.itemAt(1).widget()
            if value_label:
                value_label.setText(new_value)
    
    def debug_sales_data(self):
        """Méthode de débogage pour vérifier les ventes"""
        db = self._get_db_session()
        try:
            print("\n=== DÉBOGAGE DES DONNÉES DE VENTES ===")
            
            # 1. Vérifier le nombre total de ventes
            total_sales = db.query(func.count(Sale.id)).scalar()
            print(f"Nombre total de ventes dans la base: {total_sales}")
            
            # 2. Vérifier les ventes COMPLETED
            completed_sales = db.query(func.count(Sale.id)).filter(
                Sale.sale_status == "COMPLETED"
            ).scalar()
            print(f"Ventes COMPLETED: {completed_sales}")
            
            # 3. Vérifier les dates des dernières ventes
            recent_sales = db.query(Sale).order_by(desc(Sale.sale_date)).limit(5).all()
            print("\n5 dernières ventes:")
            for sale in recent_sales:
                print(f"  - {sale.sale_number}: {sale.sale_date} - {sale.total_amount} - {sale.sale_status}")
            
            # 4. Vérifier la requête spécifique du graphique
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            
            print(f"\nPériode analysée: {start_date.date()} à {end_date.date()}")
            
            sales_in_period = db.query(
                func.date(Sale.sale_date).label('date'),
                func.sum(Sale.total_amount).label('total'),
                func.count(Sale.id).label('count')
            ).filter(
                Sale.sale_date >= start_date,
                Sale.sale_date <= end_date,
                Sale.sale_status == "COMPLETED"
            ).group_by(func.date(Sale.sale_date)).all()
            
            print(f"Résultats groupés par jour: {len(sales_in_period)} jours avec ventes")
            for result in sales_in_period:
                print(f"  - {result.date}: {result.count} ventes, total = {result.total}")
            
            print("=== FIN DÉBOGAGE ===\n")
            
        except Exception as e:
            print(f"Erreur lors du débogage: {e}")
        finally:
            db.close()
        
    def load_chart_data(self, db=None):
        """Charge les données du graphique des 30 derniers jours"""
        from PySide6.QtCharts import QLineSeries
        
        close_session = False
        if db is None:
            db = self._get_db_session()
            close_session = True
        
        try:
            print("Chargement des données du graphique...")
            
            # Supprimer les séries existantes
            self.chart.removeAllSeries()
            
            # Créer une nouvelle série
            revenue_series = QLineSeries()
            revenue_series.setName("Revenu quotidien")
            
            # Style de la ligne
            pen = QPen(QColor(59, 130, 246))
            pen.setWidth(3)
            pen.setStyle(Qt.SolidLine)
            revenue_series.setPen(pen)
            
            # Obtenir les données des 30 derniers jours
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            
            # Récupérer toutes les ventes de la période
            all_sales = db.query(Sale).filter(
                Sale.sale_date >= start_date,
                Sale.sale_date <= end_date,
                Sale.sale_status == "COMPLETED"
            ).all()
            
            print(f"Ventes trouvées dans la période: {len(all_sales)}")
            
            # Grouper manuellement par jour
            from collections import defaultdict
            daily_totals = defaultdict(float)
            
            for sale in all_sales:
                # Extraire la date (sans l'heure)
                sale_date = sale.sale_date.date()
                daily_totals[sale_date] += sale.total_amount
            
            print(f"Jours avec ventes: {len(daily_totals)}")
            
            # Remplir la série
            data_points = []
            max_value = 0
            
            for i in range(31):
                current_date = start_date + timedelta(days=i)
                current_date_py = current_date.date()
                
                total = daily_totals.get(current_date_py, 0)
                data_points.append((current_date, total))
                max_value = max(max_value, total)
            
            # Trier par date
            data_points.sort(key=lambda x: x[0])
            
            # Ajouter à la série
            for date, total in data_points:
                qdatetime = QDateTime(date)
                revenue_series.append(qdatetime.toMSecsSinceEpoch(), total)
            
            print(f"Points dans la série: {revenue_series.count()}, Max: {max_value}")
            
            # Si pas de données réelles, pas de graphique (éviter données de démo)
            if max_value == 0:
                print("Aucune donnée réelle disponible pour le graphique")
                # Afficher un message plutôt que des données de démo
                self.chart.removeAllSeries()
                self.chart_view.update()
                return
            
            # Ajouter la série au graphique
            self.chart.addSeries(revenue_series)
            
            # Attacher les axes
            revenue_series.attachAxis(self.date_axis)
            revenue_series.attachAxis(self.value_axis)
            
            # Ajuster les axes
            self.date_axis.setRange(QDateTime(start_date), QDateTime(end_date))
            
            if max_value > 0:
                self.value_axis.setRange(0, max_value * 1.2)
            else:
                self.value_axis.setRange(0, 10000)
            
            # Rendre visible
            revenue_series.setPointsVisible(True)
            revenue_series.setPointLabelsVisible(True)
            revenue_series.setPointLabelsFormat("@yPoint")
            
            self.chart_view.update()
            
        except Exception as e:
            print(f"Erreur lors du chargement du graphique: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if close_session:
                db.close()
    
    def load_top_products(self, db=None):
        """Charge les produits les plus vendus des 7 derniers jours"""
        close_session = False
        if db is None:
            db = self._get_db_session()
            close_session = True
        
        try:
            start_date = datetime.now() - timedelta(days=7)
            
            # Requête pour les produits les plus vendus
            top_products = db.query(
                Product.name,
                func.sum(SaleItem.quantity).label('total_quantity'),
                func.sum(SaleItem.line_total).label('total_revenue')
            ).join(SaleItem, SaleItem.product_id == Product.id)\
             .join(Sale, Sale.id == SaleItem.sale_id)\
             .filter(
                Sale.sale_date >= start_date,
                Sale.sale_status == "COMPLETED"
            ).group_by(Product.id, Product.name)\
             .order_by(desc('total_quantity'))\
             .limit(5).all()
            
            # Utiliser la devise depuis les paramètres
            currency = self.settings_manager.get_setting('currency', 'FCFA')
            
            # Remplir le tableau
            self.top_products_table.setRowCount(len(top_products))
            
            for row, product in enumerate(top_products):
                self.top_products_table.setItem(row, 0, QTableWidgetItem(product.name))
                self.top_products_table.setItem(row, 1, QTableWidgetItem(f"{product.total_quantity}"))
                self.top_products_table.setItem(row, 2, QTableWidgetItem(f"{product.total_revenue:,.0f} {currency}"))
            
        except Exception as e:
            print(f"Erreur lors du chargement des produits: {e}")
        finally:
            if close_session:
                db.close()
    
    def load_recent_sales(self, db=None):
        """Charge les ventes récentes"""
        close_session = False
        if db is None:
            db = self._get_db_session()
            close_session = True
        
        try:
            # Obtenir les 10 dernières ventes
            recent_sales = db.query(Sale).join(Customer, Sale.customer_id == Customer.id, isouter=True)\
                .filter(Sale.sale_status != "CANCELLED")\
                .order_by(desc(Sale.sale_date))\
                .limit(10).all()
            
            # Remplir le tableau
            self.recent_sales_table.setRowCount(len(recent_sales))
            
            for row, sale in enumerate(recent_sales):
                # N° Vente (colonne 0)
                self.recent_sales_table.setItem(row, 0, QTableWidgetItem(sale.sale_number))
                
                # Client (colonne 1)
                customer_name = sale.customer.full_name if sale.customer else "Non renseigné"
                self.recent_sales_table.setItem(row, 1, QTableWidgetItem(customer_name))
                
                # Statut avec couleur (colonne 2)
                status_item = QTableWidgetItem(sale.payment_status)
                if sale.payment_status == "PAID":
                    status_item.setBackground(QColor(220, 252, 231))  # Vert clair
                elif sale.payment_status == "PENDING":
                    status_item.setBackground(QColor(254, 226, 226))  # Rouge clair
                elif sale.payment_status == "PARTIAL":
                    status_item.setBackground(QColor(254, 249, 195))  # Jaune clair
                elif sale.payment_status == "CANCELLED":
                    status_item.setBackground(QColor(229, 231, 235))  # Gris clair
                self.recent_sales_table.setItem(row, 2, status_item)
            
        except Exception as e:
            print(f"Erreur lors du chargement des ventes récentes: {e}")
        finally:
            if close_session:
                db.close()
    
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
        """Arrêter le timer lors de la fermeture"""
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()
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
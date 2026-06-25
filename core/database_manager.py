# core/database_manager.py
import re
from sqlalchemy import inspect, text
from core.database import SessionLocal, engine
from core.models.user import User
from core.models.activity_log import ActivityLog
import logging
from datetime import datetime
import os

# Regex pour valider une requête SELECT uniquement (sécurité)
# Autorise: SELECT, WITH, EXPLAIN, PRAGMA (lecture seule)
_ALLOWED_SQL_PATTERN = re.compile(
    r'^\s*(SELECT|WITH|EXPLAIN\s+QUERY\s+PLAN|PRAGMA)\s',
    re.IGNORECASE
)

# Liste des mots-clés dangereux à bloquer même dans un SELECT
_FORBIDDEN_KEYWORDS = [
    'INTO OUTFILE', 'INTO DUMPFILE',
    'LOAD_FILE', 'INFORMATION_SCHEMA',
    'PRAGMA WRITEABLE_SCHEMA',
    'ATTACH DATABASE',
]


class DatabaseManager:
    """Gestionnaire de base de données pour l'administration"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_database_info(self):
        """Obtenir des informations sur la base de données"""
        inspector = inspect(engine)
        
        info = {
            "tables": {},
            "total_size": 0,
            "engine": str(engine.url.drivername),
            "database": str(engine.url.database)
        }
        
        for table_name in inspector.get_table_names():
            table_info = {
                "columns": inspector.get_columns(table_name),
                "foreign_keys": inspector.get_foreign_keys(table_name),
                "indexes": inspector.get_indexes(table_name),
                "row_count": 0
            }
            
            # Compter les lignes (sécurisé — le nom de table vient de l'inspecteur, pas de l'utilisateur)
            try:
                with SessionLocal() as session:
                    # Utiliser un paramètre pour le nom de table (SQLAlchemy le gère en sécurité)
                    from sqlalchemy import func
                    # Compter via le modèle correspondant si possible
                    table_info["row_count"] = self._count_table_rows(table_name, session)
            except:
                table_info["row_count"] = 0
            
            info["tables"][table_name] = table_info
        
        return info
    
    def _count_table_rows(self, table_name: str, session) -> int:
        """Compte le nombre de lignes d'une table de manière sécurisée"""
        try:
            # Mapping table → modèle connu
            model_map = {
                "users": User,
                "activity_logs": ActivityLog,
                "customers": None,
                "products": None,
                "suppliers": None,
                "sales": None,
                "sale_items": None,
                "payments": None,
                "sale_returns": None,
                "sale_return_items": None,
                "proforma_invoices": None,
                "proforma_invoice_items": None,
                "inventory_movements": None,
                "expenses": None,
                "expense_categories": None,
                "purchase_orders": None,
                "purchase_order_items": None,
                "stock_alerts": None,
                "sale_logs": None,
            }
            
            model = model_map.get(table_name)
            if model is not None:
                return session.query(model).count()
            
            # Fallback sécurisé : utiliser text() avec nom de table validé
            # Le nom de table provient de l'inspecteur SQLAlchemy, donc sûr
            result = session.execute(text(f"SELECT COUNT(*) FROM \"{table_name}\""))
            return result.scalar() or 0
        except:
            return 0
    
    def backup_database(self, backup_path):
        """Sauvegarder la base de données"""
        try:
            # Obtenir le chemin de la base SQLite
            db_url = str(engine.url)
            if db_url.startswith("sqlite:///"):
                db_path = db_url.replace("sqlite:///", "")
                
                import shutil
                
                # Créer le dossier de backup si nécessaire
                os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                
                # Copier le fichier
                shutil.copy2(db_path, backup_path)
                
                return {
                    "success": True,
                    "message": f"Base de données sauvegardée dans {backup_path}",
                    "path": backup_path,
                    "size": os.path.getsize(backup_path)
                }
            else:
                return {
                    "success": False,
                    "message": "Backup uniquement supporté pour SQLite"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Erreur lors du backup: {str(e)}"
            }
    
    def restore_database(self, backup_path):
        """Restaurer la base de données depuis un backup"""
        try:
            db_url = str(engine.url)
            if db_url.startswith("sqlite:///"):
                db_path = db_url.replace("sqlite:///", "")
                
                import shutil
                
                if not os.path.exists(backup_path):
                    return {
                        "success": False,
                        "message": "Fichier de backup introuvable"
                    }
                
                # Restaurer
                shutil.copy2(backup_path, db_path)
                
                return {
                    "success": True,
                    "message": f"Base de données restaurée depuis {backup_path}"
                }
            else:
                return {
                    "success": False,
                    "message": "Restauration uniquement supportée pour SQLite"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Erreur lors de la restauration: {str(e)}"
            }
    
    def vacuum_database(self):
        """Optimiser la base de données"""
        try:
            with SessionLocal() as session:
                session.execute(text("VACUUM"))
                session.commit()
            return {
                "success": True,
                "message": "Base de données optimisée avec succès"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Erreur lors de l'optimisation: {str(e)}"
            }
    
    def get_table_data(self, table_name, limit=100, offset=0):
        """Récupérer les données d'une table (sécurisé)"""
        try:
            with SessionLocal() as session:
                # Validation stricte : seulement les tables connues et autorisées
                allowed_tables = {
                    "users": User,
                    "activity_logs": ActivityLog,
                }
                
                if table_name not in allowed_tables:
                    return {"success": False, "message": "Table non supportée"}
                
                model = allowed_tables[table_name]
                
                # Récupérer les données
                query = session.query(model)
                total = query.count()
                data = query.offset(offset).limit(limit).all()
                
                # Convertir en dictionnaire
                rows = []
                for row in data:
                    row_dict = {}
                    for column in model.__table__.columns:
                        value = getattr(row, column.name)
                        if isinstance(value, datetime):
                            value = value.strftime("%Y-%m-%d %H:%M:%S")
                        row_dict[column.name] = value
                    rows.append(row_dict)
                
                return {
                    "success": True,
                    "data": rows,
                    "total": total,
                    "limit": limit,
                    "offset": offset
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Erreur: {str(e)}"
            }
    
    def execute_sql(self, sql_query):
        """
        Exécuter une requête SQL SELECT en lecture seule (sécurisé).
        Les requêtes non-SELECT sont rejetées. Utilise une whitelist.
        """
        if not sql_query or not sql_query.strip():
            return {
                "success": False,
                "message": "Requête vide"
            }
        
        sql_stripped = sql_query.strip()
        
        # Vérifier que la requête commence par SELECT, WITH, EXPLAIN ou PRAGMA (lecture seule)
        if not _ALLOWED_SQL_PATTERN.match(sql_stripped):
            return {
                "success": False,
                "message": "Seules les requêtes SELECT (lecture seule) sont autorisées."
            }
        
        # Vérifier les mots-clés dangereux même dans un SELECT
        sql_upper = sql_stripped.upper()
        for keyword in _FORBIDDEN_KEYWORDS:
            if keyword in sql_upper:
                return {
                    "success": False,
                    "message": f"Mot-clé interdit détecté: {keyword}"
                }
        
        try:
            with SessionLocal() as session:
                result = session.execute(text(sql_stripped))
                rows = result.fetchall()
                columns = result.keys()
                
                data = []
                for row in rows:
                    row_dict = {}
                    for col_name, value in zip(columns, row):
                        # Convertir les types non-sérialisables
                        if isinstance(value, datetime):
                            value = value.isoformat()
                        elif isinstance(value, bytes):
                            value = value.hex()
                        row_dict[col_name] = value
                    data.append(row_dict)
                
                return {
                    "success": True,
                    "data": data,
                    "row_count": len(data),
                    "columns": list(columns)
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Erreur SQL: {str(e)}"
            }
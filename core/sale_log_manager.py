# core/sale_log_manager.py
from core.database import SessionLocal
from core.models.sale_log import SaleLog
from datetime import datetime, timedelta
import socket


class SaleLogManager:
    """Gestionnaire de logs spécifique aux ventes"""

    def __init__(self, session=None):
        # session can be an existing SQLAlchemy Session or None
        self._session = session

    def _get_db_session(self):
        return self._session if self._session is not None else SessionLocal()

    def add_sale_log(self, sale_id, sale_number, action, user_id, username, user_role,
                     total_amount, customer_id=None, customer_name=None,
                     payment_method=None, details=None, ip_address=None):
        """Ajouter un log de vente"""
        db_session = None
        try:
            db_session = self._get_db_session()
            log = SaleLog(
                sale_id=sale_id,
                sale_number=sale_number,
                action=action,
                user_id=user_id,
                username=username,
                user_role=user_role,
                customer_id=customer_id,
                customer_name=customer_name,
                total_amount=total_amount,
                payment_method=payment_method,
                details=details,
                ip_address=ip_address or SaleLogManager._get_local_ip(),
                created_at=datetime.now()
            )
            db_session.add(log)
            db_session.commit()
            return True
        except Exception as e:
            print(f"Erreur lors de l'ajout du log de vente: {e}")
            return False
        finally:
            # close only if we created the session locally
            if self._session is None and db_session is not None:
                try:
                    db_session.close()
                except Exception:
                    pass
    
    def get_sale_logs(self, sale_id=None, action=None, user_id=None, 
                      start_date=None, end_date=None, limit=100, offset=0):
        """Récupérer les logs de ventes avec filtres"""
        db_session = None
        try:
            db_session = self._get_db_session()
            query = db_session.query(SaleLog)

            if sale_id:
                query = query.filter(SaleLog.sale_id == sale_id)
            if action:
                query = query.filter(SaleLog.action == action)
            if user_id:
                query = query.filter(SaleLog.user_id == user_id)
            if start_date:
                query = query.filter(SaleLog.created_at >= start_date)
            if end_date:
                query = query.filter(SaleLog.created_at <= end_date)

            total = query.count()
            logs = query.order_by(SaleLog.created_at.desc()).offset(offset).limit(limit).all()

            return {
                "success": True,
                "logs": logs,
                "total": total,
                "limit": limit,
                "offset": offset
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            if self._session is None and db_session is not None:
                try:
                    db_session.close()
                except Exception:
                    pass
    
    def get_sale_statistics(self):
        """Obtenir des statistiques sur les ventes"""
        db_session = None
        try:
            db_session = self._get_db_session()
            from sqlalchemy import func

            total_sales = db_session.query(SaleLog).count()

            # Par action
            actions_stats = db_session.query(
                SaleLog.action,
                func.count(SaleLog.id).label('count')
            ).group_by(SaleLog.action).all()

            # Par utilisateur
            users_stats = db_session.query(
                SaleLog.username,
                func.count(SaleLog.id).label('count')
            ).group_by(SaleLog.username).all()

            # Ventes aujourd'hui
            today = datetime.now().date()
            today_sales = db_session.query(SaleLog).filter(
                func.date(SaleLog.created_at) == today,
                SaleLog.action == 'CREATE'
            ).count()

            # Montant total des ventes aujourd'hui
            today_amount = db_session.query(func.sum(SaleLog.total_amount)).filter(
                func.date(SaleLog.created_at) == today,
                SaleLog.action == 'CREATE'
            ).scalar() or 0

            return {
                "success": True,
                "total_sale_logs": total_sales,
                "today_sales_count": today_sales,
                "today_sales_amount": today_amount,
                "actions_stats": {action: count for action, count in actions_stats},
                "users_stats": {username: count for username, count in users_stats}
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            if self._session is None and db_session is not None:
                try:
                    db_session.close()
                except Exception:
                    pass
    
    @staticmethod
    def _get_local_ip():
        """Obtenir l'IP locale"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
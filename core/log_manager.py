# core/log_manager.py
from core.database import SessionLocal
from core.models.activity_log import ActivityLog
from datetime import datetime, timedelta
import socket
import platform

class LogManager:
    """Gestionnaire de logs d'activité"""
    
    @staticmethod
    def add_log(user_id, username, action, details=None, ip_address=None, user_agent=None):
        """Ajouter un log d'activité"""
        try:
            with SessionLocal() as session:
                log = ActivityLog(
                    user_id=user_id,
                    username=username,
                    action=action,
                    details=details,
                    ip_address=ip_address or LogManager._get_local_ip(),
                    user_agent=user_agent or platform.platform(),
                    created_at=datetime.now()
                )
                session.add(log)
                session.commit()
                return True
        except Exception as e:
            print(f"Erreur lors de l'ajout du log: {e}")
            return False
    
    @staticmethod
    def get_logs(filters=None, limit=100, offset=0):
        """Récupérer les logs avec filtres"""
        try:
            with SessionLocal() as session:
                query = session.query(ActivityLog)
                
                if filters:
                    if filters.get('user_id'):
                        query = query.filter(ActivityLog.user_id == filters['user_id'])
                    if filters.get('username'):
                        query = query.filter(ActivityLog.username.like(f"%{filters['username']}%"))
                    if filters.get('action'):
                        query = query.filter(ActivityLog.action.like(f"%{filters['action']}%"))
                    if filters.get('start_date'):
                        query = query.filter(ActivityLog.created_at >= filters['start_date'])
                    if filters.get('end_date'):
                        query = query.filter(ActivityLog.created_at <= filters['end_date'])
                
                total = query.count()
                logs = query.order_by(ActivityLog.created_at.desc()).offset(offset).limit(limit).all()
                
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
    
    @staticmethod
    def clear_old_logs(days=30):
        """Supprimer les logs plus vieux que X jours"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with SessionLocal() as session:
                deleted = session.query(ActivityLog).filter(
                    ActivityLog.created_at < cutoff_date
                ).delete()
                session.commit()
                return {
                    "success": True,
                    "deleted_count": deleted,
                    "message": f"{deleted} logs supprimés (plus vieux que {days} jours)"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def get_statistics():
        """Obtenir des statistiques sur les logs"""
        try:
            with SessionLocal() as session:
                from sqlalchemy import func
                
                total_logs = session.query(ActivityLog).count()
                
                # Par action
                actions_stats = session.query(
                    ActivityLog.action,
                    func.count(ActivityLog.id).label('count')
                ).group_by(ActivityLog.action).all()
                
                # Par utilisateur
                users_stats = session.query(
                    ActivityLog.username,
                    func.count(ActivityLog.id).label('count')
                ).group_by(ActivityLog.username).all()
                
                # Logs aujourd'hui
                today = datetime.now().date()
                today_logs = session.query(ActivityLog).filter(
                    func.date(ActivityLog.created_at) == today
                ).count()
                
                return {
                    "success": True,
                    "total_logs": total_logs,
                    "today_logs": today_logs,
                    "actions_stats": {action: count for action, count in actions_stats},
                    "users_stats": {username: count for username, count in users_stats}
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
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
# core/models/activity_log.py
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func
from core.database import Base

class ActivityLog(Base):
    __tablename__ = "activity_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)  # Peut être NULL pour actions système
    username = Column(String(50), nullable=False)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    # Colonne multi-entreprise (migration 0004/0005/0006)
    # Abandon du système multi-entreprise : organisation_id redevient nullable
    organization_id = Column(
        postgresql.UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime, default=func.now())
    
    def __repr__(self):
        return f"<ActivityLog {self.username} - {self.action}>"
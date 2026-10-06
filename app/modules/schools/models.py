from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
from app.core.database import Base

class School(Base):
    __tablename__ = "schools"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    domain = Column(String(200), unique=True, index=True, nullable=False)
    school_type = Column(String(50), default="Tecnica") # 'Tecnica' o 'Comun'
    primary_color = Column(String(7), default="#003366")
    secondary_color = Column(String(7), default="#cc9900")
    logo_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

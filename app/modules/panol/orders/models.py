from sqlalchemy import Column, Integer, ForeignKey, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="pendiente")
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User")
    items = relationship("OrderItem", back_populates="order")
    @property
    def profesor(self):
        return self.user.name if self.user else None

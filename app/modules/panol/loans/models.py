from sqlalchemy import Column, Integer, ForeignKey, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class Loan(Base):
    __tablename__ = "loans"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    panolero_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    tool_id = Column(Integer, ForeignKey("tools.id"))
    quantity = Column(Integer, default=1)
    description_loan = Column(String, nullable=True)
    description_return = Column(String, nullable=True)
    borrowed_at = Column(DateTime, default=datetime.utcnow)
    returned_at = Column(DateTime, nullable=True)
    status = Column(String, default="active")
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    
    user = relationship("User", foreign_keys=[user_id], back_populates="loans")
    panolero = relationship("User", foreign_keys=[panolero_id])
    tool = relationship("Tool")

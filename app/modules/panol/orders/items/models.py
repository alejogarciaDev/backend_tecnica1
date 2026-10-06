from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    tool_id = Column(Integer, ForeignKey("tools.id"))
    quantity = Column(Integer, default=1)
    
    order = relationship("Order", back_populates="items")
    tool = relationship("Tool")

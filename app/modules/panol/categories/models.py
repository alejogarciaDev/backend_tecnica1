from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)  # e.g., "Manual", "Eléctrica"

class ToolType(Base):
    __tablename__ = "tool_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # e.g., "Martillo", "Destornillador"
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    
    category = relationship("Category", backref="types")

class Tool(Base):
    __tablename__ = "tools"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # e.g., "Martillo de peña 300g"
    barcode = Column(String, unique=True, index=True, nullable=True)
    stock = Column(Integer, default=0)
    activo = Column(Boolean, default=True)
    type_id = Column(Integer, ForeignKey("tool_types.id"), nullable=False)
    
    tool_type = relationship("ToolType", backref="tools")

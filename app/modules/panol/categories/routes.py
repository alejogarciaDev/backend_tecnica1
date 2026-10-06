from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from .models import Category, ToolType, Tool
from pydantic import BaseModel
from typing import Optional, List
import random

router = APIRouter(prefix="/categories", tags=["Pañol - Categorías"])

# Schemas
class CategoryCreate(BaseModel):
    name: str

class TypeCreate(BaseModel):
    name: str
    category_id: int

class ToolCreate(BaseModel):
    name: str
    type_id: int
    barcode: Optional[str] = None
    stock: int = 1

# Category Routes (parent, e.g. "Manual", "Eléctrica")
@router.get("/")
def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).all()

@router.post("/")
def create_category(data: CategoryCreate, db: Session = Depends(get_db)):
    existing = db.query(Category).filter(Category.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="La categoría ya existe")
    cat = Category(name=data.name)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat

@router.get("/summary")
def get_categories_summary(db: Session = Depends(get_db)):
    types = db.query(ToolType).all()
    res = []
    for t in types:
        total = sum(tool.stock for tool in t.tools)
        available = sum(tool.stock for tool in t.tools if tool.activo)
        res.append({
            "category_id": t.id,
            "category_name": t.name,
            "available": available,
            "total": total
        })
    return res

# ToolType Routes (child of Category, e.g. "Martillo" inside "Manual")
@router.get("/types")
@router.get("/types/")
def list_types(db: Session = Depends(get_db)):
    types = db.query(ToolType).all()
    res = []
    for t in types:
        res.append({
            "id": t.id,
            "name": t.name,
            "category_id": t.category_id,
            "category_name": t.category.name if t.category else "Sin categoría"
        })
    return res

@router.post("/types")
@router.post("/types/")
def create_type(data: TypeCreate, db: Session = Depends(get_db)):
    # Check if category exists
    cat = db.query(Category).filter(Category.id == data.category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
        
    t = ToolType(name=data.name, category_id=data.category_id)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t

# Tool Routes (child of ToolType, e.g. "Martillo de peña 300g" inside "Martillo")
@router.get("/tools")
@router.get("/tools/")
def list_tools(db: Session = Depends(get_db)):
    tools = db.query(Tool).all()
    res = []
    for t in tools:
        res.append({
            "id": t.id,
            "name": t.name,
            "barcode": t.barcode,
            "stock": t.stock,
            "activo": t.activo,
            "type_id": t.type_id,
            "type_name": t.tool_type.name if t.tool_type else "Sin tipo",
            "category_name": t.tool_type.category.name if t.tool_type and t.tool_type.category else "Sin categoría"
        })
    return res

@router.post("/tools")
@router.post("/tools/")
def create_tool(data: ToolCreate, db: Session = Depends(get_db)):
    t_type = db.query(ToolType).filter(ToolType.id == data.type_id).first()
    if not t_type:
        raise HTTPException(status_code=404, detail="Tipo de herramienta no encontrado")
        
    barcode = data.barcode
    if not barcode:
        # Auto-generate a unique barcode
        prefix = t_type.name[:3].upper() if len(t_type.name) >= 3 else "TL"
        rand_num = "".join(random.choices("0123456789", k=6))
        barcode = f"BAR-{prefix}-{rand_num}"
        
    tool = Tool(name=data.name, type_id=data.type_id, barcode=barcode, stock=data.stock)
    db.add(tool)
    db.commit()
    db.refresh(tool)
    return tool

@router.delete("/tools/{tool_id}")
def delete_tool(tool_id: int, db: Session = Depends(get_db)):
    t = db.query(Tool).filter(Tool.id == tool_id).first()
    if t:
        db.delete(t)
        db.commit()
    return {"status": "ok"}

class AddStockRequest(BaseModel):
    quantity: int

@router.post("/tools/{tool_id}/add-stock")
@router.post("/tools/{tool_id}/add-stock/")
def add_tool_stock(tool_id: int, data: AddStockRequest, db: Session = Depends(get_db)):
    tool = db.query(Tool).filter(Tool.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Herramienta no encontrada")
    if data.quantity <= 0:
        raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a 0")
    tool.stock += data.quantity
    db.commit()
    db.refresh(tool)
    return tool

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.core.database import get_db
from app.core.security import get_current_user_db
from .models import Loan
from ..categories.models import Tool
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/loans", tags=["Pañol - Préstamos"])

class LoanCreate(BaseModel):
    user_id: int
    tool_id: int
    quantity: int = 1
    description_loan: Optional[str] = None

class ReturnRequest(BaseModel):
    description_return: Optional[str] = None
    quantity_returned: Optional[int] = None

@router.get("/")
def list_loans(status: Optional[str] = None, user_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(Loan)
    if status: query = query.filter(Loan.status == status)
    if user_id: query = query.filter(Loan.user_id == user_id)
    loans = query.order_by(Loan.borrowed_at.desc()).all()
    
    res = []
    for l in loans:
        # Format the Tool name like: "[Tipo > Categoría] NombreHerramienta"
        if l.tool:
            tipo = l.tool.tool_type.name if l.tool.tool_type else "Sin tipo"
            cat = l.tool.tool_type.category.name if l.tool.tool_type and l.tool.tool_type.category else "Sin categoría"
            tool_name = f"[{tipo} > {cat}] {l.tool.name}"
        else:
            tool_name = "Herramienta Desconocida"

        res.append({
            "id": l.id,
            "user_id": l.user_id,
            "user_name": l.user.name if l.user else "Desconocido",
            "panolero_id": l.panolero_id,
            "panolero_name": l.panolero.name if l.panolero else "Desconocido",
            "tool_id": l.tool_id,
            "tool_name": tool_name,
            "quantity": l.quantity,
            "description_loan": l.description_loan,
            "description_return": l.description_return,
            "borrowed_at": l.borrowed_at.strftime("%d/%m/%Y %H:%M:%S") if l.borrowed_at else "-",
            "returned_at": l.returned_at.strftime("%d/%m/%Y %H:%M:%S") if l.returned_at else "Pendiente",
            "status": l.status,
            "returned": l.status == "returned"
        })
    return res

@router.post("/")
def create_loan(data: LoanCreate, db: Session = Depends(get_db), user=Depends(get_current_user_db)):
    tool = db.query(Tool).filter(Tool.id == data.tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Herramienta no encontrada")
    if tool.stock < data.quantity:
        raise HTTPException(status_code=400, detail="Stock insuficiente")
        
    loan = Loan(
        user_id=data.user_id,
        panolero_id=user.id,
        tool_id=data.tool_id,
        quantity=data.quantity,
        description_loan=data.description_loan,
        status="active"
    )
    tool.stock -= data.quantity
    db.add(loan)
    db.commit()
    db.refresh(loan)
    return loan

@router.get("/active")
def list_active_loans(db: Session = Depends(get_db)):
    return list_loans(status="active", db=db)

@router.get("/active/by-professor")
def list_active_loans_by_professor(db: Session = Depends(get_db), user=Depends(get_current_user_db)):
    return list_loans(status="active", user_id=user.id, db=db)

class BarcodeReturnRequest(BaseModel):
    barcodes: list[str]
    description_return: Optional[str] = None

@router.post("/return-by-barcode")
def return_loans_by_barcode(data: BarcodeReturnRequest, db: Session = Depends(get_db), user=Depends(get_current_user_db)):
    from app.core.hook_registry import hook_registry
    data.barcodes = hook_registry.apply_filters("before_tool_return", data.barcodes, db=db)
    res = []
    for barcode in data.barcodes:
        tool = db.query(Tool).filter(Tool.barcode == barcode).first()
        if not tool:
            raise HTTPException(status_code=404, detail=f"Herramienta con código {barcode} no encontrada")
        # Find active loan for this tool
        loan = db.query(Loan).filter(Loan.tool_id == tool.id, Loan.status == "active").first()
        if not loan:
            raise HTTPException(status_code=400, detail=f"No hay préstamos activos para la herramienta {tool.name} (código: {barcode})")
        
        loan.status = "returned"
        loan.returned_at = datetime.utcnow()
        loan.description_return = data.description_return
        tool.stock += loan.quantity
        res.append(loan)
    db.commit()
    return {"status": "ok", "returned_loans_count": len(res)}

@router.post("/{loan_id}/remind")
def remind_return(loan_id: int, db: Session = Depends(get_db)):
    from app.modules.notifications.models import Notification
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Préstamo no encontrado")
    if loan.status != "active":
        raise HTTPException(status_code=400, detail="El préstamo no está activo")
        
    tool_name = loan.tool.name if loan.tool else "Herramienta"
    notif = Notification(
        user_id=loan.user_id,
        title="Recordatorio: Devolución Pendiente",
        message=f"Estimado/a docente, se solicita la devolución de la herramienta '{tool_name}' a la brevedad. ¡Gracias!",
        type="warning"
    )
    db.add(notif)
    db.commit()
    return {"status": "ok", "message": "Recordatorio enviado"}

@router.put("/{loan_id}/return")
@router.post("/{loan_id}/return")
def return_loan(loan_id: int, data: Optional[ReturnRequest] = None, db: Session = Depends(get_db), user=Depends(get_current_user_db)):
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Préstamo no encontrado")
    if loan.status != "active":
        raise HTTPException(status_code=400, detail="El préstamo ya fue devuelto")
        
    desc_return = data.description_return if data and data.description_return else None
    
    qty_returned = loan.quantity
    if data and data.quantity_returned is not None:
        qty_returned = max(0, min(data.quantity_returned, loan.quantity))
    
    tool = db.query(Tool).filter(Tool.id == loan.tool_id).first()
    if tool and qty_returned > 0:
        tool.stock += qty_returned

    if qty_returned >= loan.quantity:
        loan.status = "returned"
        loan.returned_at = datetime.utcnow()
    else:
        loan.quantity -= qty_returned
        if loan.quantity <= 0:
            loan.status = "returned"
            loan.returned_at = datetime.utcnow()

    if desc_return:
        loan.description_return = desc_return

    try:
        from app.modules.notifications.models import Notification
        tool_name = tool.name if tool else "herramienta"
        db.add(Notification(
            user_id=loan.user_id,
            title="Devolución Confirmada",
            message=f"Se ha registrado la devolución de {qty_returned} unidad(es) de '{tool_name}'. ¡Muchas gracias!",
            type="success"
        ))
    except Exception:
        pass
        
    db.commit()
    return {
        "id": loan.id,
        "status": loan.status,
        "quantity": loan.quantity,
        "quantity_returned": qty_returned,
        "description_return": loan.description_return
    }

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user_db
from .models import Order
from .items.models import OrderItem
from ..categories.models import Tool
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/orders", tags=["Pañol - Pedidos"])

class OrderItemCreate(BaseModel):
    tool_id: Optional[int] = None
    category_id: Optional[int] = None
    quantity: int = 1

class OrderCreate(BaseModel):
    items: list[OrderItemCreate]

class DeliverRequest(BaseModel):
    barcodes: Optional[list[str]] = None
    description_loan: Optional[str] = ""

class ManualOrderCreate(BaseModel):
    user_id: int
    category_id: int
    quantity: int = 1
    description_loan: Optional[str] = ""

def _format_order_dict(o: Order):
    items_res = []
    for item in o.items:
        items_res.append({
            "id": item.id,
            "tool_id": item.tool_id,
            "tool_name": item.tool.name if item.tool else "Herramienta Desconocida",
            "quantity": item.quantity,
            "category_id": item.tool.tool_type.id if item.tool and item.tool.tool_type else None,
            "category_name": item.tool.tool_type.name if item.tool and item.tool.tool_type else "Sin tipo"
        })
    return {
        "id": o.id,
        "user_id": o.user_id,
        "user_name": o.user.name if o.user else "Desconocido",
        "profesor": o.user.name if o.user else "Desconocido",
        "status": o.status,
        "created_at": o.created_at.isoformat() if hasattr(o, 'created_at') and o.created_at else None,
        "items": items_res
    }

@router.get("/")
def list_orders(status: Optional[str] = None, user_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(Order)
    if status: 
        query = query.filter(Order.status == status)
    if user_id: 
        query = query.filter(Order.user_id == user_id)
    orders = query.order_by(Order.id.desc()).all()
    return [_format_order_dict(o) for o in orders]

@router.get("/pending")
@router.get("/pending/")
def list_pending_orders(db: Session = Depends(get_db)):
    query = db.query(Order).filter(Order.status.in_(["pendiente", "preparado", "listo"]))
    orders = query.order_by(Order.id.desc()).all()
    return [_format_order_dict(o) for o in orders]

@router.get("/my")
@router.get("/my/")
def list_my_orders(db: Session = Depends(get_db), user=Depends(get_current_user_db)):
    return list_orders(user_id=user.id, db=db)

@router.post("")
@router.post("/")
def create_order(data: OrderCreate, db: Session = Depends(get_db), user=Depends(get_current_user_db)):
    order = Order(user_id=user.id, status="pendiente", created_at=datetime.utcnow())
    db.add(order)
    db.flush()
    total_tools = 0
    for item in data.items:
        tool_id = item.tool_id
        if item.category_id and not tool_id:
            tool = db.query(Tool).filter(Tool.type_id == item.category_id).first()
            if tool:
                tool_id = tool.id
            else:
                raise HTTPException(status_code=404, detail="No hay herramientas de esta categoría en stock")
        
        tool = db.query(Tool).filter(Tool.id == tool_id).first()
        if not tool: 
            raise HTTPException(status_code=404, detail=f"Herramienta no encontrada")
        db.add(OrderItem(order_id=order.id, tool_id=tool_id, quantity=item.quantity))
        total_tools += item.quantity

    from app.modules.notifications.models import Notification
    from app.modules.users.users.models import User
    from app.modules.roles.models import Role

    # 1. Notificación para el profesor solicitante
    db.add(Notification(
        user_id=user.id,
        title="Pedido al Pañol Registrado",
        message=f"Tu solicitud de {total_tools} herramientas ha sido enviada con éxito.",
        type="success"
    ))

    # 2. Notificación para los pañoleros y administradores
    try:
        staff_users = db.query(User).join(User.role).filter(Role.name.in_(["panolero", "panol", "admin", "superadmin"])).all()
        for staff in staff_users:
            if staff.id != user.id:
                db.add(Notification(
                    user_id=staff.id,
                    title="Nuevo Pedido al Pañol",
                    message=f"El docente {user.name} realizó un nuevo pedido de {total_tools} herramientas.",
                    type="info"
                ))
    except Exception as e:
        pass

    db.commit()
    db.refresh(order)
    return _format_order_dict(order)

@router.put("/{order_id}/prepare")
@router.post("/{order_id}/prepare")
def prepare_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order: 
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    order.status = "preparado"

    from app.modules.notifications.models import Notification

    # Notificación para el profesor/usuario que realizó el pedido
    try:
        db.add(Notification(
            user_id=order.user_id,
            title="¡Tu pedido está listo!",
            message=f"Tu pedido #{order.id} de herramientas ha sido PREPARADO por el pañolero. Ya lo puedes pasar a buscar por el pañol.",
            type="success"
        ))
    except Exception as e:
        pass

    db.commit()
    db.refresh(order)
    return _format_order_dict(order)

@router.put("/{order_id}/deliver")
@router.post("/{order_id}/deliver")
def deliver_order(order_id: int, data: Optional[DeliverRequest] = None, db: Session = Depends(get_db), user=Depends(get_current_user_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order: 
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    if order.status == "entregado":
        raise HTTPException(status_code=400, detail="Este pedido ya fue entregado")
        
    order.status = "entregado"
    
    from app.modules.panol.loans.models import Loan
    description = data.description_loan if data else ""
    if not description:
        description = f"Pedido #{order.id} entregado"

    if data and data.barcodes and len(data.barcodes) > 0:
        from app.core.hook_registry import hook_registry
        data.barcodes = hook_registry.apply_filters("before_tool_loan", data.barcodes, db=db, order=order)
        # Deliver by barcodes
        for barcode in data.barcodes:
            tool = db.query(Tool).filter(Tool.barcode == barcode).first()
            if not tool:
                raise HTTPException(status_code=404, detail=f"Herramienta con código {barcode} no encontrada")
            if tool.stock < 1:
                raise HTTPException(status_code=400, detail=f"Stock insuficiente para {tool.name}")
            tool.stock -= 1
            
            # Create Loan record
            loan = Loan(
                user_id=order.user_id,
                panolero_id=user.id,
                tool_id=tool.id,
                quantity=1,
                description_loan=description,
                status="active"
            )
            db.add(loan)
    else:
        # Deliver direct (non-barcode mode or no barcodes scanned)
        for item in order.items:
            tool = db.query(Tool).filter(Tool.id == item.tool_id).first()
            if tool:
                if tool.stock < item.quantity:
                    raise HTTPException(status_code=400, detail=f"Stock insuficiente para {tool.name}")
                tool.stock -= item.quantity
                
                # Create Loan record
                loan = Loan(
                    user_id=order.user_id,
                    panolero_id=user.id,
                    tool_id=item.tool_id,
                    quantity=item.quantity,
                    description_loan=description,
                    status="active"
                )
                db.add(loan)
            
    try:
        from app.modules.notifications.models import Notification
        db.add(Notification(
            user_id=order.user_id,
            title="Pedido Entregado",
            message=f"Las herramientas de tu pedido #{order.id} han sido entregadas.",
            type="info"
        ))
    except Exception:
        pass

    db.commit()
    db.refresh(order)
    return _format_order_dict(order)

@router.post("/manual")
def create_manual_order(data: ManualOrderCreate, db: Session = Depends(get_db), user=Depends(get_current_user_db)):
    # 1. Create order
    order = Order(user_id=data.user_id, status="entregado")
    db.add(order)
    db.flush()
    
    # 2. Find tool
    tool = db.query(Tool).filter(Tool.type_id == data.category_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="No hay herramientas de esta categoría en stock")
        
    if tool.stock < data.quantity:
        raise HTTPException(status_code=400, detail="Stock insuficiente")
        
    db.add(OrderItem(order_id=order.id, tool_id=tool.id, quantity=data.quantity))
    tool.stock -= data.quantity
    
    # 3. Create Loan
    from app.modules.panol.loans.models import Loan
    desc = data.description_loan if data.description_loan else "Pedido manual directo entregado"
    loan = Loan(
        user_id=data.user_id,
        panolero_id=user.id,
        tool_id=tool.id,
        quantity=data.quantity,
        description_loan=desc,
        status="active"
    )
    db.add(loan)
    db.commit()
    return {"status": "ok", "order_id": order.id}

@router.delete("/{order_id}")
def delete_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if order:
        db.delete(order)
        db.commit()
    return {"status": "ok"}

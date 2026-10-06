from sqlalchemy.orm import Session
from .models import User
from . import schemas

def get_users(db: Session):
    users = db.query(User).all()
    for u in users:
        if not u.dni:
            alum = db.query(Alumno).filter((Alumno.user_id == u.id) | ((Alumno.dni != None) & (Alumno.dni == u.dni))).first()
            if alum and alum.dni:
                u.dni = alum.dni
                db.commit()
    return users

def get_user_by_id(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

from app.modules.users.permissions.models import Permission
from app.modules.academico.alumnos.models import Alumno

from app.core.security import hash_password

def _sync_user_dashboards(db: Session, user: User, dashboards: list[str]):
    # Si el usuario es alumno, solo puede tener alumno y perfil
    if user.role and user.role.name == "alumno":
        dashboards = [d for d in dashboards if d in ("alumno", "perfil")]
        if not dashboards:
            dashboards = ["alumno"]

    user.permissions = [] # Clear existing
    for d in dashboards:
        perm_name = f"dashboard:{d}"
        perm = db.query(Permission).filter(Permission.name == perm_name).first()
        if not perm:
            perm = Permission(name=perm_name)
            db.add(perm)
        user.permissions.append(perm)

def create_user(db: Session, data: schemas.UserCreate):
    from app.core.supabase_sync import create_supabase_user
    from app.core.school_config import get_school_config
    from app.modules.schools.models import School
    cfg = get_school_config()
    school = db.query(School).filter((School.domain == cfg.domain) | (School.name == cfg.name)).first()
    if not school:
        school = db.query(School).first()
    active_school_id = school.id if school else 2
    
    from app.modules.users.roles.models import Role
    role = db.query(Role).filter(Role.id == data.role_id).first()
    role_name = role.name if role else "alumno"

    supabase_uid = None
    try:
        supabase_uid = create_supabase_user(data.email, data.password, name=data.name, school_id=active_school_id, role=role_name, dni=data.dni)
    except Exception as e:
        print(f"Supabase user creation failed (non-fatal): {e}")

    hashed_pwd = hash_password(data.password)
    user = User(
        name=data.name, 
        email=data.email, 
        password=hashed_pwd, 
        role_id=data.role_id, 
        supabase_uid=supabase_uid, 
        dni=data.dni,
        account_status="ACTIVA",
        must_change_password=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    if data.dashboards:
        _sync_user_dashboards(db, user, data.dashboards)
        db.commit()
        db.refresh(user)
        
    # Check if role is profesor
    from app.modules.users.roles.models import Role
    role = db.query(Role).filter(Role.id == data.role_id).first()
    if role and role.name == "profesor":
        from app.modules.profesores.models import Profesor
        profesor = None
        if data.dni:
            profesor = db.query(Profesor).filter(Profesor.dni == data.dni).first()
        if not profesor:
            parts = data.name.split(" ", 1)
            nombre = parts[0]
            apellido = parts[1] if len(parts) > 1 else "Docente"
            dni_val = data.dni or f"P-{user.id}"
            profesor = Profesor(
                dni=dni_val,
                nombre=nombre,
                apellido=apellido,
                tipo=data.tipo or "aula",
                user_id=user.id
            )
            db.add(profesor)
        else:
            profesor.user_id = user.id
            if data.tipo is not None:
                profesor.tipo = data.tipo
        db.commit()

    # Auto-create Alumno in Oficina de Alumnos ONLY if role is explicitly 'alumno'
    if role and role.name and role.name.lower() == "alumno":
        dni_val = data.dni or f"A-{user.id}"
        alumno = db.query(Alumno).filter(Alumno.user_id == user.id).first()
        if not alumno and data.dni:
            alumno = db.query(Alumno).filter(Alumno.dni == data.dni).first()
            
        parts = data.name.split(" ", 1)
        nombre = parts[0]
        apellido = parts[1] if len(parts) > 1 else "Estudiante"
        
        if not alumno:
            alumno = Alumno(
                dni=dni_val,
                nombre=nombre,
                apellido=apellido,
                user_id=user.id,
                estado="Activo"
            )
            db.add(alumno)
        else:
            alumno.user_id = user.id
            alumno.nombre = nombre
            alumno.apellido = apellido
            if data.dni:
                alumno.dni = data.dni
        db.commit()

    return user

def update_user(db: Session, user_id: int, data: schemas.UserUpdate):
    from app.core.supabase_sync import create_supabase_user, update_supabase_user
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    
    # Sincronizar cambios en Supabase
    if data.email is not None or data.password is not None:
        try:
            if user.supabase_uid:
                update_supabase_user(user.supabase_uid, email=data.email, password=data.password)
            else:
                from app.core.school_config import get_school_config
                from app.modules.schools.models import School
                cfg = get_school_config()
                school = db.query(School).filter(School.domain == cfg.domain).first()
                active_school_id = school.id if school else 1
                
                from app.modules.users.roles.models import Role
                target_role_id = data.role_id if data.role_id is not None else user.role_id
                role = db.query(Role).filter(Role.id == target_role_id).first()
                role_name = role.name if role else "alumno"
                
                supabase_uid = create_supabase_user(data.email or user.email, data.password or user.password, name=user.name, school_id=active_school_id, role=role_name)
                user.supabase_uid = supabase_uid
        except Exception as e:
            print(f"Error syncing user details to Supabase (non-fatal): {e}")

    if data.name is not None:
        user.name = data.name
    if data.email is not None:
        user.email = data.email
    if data.password is not None and data.password.strip():
        user.password = hash_password(data.password.strip())
    if data.role_id is not None:
        user.role_id = data.role_id
    if data.dni is not None:
        user.dni = data.dni
        
    if data.dashboards is not None:
        _sync_user_dashboards(db, user, data.dashboards)

    # Sync profesor profile on update
    from app.modules.users.roles.models import Role
    role = db.query(Role).filter(Role.id == user.role_id).first()
    if role and role.name == "profesor":
        from app.modules.profesores.models import Profesor
        profesor = db.query(Profesor).filter(Profesor.user_id == user.id).first()
        if not profesor:
            parts = user.name.split(" ", 1)
            nombre = parts[0]
            apellido = parts[1] if len(parts) > 1 else "Docente"
            dni_val = data.dni or user.dni or f"P-{user.id}"
            profesor = Profesor(
                dni=dni_val,
                nombre=nombre,
                apellido=apellido,
                tipo=data.tipo or "aula",
                user_id=user.id
            )
            db.add(profesor)
            db.commit()
        else:
            if data.tipo is not None:
                profesor.tipo = data.tipo

    # Auto-update Alumno on update_user
    if (role and role.name == "alumno") or data.dni is not None:
        dni_val = data.dni or user.dni or f"A-{user.id}"
        alumno = db.query(Alumno).filter(Alumno.user_id == user.id).first()
        if not alumno and dni_val:
            alumno = db.query(Alumno).filter(Alumno.dni == dni_val).first()
            
        parts = user.name.split(" ", 1)
        nombre = parts[0]
        apellido = parts[1] if len(parts) > 1 else "Estudiante"
        
        if not alumno:
            alumno = Alumno(
                dni=dni_val,
                nombre=nombre,
                apellido=apellido,
                user_id=user.id,
                estado="Activo"
            )
            db.add(alumno)
        else:
            alumno.user_id = user.id
            alumno.nombre = nombre
            alumno.apellido = apellido
            if data.dni is not None:
                alumno.dni = data.dni

    db.commit()
    db.refresh(user)
    return user

def delete_user(db: Session, user_id: int):
    from app.core.supabase_sync import delete_supabase_user
    user = get_user_by_id(db, user_id)
    if user:
        if user.supabase_uid:
            try:
                delete_supabase_user(user.supabase_uid)
            except Exception as e:
                print(f"Error deleting user from Supabase: {e}")
        db.delete(user)
        db.commit()
    return user

def change_role(db: Session, user_id: int, role_id: int):
    user = get_user_by_id(db, user_id)
    if user:
        user.role_id = role_id
        db.commit()
        db.refresh(user)
    return user

def login(db: Session, email: str, password: str):
    user = get_user_by_email(db, email)
    if user and user.password == password:
        return user
    return None

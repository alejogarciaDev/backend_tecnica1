from fastapi import HTTPException
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
    from app.modules.users.roles.models import Role

    # 1. Validar correo duplicado
    email_clean = data.email.strip().lower()
    exist_user = db.query(User).filter(User.email.ilike(email_clean)).first()
    if exist_user:
        raise HTTPException(status_code=400, detail=f"El correo '{data.email}' ya está registrado en el sistema.")

    # 2. Validar DNI duplicado si se ingresó
    if data.dni and str(data.dni).strip():
        dni_clean = str(data.dni).strip()
        exist_dni = db.query(User).filter(User.dni == dni_clean).first()
        if exist_dni:
            raise HTTPException(status_code=400, detail=f"El DNI '{dni_clean}' ya pertenece a otro usuario registrado.")

    # 3. Validar Rol
    role = db.query(Role).filter(Role.id == data.role_id).first()
    if not role:
        role = db.query(Role).filter(Role.name == "profesor").first() or db.query(Role).first()
        if not role:
            raise HTTPException(status_code=400, detail=f"El rol especificado (ID {data.role_id}) no existe en la base de datos.")
        data.role_id = role.id

    role_name = role.name if role else "alumno"

    cfg = get_school_config()
    school = db.query(School).filter((School.domain == cfg.domain) | (School.name == cfg.name)).first()
    if not school:
        school = db.query(School).first()
    active_school_id = school.id if school else 2

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
        school_id=active_school_id,
        supabase_uid=supabase_uid, 
        dni=data.dni,
        account_status="ACTIVA",
        must_change_password=False
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error al registrar usuario en la base de datos: {str(e)}")
    
    if data.dashboards:
        _sync_user_dashboards(db, user, data.dashboards)
        db.commit()
        db.refresh(user)
    else:
        # Asignar dashboards por defecto acordes al rol
        default_dash = ["perfil"]
        if role_name in ("admin", "superadmin"):
            default_dash = ["admin", "profesor", "panol", "ofalumnos", "biblioteca", "preceptor", "secretaria", "perfil"]
        elif role_name == "profesor":
            default_dash = ["profesor", "perfil"]
        elif role_name == "preceptor":
            default_dash = ["preceptor", "perfil"]
        elif role_name == "panol":
            default_dash = ["panol", "perfil"]
        elif role_name in ("bibliotecario", "biblioteca"):
            default_dash = ["biblioteca", "perfil"]
        elif role_name in ("secretaria", "oficina_alumnos"):
            default_dash = ["secretaria", "ofalumnos", "perfil"]
        elif role_name == "alumno":
            default_dash = ["alumno", "perfil"]
        _sync_user_dashboards(db, user, default_dash)
        db.commit()
        db.refresh(user)
        
    # Check if role is profesor
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
            exist_prof_dni = db.query(Profesor).filter(Profesor.dni == dni_val).first()
            if exist_prof_dni:
                exist_prof_dni.user_id = user.id
                profesor = exist_prof_dni
            else:
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
        try:
            db.commit()
        except Exception:
            db.rollback()

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
    from sqlalchemy import text
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    if user.supabase_uid:
        try:
            delete_supabase_user(user.supabase_uid)
        except Exception as e:
            print(f"Error deleting user from Supabase: {e}")

    try:
        uid = user.id
        # 1. Limpiar notificaciones, permisos y logs del usuario
        db.execute(text("DELETE FROM notifications WHERE user_id = :uid"), {"uid": uid})
        db.execute(text("DELETE FROM user_permissions WHERE user_id = :uid"), {"uid": uid})
        db.execute(text("DELETE FROM audit_logs WHERE user_id = :uid"), {"uid": uid})
        db.execute(text("DELETE FROM olimpiadas_inscripciones WHERE user_id = :uid"), {"uid": uid})
        
        # 2. Desvincular de Cursos y Roles
        db.execute(text("UPDATE cursos SET preceptor_principal_id = NULL WHERE preceptor_principal_id = :uid"), {"uid": uid})
        db.execute(text("UPDATE profesores SET user_id = NULL WHERE user_id = :uid"), {"uid": uid})
        db.execute(text("UPDATE alumnos SET user_id = NULL WHERE user_id = :uid"), {"uid": uid})
        
        # 3. Desvincular de Pañol y Biblioteca
        db.execute(text("UPDATE loans SET panolero_id = NULL WHERE panolero_id = :uid"), {"uid": uid})
        db.execute(text("DELETE FROM orders WHERE user_id = :uid"), {"uid": uid})
        db.execute(text("DELETE FROM loans WHERE user_id = :uid"), {"uid": uid})
        db.execute(text("DELETE FROM prestamos_libros WHERE user_id = :uid"), {"uid": uid})
        
        # 4. Desvincular de registros académicos y campus
        db.execute(text("UPDATE asistencias SET registrado_por_id = NULL WHERE registrado_por_id = :uid"), {"uid": uid})
        db.execute(text("UPDATE calificaciones_academicas SET profesor_id = NULL WHERE profesor_id = :uid"), {"uid": uid})
        db.execute(text("UPDATE calificaciones_academicas SET aprobado_por_id = NULL WHERE aprobado_por_id = :uid"), {"uid": uid})
        db.execute(text("UPDATE boletines_publicados SET publicado_por_id = NULL WHERE publicado_por_id = :uid"), {"uid": uid})
        
        # 5. Limpiar registros de campus/comunicados
        db.execute(text("DELETE FROM comunicados_comentarios WHERE autor_id = :uid"), {"uid": uid})
        db.execute(text("DELETE FROM comunicados WHERE autor_id = :uid"), {"uid": uid})
        db.execute(text("DELETE FROM entregas_comentarios WHERE autor_id = :uid"), {"uid": uid})
        db.execute(text("DELETE FROM documentos_compartidos WHERE creador_id = :uid"), {"uid": uid})
        db.execute(text("DELETE FROM evaluaciones WHERE profesor_id = :uid"), {"uid": uid})
        db.execute(text("DELETE FROM tareas WHERE profesor_id = :uid"), {"uid": uid})
        db.execute(text("DELETE FROM materiales_estudio WHERE profesor_id = :uid"), {"uid": uid})
        db.execute(text("DELETE FROM calificaciones WHERE profesor_id = :uid"), {"uid": uid})
        
        db.flush()

        # 6. Eliminar usuario
        db.delete(user)
        db.commit()
        return user

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"No se pudo eliminar el usuario: {str(e)}")

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

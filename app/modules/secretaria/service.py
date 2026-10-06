from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from fastapi import HTTPException
from app.modules.academico.alumnos.models import Alumno, AlumnoHistorial
from app.modules.users.users.models import User
from app.modules.users.roles.models import Role
from app.modules.audit.models import AuditLog
from app.modules.audit.service import log_action
from app.core.security import hash_password, generate_temp_password
from . import schemas

def get_or_create_alumno_role(db: Session) -> Role:
    role = db.query(Role).filter(Role.name == "alumno").first()
    if not role:
        role = Role(name="alumno")
        db.add(role)
        db.commit()
        db.refresh(role)
    return role

def pre_registrar_alumno(db: Session, data: schemas.AlumnoPreRegistro, actor) -> dict:
    dni_clean = "".join(filter(str.isdigit, str(data.dni))).strip()
    if not dni_clean:
        raise HTTPException(status_code=400, detail="El DNI no puede estar vacío.")

    # Verificar si el alumno ya existe por DNI
    existing_alumno = db.query(Alumno).filter(Alumno.dni == dni_clean).first()
    if existing_alumno:
        raise HTTPException(status_code=409, detail=f"Ya existe un alumno registrado con el DNI {dni_clean}.")

    # Generar contraseña temporal segura
    temp_password = generate_temp_password(data.fecha_nacimiento, dni_clean)
    hashed_password = hash_password(temp_password)

    # Rol del alumno: ESTRICTAMENTE ALUMNO
    alumno_role = get_or_create_alumno_role(db)

    # Determinar school_id
    school_id = getattr(actor, "school_id", None)

    # Crear o enlazar usuario
    user_email = f"{dni_clean}@mitecnica.edu.ar"
    existing_user = db.query(User).filter(or_(User.dni == dni_clean, User.email == user_email)).first()
    if existing_user:
        # Reutilizar usuario pero garantizar rol y flags
        user = existing_user
        user.name = f"{data.nombre.strip()} {data.apellido.strip()}"
        user.password = hashed_password
        user.role_id = alumno_role.id
        user.dni = dni_clean
        user.fecha_nacimiento = data.fecha_nacimiento
        user.must_change_password = True
        user.account_status = "SIN_ACTIVAR"
        user.identity_status = "NO_VERIFICADA"
    else:
        user = User(
            name=f"{data.nombre.strip()} {data.apellido.strip()}",
            email=user_email,
            password=hashed_password,
            role_id=alumno_role.id,
            dni=dni_clean,
            fecha_nacimiento=data.fecha_nacimiento,
            school_id=school_id,
            must_change_password=True,
            account_status="SIN_ACTIVAR",
            identity_status="NO_VERIFICADA",
            accepted_terms=False
        )
        db.add(user)
        db.flush()

    # Crear registro Alumno con los 3 estados independientes
    alumno = Alumno(
        dni=dni_clean,
        nombre=data.nombre.strip(),
        apellido=data.apellido.strip(),
        fecha_nacimiento=data.fecha_nacimiento,
        curso=data.curso.strip(),
        division=data.division.strip(),
        turno=data.turno.strip(),
        estado_academico=data.estado_academico or "REGULAR",
        estado_cuenta="SIN_ACTIVAR",
        estado_identidad="NO_VERIFICADA",
        telefono=data.telefono,
        folio=data.folio,
        legajo=data.legajo,
        grupo_taller=data.grupo_taller,
        user_id=user.id,
        school_id=school_id,
        estado="Activo"
    )
    db.add(alumno)
    db.flush()

    # Registrar historial académico inicial
    historial = AlumnoHistorial(
        alumno_id=alumno.id,
        anio="2026",
        curso=f"{data.curso} {data.division}".strip(),
        repitio=False,
        observaciones=f"Pre-registro Secretaría - Turno {data.turno}"
    )
    db.add(historial)
    db.commit()
    db.refresh(alumno)

    # Registrar en auditoría
    log_action(
        db=db,
        action="CREAR_ALUMNO",
        actor=actor,
        target_id=alumno.id,
        target_dni=alumno.dni,
        target_name=f"{alumno.nombre} {alumno.apellido}",
        details=f"Pre-registro: Curso {data.curso}° {data.division}°, Turno {data.turno}, Estado Académico: {alumno.estado_academico}",
        status="EXITOSO",
        school_id=school_id
    )

    return {
        "id": alumno.id,
        "dni": alumno.dni,
        "nombre": alumno.nombre,
        "apellido": alumno.apellido,
        "fecha_nacimiento": alumno.fecha_nacimiento,
        "curso": alumno.curso,
        "division": alumno.division,
        "turno": alumno.turno,
        "grupo_taller": alumno.grupo_taller,
        "folio": alumno.folio,
        "legajo": alumno.legajo,
        "telefono": alumno.telefono,
        "estado_academico": alumno.estado_academico,
        "estado_cuenta": alumno.estado_cuenta,
        "estado_identidad": alumno.estado_identidad,
        "user_id": alumno.user_id,
        "school_id": alumno.school_id,
        "temp_password": temp_password
    }

def get_alumnos_secretaria(
    db: Session,
    q: str = None,
    curso: str = None,
    division: str = None,
    turno: str = None,
    estado_academico: str = None,
    estado_cuenta: str = None,
    school_id: int = None
):
    query = db.query(Alumno)
    if school_id:
        query = query.filter(or_(Alumno.school_id == school_id, Alumno.school_id == None))

    if q:
        q_term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Alumno.dni.ilike(q_term),
                Alumno.nombre.ilike(q_term),
                Alumno.apellido.ilike(q_term),
                Alumno.legajo.ilike(q_term)
            )
        )

    if curso:
        query = query.filter(Alumno.curso == curso)
    if division:
        query = query.filter(Alumno.division == division)
    if turno:
        query = query.filter(Alumno.turno == turno)
    if estado_academico:
        query = query.filter(Alumno.estado_academico == estado_academico)
    if estado_cuenta:
        query = query.filter(Alumno.estado_cuenta == estado_cuenta)

    alumnos = query.order_by(Alumno.apellido.asc(), Alumno.nombre.asc()).all()
    results = []
    for a in alumnos:
        # Sincronizar estado de cuenta desde User si existe
        u = a.user
        est_cuenta = u.account_status if (u and u.account_status) else (a.estado_cuenta or "SIN_ACTIVAR")
        est_identidad = u.identity_status if (u and u.identity_status) else (a.estado_identidad or "NO_VERIFICADA")
        est_acad = a.estado_academico or "REGULAR"

        results.append({
            "id": a.id,
            "dni": a.dni,
            "nombre": a.nombre,
            "apellido": a.apellido,
            "fecha_nacimiento": a.fecha_nacimiento or (u.fecha_nacimiento if u else None),
            "curso": a.curso,
            "division": a.division,
            "turno": a.turno,
            "grupo_taller": a.grupo_taller,
            "folio": a.folio,
            "legajo": a.legajo,
            "telefono": a.telefono,
            "estado_academico": est_acad,
            "estado_cuenta": est_cuenta,
            "estado_identidad": est_identidad,
            "user_id": a.user_id,
            "school_id": a.school_id
        })
    return results

def get_alumno_by_id(db: Session, alumno_id: int):
    alumno = db.query(Alumno).filter(Alumno.id == alumno_id).first()
    if not alumno:
        raise HTTPException(status_code=404, detail="Alumno no encontrado")
    
    u = alumno.user
    hist = []
    for h in (alumno.historial or []):
        hist.append({
            "id": h.id,
            "anio": h.anio,
            "curso": h.curso,
            "repitio": h.repitio,
            "observaciones": h.observaciones
        })

    audit_logs = db.query(AuditLog).filter(
        or_(AuditLog.target_id == alumno.id, AuditLog.target_dni == alumno.dni)
    ).order_by(AuditLog.created_at.desc()).limit(20).all()

    audit_items = []
    for log in audit_logs:
        audit_items.append({
            "id": log.id,
            "action": log.action,
            "user_name": log.user_name,
            "user_email": log.user_email,
            "details": log.details,
            "status": log.status,
            "created_at": log.created_at
        })

    return {
        "id": alumno.id,
        "dni": alumno.dni,
        "nombre": alumno.nombre,
        "apellido": alumno.apellido,
        "fecha_nacimiento": alumno.fecha_nacimiento or (u.fecha_nacimiento if u else None),
        "curso": alumno.curso,
        "division": alumno.division,
        "turno": alumno.turno,
        "grupo_taller": alumno.grupo_taller,
        "folio": alumno.folio,
        "legajo": alumno.legajo,
        "telefono": alumno.telefono,
        "estado_academico": alumno.estado_academico or "REGULAR",
        "estado_cuenta": u.account_status if (u and u.account_status) else (alumno.estado_cuenta or "SIN_ACTIVAR"),
        "estado_identidad": u.identity_status if (u and u.identity_status) else (alumno.estado_identidad or "NO_VERIFICADA"),
        "user_id": alumno.user_id,
        "school_id": alumno.school_id,
        "historial": hist,
        "auditoria": audit_items
    }

def update_alumno(db: Session, alumno_id: int, data: schemas.AlumnoUpdateSecretaria, actor):
    alumno = db.query(Alumno).filter(Alumno.id == alumno_id).first()
    if not alumno:
        raise HTTPException(status_code=404, detail="Alumno no encontrado")

    cambios = []
    if data.nombre is not None and data.nombre != alumno.nombre:
        cambios.append(f"nombre: {alumno.nombre} -> {data.nombre}")
        alumno.nombre = data.nombre.strip()
    if data.apellido is not None and data.apellido != alumno.apellido:
        cambios.append(f"apellido: {alumno.apellido} -> {data.apellido}")
        alumno.apellido = data.apellido.strip()
    if data.fecha_nacimiento is not None and data.fecha_nacimiento != alumno.fecha_nacimiento:
        cambios.append(f"fecha_nac: {alumno.fecha_nacimiento} -> {data.fecha_nacimiento}")
        alumno.fecha_nacimiento = data.fecha_nacimiento
    if data.curso is not None and data.curso != alumno.curso:
        cambios.append(f"curso: {alumno.curso} -> {data.curso}")
        alumno.curso = data.curso
    if data.division is not None and data.division != alumno.division:
        cambios.append(f"division: {alumno.division} -> {data.division}")
        alumno.division = data.division
    if data.turno is not None and data.turno != alumno.turno:
        cambios.append(f"turno: {alumno.turno} -> {data.turno}")
        alumno.turno = data.turno
    if data.telefono is not None:
        alumno.telefono = data.telefono
    if data.folio is not None:
        alumno.folio = data.folio
    if data.legajo is not None:
        alumno.legajo = data.legajo
    if data.grupo_taller is not None:
        alumno.grupo_taller = data.grupo_taller

    # Sincronizar con User vinculado si existe
    if alumno.user:
        alumno.user.name = f"{alumno.nombre} {alumno.apellido}"
        if alumno.fecha_nacimiento:
            alumno.user.fecha_nacimiento = alumno.fecha_nacimiento

    db.commit()
    db.refresh(alumno)

    if cambios:
        log_action(
            db=db,
            action="EDITAR_ALUMNO",
            actor=actor,
            target_id=alumno.id,
            target_dni=alumno.dni,
            target_name=f"{alumno.nombre} {alumno.apellido}",
            details="; ".join(cambios),
            status="EXITOSO",
            school_id=alumno.school_id
        )

    return get_alumno_by_id(db, alumno.id)

def update_estado_academico(db: Session, alumno_id: int, data: schemas.EstadoAcademicoUpdate, actor):
    alumno = db.query(Alumno).filter(Alumno.id == alumno_id).first()
    if not alumno:
        raise HTTPException(status_code=404, detail="Alumno no encontrado")

    estado_anterior = alumno.estado_academico or "REGULAR"
    nuevo_estado = data.estado_academico.upper().strip()

    validos = ("REGULAR", "INACTIVO", "EGRESADO", "DADO_DE_BAJA")
    if nuevo_estado not in validos:
        raise HTTPException(status_code=400, detail=f"Estado inválido. Valores permitidos: {', '.join(validos)}")

    alumno.estado_academico = nuevo_estado
    
    # Determinar acción para auditoría
    if nuevo_estado == "DADO_DE_BAJA":
        action = "DAR_DE_BAJA"
    elif nuevo_estado == "EGRESADO":
        action = "REGISTRAR_EGRESADO"
    elif estado_anterior in ("DADO_DE_BAJA", "INACTIVO") and nuevo_estado == "REGULAR":
        action = "REACTIVAR_ALUMNO"
    else:
        action = "CAMBIAR_ESTADO"

    db.commit()
    db.refresh(alumno)

    log_action(
        db=db,
        action=action,
        actor=actor,
        target_id=alumno.id,
        target_dni=alumno.dni,
        target_name=f"{alumno.nombre} {alumno.apellido}",
        details=f"Estado académico cambiado de {estado_anterior} a {nuevo_estado}. Motivo: {data.motivo or 'No especificado'}",
        status="EXITOSO",
        school_id=alumno.school_id
    )

    return {"status": "ok", "estado_academico": alumno.estado_academico, "accion": action}

def update_bloqueo_cuenta(db: Session, alumno_id: int, data: schemas.BloqueoCuentaUpdate, actor):
    alumno = db.query(Alumno).filter(Alumno.id == alumno_id).first()
    if not alumno:
        raise HTTPException(status_code=404, detail="Alumno no encontrado")

    user = alumno.user
    if not user:
        raise HTTPException(status_code=400, detail="El alumno no posee una cuenta de usuario vinculada.")

    if data.bloqueada:
        user.account_status = "BLOQUEADA"
        alumno.estado_cuenta = "BLOQUEADA"
        action = "BLOQUEAR_CUENTA"
    else:
        # Desbloquear: Si tenía must_change_password=True vuelve a SIN_ACTIVAR o ACTIVACION_PENDIENTE, sino ACTIVA
        user.account_status = "ACTIVA" if not user.must_change_password else "SIN_ACTIVAR"
        alumno.estado_cuenta = user.account_status
        action = "DESBLOQUEAR_CUENTA"

    db.commit()
    db.refresh(user)
    db.refresh(alumno)

    log_action(
        db=db,
        action=action,
        actor=actor,
        target_id=alumno.id,
        target_dni=alumno.dni,
        target_name=f"{alumno.nombre} {alumno.apellido}",
        details=f"Cuenta marcada como {user.account_status}. Motivo: {data.motivo or 'No especificado'}",
        status="EXITOSO",
        school_id=alumno.school_id
    )

    return {"status": "ok", "estado_cuenta": user.account_status, "bloqueada": data.bloqueada}

def reset_password_alumno(db: Session, alumno_id: int, data: schemas.ResetPasswordRequest, actor):
    alumno = db.query(Alumno).filter(Alumno.id == alumno_id).first()
    if not alumno:
        raise HTTPException(status_code=404, detail="Alumno no encontrado")

    user = alumno.user
    if not user:
        # Si por alguna razón no tiene usuario, crearlo
        alumno_role = get_or_create_alumno_role(db)
        user_email = f"{alumno.dni}@mitecnica.edu.ar"
        user = User(
            name=f"{alumno.nombre} {alumno.apellido}",
            email=user_email,
            password="",
            role_id=alumno_role.id,
            dni=alumno.dni,
            fecha_nacimiento=alumno.fecha_nacimiento,
            school_id=alumno.school_id,
            account_status="SIN_ACTIVAR",
            identity_status="NO_VERIFICADA"
        )
        db.add(user)
        db.flush()
        alumno.user_id = user.id

    # Si se pasó contraseña manual, usarla; si no, calcular la fórmula temporal
    if data.new_password and data.new_password.strip():
        plain_pwd = data.new_password.strip()
    else:
        fn = alumno.fecha_nacimiento or user.fecha_nacimiento or "01/01/2010"
        plain_pwd = generate_temp_password(fn, alumno.dni)

    user.password = hash_password(plain_pwd)
    user.must_change_password = data.must_change_password
    if data.must_change_password:
        user.account_status = "SIN_ACTIVAR"
        alumno.estado_cuenta = "SIN_ACTIVAR"
    else:
        user.account_status = "ACTIVA"
        alumno.estado_cuenta = "ACTIVA"

    db.commit()
    db.refresh(user)
    db.refresh(alumno)

    log_action(
        db=db,
        action="REINICIAR_CONTRASENA_ALUMNO",
        actor=actor,
        target_id=alumno.id,
        target_dni=alumno.dni,
        target_name=f"{alumno.nombre} {alumno.apellido}",
        details=f"Contraseña reiniciada por Secretaría. must_change_password={data.must_change_password}",
        status="EXITOSO",
        school_id=alumno.school_id
    )

    return {
        "status": "ok",
        "message": "Contraseña reiniciada con éxito.",
        "plain_password": plain_pwd,
        "must_change_password": user.must_change_password,
        "estado_cuenta": user.account_status
    }

def get_metricas_secretaria(db: Session, school_id: int = None) -> schemas.SecretariaMetricas:
    query = db.query(Alumno)
    if school_id:
        query = query.filter(or_(Alumno.school_id == school_id, Alumno.school_id == None))

    total = query.count()
    regulares = query.filter(Alumno.estado_academico == "REGULAR").count()
    inactivos = query.filter(Alumno.estado_academico == "INACTIVO").count()
    egresados = query.filter(Alumno.estado_academico == "EGRESADO").count()
    dados_de_baja = query.filter(Alumno.estado_academico == "DADO_DE_BAJA").count()

    # Cuentas
    cuentas_activas = db.query(Alumno).join(User, Alumno.user_id == User.id).filter(User.account_status == "ACTIVA").count()
    cuentas_sin_activar = db.query(Alumno).join(User, Alumno.user_id == User.id).filter(User.account_status.in_(["SIN_ACTIVAR", "ACTIVACION_PENDIENTE"])).count()
    cuentas_bloqueadas = db.query(Alumno).join(User, Alumno.user_id == User.id).filter(User.account_status == "BLOQUEADA").count()

    return schemas.SecretariaMetricas(
        total_alumnos=total,
        regulares=regulares,
        inactivos=inactivos,
        egresados=egresados,
        dados_de_baja=dados_de_baja,
        cuentas_activas=cuentas_activas,
        cuentas_sin_activar=cuentas_sin_activar,
        cuentas_bloqueadas=cuentas_bloqueadas
    )

def get_auditoria_secretaria(db: Session, limit: int = 100, school_id: int = None):
    query = db.query(AuditLog)
    if school_id:
        query = query.filter(or_(AuditLog.school_id == school_id, AuditLog.school_id == None))
    return query.order_by(AuditLog.created_at.desc()).limit(limit).all()

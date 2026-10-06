import os
import sys
import argparse
import getpass
import yaml
from pathlib import Path

# Add backend, project root, and container paths to sys.path to enable imports
backend_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(backend_dir))
for p in [backend_dir, project_root, "/app", "/"]:
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

def validate_yaml(config_path: str):
    """Basic validation of the school configuration YAML file."""
    if not os.path.exists(config_path):
        print(f"Error: El archivo de configuración '{config_path}' no existe.")
        sys.exit(1)
        
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"Error parseando YAML: {e}")
        sys.exit(1)
        
    if not data or "school" not in data:
        print("Error: El archivo YAML debe contener la sección principal 'school'.")
        sys.exit(1)
        
    school = data["school"]
    required_fields = ["name", "domain", "roles"]
    missing = [field for field in required_fields if field not in school]
    if missing:
        print(f"Error: Falta(n) el/los campo(s) obligatorio(s) en 'school': {', '.join(missing)}")
        sys.exit(1)
        
    return data

def main():
    default_config = os.getenv("SCHOOL_CONFIG_PATH", "config/school.default.yml")
    parser.add_argument("config_path", nargs="?", default=default_config, help="Ruta al archivo YAML de configuración de la escuela (ej: config/school.default.yml)")
    parser.add_argument("--admin-name", help="Nombre del primer superadministrador", default=os.getenv("ADMIN_NAME"))
    parser.add_argument("--admin-email", help="Email del primer superadministrador", default=os.getenv("ADMIN_EMAIL"))
    parser.add_argument("--admin-password", help="Contraseña del primer superadministrador", default=os.getenv("ADMIN_PASSWORD"))
    parser.add_argument("--non-interactive", action="store_true", help="Deshabilitar prompts interactivos")
    
    args = parser.parse_args()
    
    # Resolve the config path relative to current working directory or absolute
    config_abs_path = os.path.abspath(args.config_path)
    validate_yaml(config_abs_path)
    
    # Configurar la variable de entorno para que el core la detecte y cargue
    os.environ["SCHOOL_CONFIG_PATH"] = config_abs_path
    
    # Importar app core después de setear la variable de entorno
    from app.core.school_config import get_school_config
    cfg = get_school_config()
    
    print(f"\n==========================================")
    print(f" Inicializando Escuela: {cfg.name}")
    print(f" Dominio: {cfg.domain}")
    print(f"==========================================\n")
    
    # Cargar dinámicamente los plugins activos para registrar sus modelos en metadata
    from fastapi import FastAPI
    from app.core.plugin_loader import plugin_loader
    dummy_app = FastAPI()
    plugin_loader.load_active_plugins(dummy_app)
    
    # Inicializar Base de Datos (Core + Plugins)
    from app.core.database import Base, engine, SessionLocal
    # Cargar todos los modelos del Core
    import app.core.models  # force imports of core models
    
    print("Creando tablas en la base de datos...")
    Base.metadata.create_all(bind=engine)
    print("Tablas creadas correctamente.")
    
    db = SessionLocal()
    try:
        # Asegurar que la escuela esté registrada en la tabla schools
        from app.modules.schools.models import School
        school = db.query(School).filter((School.domain == cfg.domain) | (School.name == cfg.name)).first()
        if not school:
            print(f"Registrando escuela '{cfg.name}' en la base de datos...")
            school = School(
                name=cfg.name,
                domain=cfg.domain or "localhost",
                school_type="Tecnica",
                primary_color=getattr(cfg, "primary_color", "#1a3a5c"),
                secondary_color=getattr(cfg, "secondary_color", "#e67e22"),
                logo_url=getattr(cfg, "logo", None),
                is_active=True
            )
            db.add(school)
            db.commit()
            db.refresh(school)
            print(f"Escuela registrada con ID: {school.id}")
        else:
            print(f"Escuela existente encontrada (ID: {school.id}): {school.name}")

        # Aprovisionar Roles y Permisos
        print("Registrando roles y permisos...")
        
        # 1. Crear todos los permisos existentes en la configuración
        permission_set = set()
        for role_def in cfg.roles:
            perms = role_def.get("permissions", [])
            if isinstance(perms, list):
                for p in perms:
                    if p != "*":
                        permission_set.add(p)
            elif isinstance(perms, str) and perms != "*":
                permission_set.add(perms)
        
        from app.modules.users.permissions.models import Permission as DBPermission
        perm_objects = {}
        for p_name in sorted(permission_set):
            p = db.query(DBPermission).filter(DBPermission.name == p_name).first()
            if not p:
                p = DBPermission(name=p_name)
                db.add(p)
                db.flush()
            perm_objects[p_name] = p
            
        # 2. Crear roles y asociar permisos
        from app.modules.users.roles.models import Role as DBRole
        role_map = {}
        for role_def in cfg.roles:
            role_name = role_def["name"]
            r = db.query(DBRole).filter(DBRole.name == role_name).first()
            if not r:
                r = DBRole(name=role_name)
                db.add(r)
                db.flush()
            role_map[role_name] = r
            
            # Asociar permisos
            perms = role_def.get("permissions", [])
            if perms == ["*"] or perms == "*":
                r.permissions = list(perm_objects.values()) if perm_objects else []
            else:
                current_perms = []
                for p_name in perms:
                    if p_name in perm_objects:
                        current_perms.append(perm_objects[p_name])
                r.permissions = current_perms
                
        db.commit()
        print("Roles y permisos registrados con éxito.")
        
        # Verificar si ya existe un administrador/superadmin
        from app.modules.users.users.models import User as DBUser
        existing_admins = db.query(DBUser).join(DBRole).filter(DBRole.name.in_(["superadmin", "admin"])).count()
        
        if existing_admins > 0:
            print("\n[INFO] Ya existe un usuario administrador en esta base de datos. Saltando creación de superadmin.")
        else:
            # Solicitar credenciales
            admin_name = args.admin_name
            admin_email = args.admin_email
            admin_password = args.admin_password
            
            if not args.non_interactive:
                if not admin_name:
                    admin_name = input("Nombre del Superadministrador [Super Admin]: ").strip() or "Super Admin"
                if not admin_email:
                    admin_email = input(f"Email del Superadministrador [admin@{cfg.domain}]: ").strip() or f"admin@{cfg.domain}"
                if not admin_password:
                    while True:
                        admin_password = getpass.getpass("Contraseña del Superadministrador: ").strip()
                        if not admin_password:
                            print("Error: La contraseña no puede estar vacía.")
                            continue
                        confirm = getpass.getpass("Confirmar contraseña: ").strip()
                        if admin_password != confirm:
                            print("Error: Las contraseñas no coinciden.")
                            continue
                        break
            else:
                # Valores por defecto en modo no interactivo si no se suministran
                if not admin_name:
                    admin_name = os.getenv("ADMIN_NAME", "Super Admin")
                if not admin_email:
                    admin_email = os.getenv("ADMIN_EMAIL", f"admin@{cfg.domain or 'colegio.local'}")
                if not admin_password:
                    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
            
            # Buscar el rol adecuado para el superadministrador
            admin_role = role_map.get("superadmin") or role_map.get("admin")
            if not admin_role:
                # Si no está en el mapa, tomar el primero con permisos completos o cualquiera
                admin_role = list(role_map.values())[0]
                
            from app.modules.users.users.schemas import UserCreate
            from app.modules.users.users.service import create_user
            
            new_admin = UserCreate(
                name=admin_name,
                email=admin_email,
                password=admin_password,
                role_id=admin_role.id
            )
            create_user(db, new_admin)
            print(f"\n[ÉXITO] Superadmin creado correctamente.")
            print(f"  - Nombre: {admin_name}")
            print(f"  - Email:  {admin_email}")
            print(f"  - Rol:    {admin_role.name}")
            
        print("\n==========================================")
        print(" APROVISIONAMIENTO FINALIZADO CON ÉXITO")
        print(f" Base de Datos: {engine.url}")
        print(" Plugins cargados y activos:")
        for plugin_id, meta in plugin_loader.loaded_plugins.items():
            print(f"   - {meta.get('name', plugin_id)} (v{meta.get('version', '1.0.0')})")
        print("==========================================\n")
        
    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] Error durante el aprovisionamiento de la escuela: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()

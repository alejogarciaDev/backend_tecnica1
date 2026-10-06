# Backend de Colegio (SIGEN) - Contenedor Docker Listo para Producción

Este paquete contiene el **backend completo para un colegio nuevo**, configurado desde cero, **completamente limpio (sin alumnos, profesores ni datos ficticios)** y listo para desplegar en tu servidor.

---

##  ¿Qué hace automáticamente al arrancar?

1. **Espera la base de datos** (PostgreSQL) hasta que esté lista y saludable.
2. **Crea todas las tablas** del sistema automáticamente (modelos académicos, secretaría, pañol, campus, usuarios, etc.).
3. **Registra la escuela** con su configuración en la base de datos.
4. **Aprovisiona roles y permisos** del sistema (`superadmin`, `admin`, `profesor`, `alumno`, `preceptor`, `secretaria`, etc.).
5. **Crea el usuario Super Administrador** con las credenciales definidas en `.env`.
6. **Inicia el servidor API** (FastAPI / Uvicorn) en el puerto configurado.

La base de datos queda **100% limpia**, lista para que cargues tus materias, cursos y usuarios reales.

---

## 📁 Estructura del Paquete

```text
backend_colegio_docker/
├── app/                      # Código fuente de la API (FastAPI)
├── config/                   # Configuración del colegio
│   └── school.default.yml    # Nombre, colores, módulos activos y roles
├── bootstrap_school.py       # Inicializador de la base de datos y superadmin
├── entrypoint.sh             # Script de arranque automatizado
├── Dockerfile                # Imagen Docker optimizada (Python 3.11-slim)
├── docker-compose.yml        # Orquestación de Backend + PostgreSQL
├── .dockerignore             # Exclusiones para build liviano y limpio
├── .env                      # Variables de configuración
├── .env.example              # Plantilla de variables
└── requirements.txt          # Dependencias de Python
```

---

## 🚀 Pasos para Desplegar en tu Servidor

### 1. Subir esta carpeta al servidor

Puedes transferir la carpeta `backend_colegio_docker` a tu servidor por cualquiera de estos métodos:

#### Opción A: Comprimir y subir por SCP / SFTP
En tu máquina local:
```bash
# Comprimir la carpeta (en Linux/Mac o Git Bash)
tar -czvf colegio_backend.tar.gz backend_colegio_docker/

# Subir a tu servidor
scp colegio_backend.tar.gz usuario@TU_IP_O_DOMINIO:/opt/
```

En el servidor:
```bash
cd /opt
tar -xzvf colegio_backend.tar.gz
cd backend_colegio_docker
```

#### Opción B: Mediante Git
Si tienes tu repositorio clonado en el servidor:
```bash
git pull origin main
cd backend_colegio_docker
```

---

### 2. Configurar las variables en `.env`

Abre el archivo `.env` en el servidor y ajusta tus credenciales y puertos:

```bash
nano .env
```

Contenido de ejemplo:
```env
# Puerto del backend en el servidor
PORT=8001

# Credenciales del Super Administrador (¡Cámbialas!)
ADMIN_NAME="Administrador General"
ADMIN_EMAIL="admin@tucolegio.edu.ar"
ADMIN_PASSWORD="TuContraseñaSegura2026"

# Clave secreta para JWT
SECRET_KEY="clave_aleatoria_muy_segura_aqui"

# PostgreSQL
POSTGRES_USER=sigen
POSTGRES_PASSWORD=sigen_pass
POSTGRES_DB=sigen_colegio
POSTGRES_PORT=5432
```

> **Tip para el nombre del colegio:** Puedes editar `config/school.default.yml` para cambiar el nombre visible (`school.name`), lema (`school.slogan`) y colores institucionales (`primary_color`, `secondary_color`).

---

### 3. Iniciar el contenedor

En la carpeta `backend_colegio_docker`, ejecuta:

```bash
docker compose up -d --build
```

Docker descargará PostgreSQL, compilará la imagen del backend, inicializará las tablas, creará el Super Administrador y dejará el servicio corriendo en segundo plano.

Para ver los logs de arranque en tiempo real:
```bash
docker compose logs -f backend
```

Verás una salida similar a esta:
```text
[1/3] Configuración activa: config/school.default.yml
[2/3] Verificando conexión con PostgreSQL...
 Conexión a PostgreSQL establecida con éxito.
[3/3] Inicializando base de datos y verificando Super Admin...
Creando tablas en la base de datos...
Tablas creadas correctamente.
Registrando escuela 'Colegio Base SIGEN' en la base de datos...
Registrando roles y permisos...
[ÉXITO] Superadmin creado correctamente.
  - Nombre: Administrador General
  - Email:  admin@tucolegio.edu.ar
  - Rol:    superadmin
==========================================================
 Backend listo. Escuchando en el puerto 8001...
==========================================================
INFO:     Application startup complete.
```

---

##  Verificación y Uso

### 1. Estado de salud (Health Check)
```bash
curl http://localhost:8001/health
```
Respuesta esperada:
```json
{
  "status": "ok",
  "school": "Colegio Base SIGEN",
  "version": "1.0.0-beta",
  "modules": { ... }
}
```

### 2. Documentación Swagger Interactiva
Abre en tu navegador:
```text
http://TU_IP_O_DOMINIO:8001/docs
```

### 3. Iniciar Sesión (Login)
Puedes enviar una petición `POST` a `/auth/login`:
```bash
curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@tucolegio.edu.ar", "password": "TuContraseñaSegura2026"}'
```

---

## 🛠 Opciones Avanzadas

### Conectar a un PostgreSQL que ya existe en el servidor
Si en tu VPS ya tienes un contenedor o servidor de PostgreSQL corriendo (por ejemplo en el puerto 5432):
1. En `docker-compose.yml`, elimina o comenta el servicio `postgres`.
2. En `.env`, configura tu `DATABASE_URL` apuntando a tu PostgreSQL existente:
   ```env
   DATABASE_URL=postgresql://usuario:password@host:5432/nombre_db
   ```
3. Ejecuta `docker compose up -d --build`.

### Desplegar varios colegios en el mismo servidor
Si quieres desplegar un segundo o tercer colegio independiente:
1. Copia la carpeta con otro nombre: `cp -r backend_colegio_docker/ backend_colegio2/`
2. En `backend_colegio2/.env`:
   - Cambia `PORT=8002`
   - Cambia `POSTGRES_DB=sigen_colegio2`
   - Cambia `POSTGRES_PORT=5433` (o usa la misma base de datos Postgres cambiando solo el nombre de la BD)
   - Ajusta el email/password del admin.
3. En `backend_colegio2/docker-compose.yml`, cambia `container_name: sigen-colegio2-backend`.
4. Ejecuta `docker compose up -d --build`.

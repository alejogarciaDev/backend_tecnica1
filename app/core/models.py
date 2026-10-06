from app.modules.users.users.models import User
from app.modules.users.roles.models import Role
from app.modules.users.permissions.models import Permission
from app.modules.schools.models import School
from app.modules.panol.categories.models import Category, ToolType, Tool
from app.modules.panol.loans.models import Loan
from app.modules.panol.orders.models import Order
from app.modules.panol.orders.items.models import OrderItem
from app.modules.academico.alumnos.models import Alumno, AlumnoHistorial
from app.modules.academico.materias.models import Materia
from app.modules.academico.archivos.models import Archivo
from app.modules.campus.models import Tarea, Entrega, Calificacion, MaterialEstudio, DocumentoAlumno, DocumentoCompartido, CompartidoPermiso, EntregaComentario, Comunicado, ComunicadoComentario
from app.modules.notifications.models import Notification
from app.modules.profesores.models import Profesor
from app.modules.oficina_alumnos.models import Tramite
from app.modules.academico.cursos.models import Curso
from app.modules.academico.asistencias.models import Asistencia
from app.modules.academico.calificaciones.models import CalificacionAcademica
from app.modules.academico.horarios.models import Horario
from app.modules.academico.alumnos.models import FamiliarTutor
from app.modules.whatsapp.models import WhatsappLog
from app.modules.audit.models import AuditLog


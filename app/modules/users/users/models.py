from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"))
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True)
    supabase_uid = Column(String, nullable=True)
    role = relationship("Role")
    school = relationship("School", backref="users")
    loans = relationship("Loan", foreign_keys="[Loan.user_id]", back_populates="user")
    permissions = relationship("Permission", secondary="user_permissions", back_populates="users")

    dni = Column(String, nullable=True)
    domicilio = Column(String, nullable=True)
    fecha_nacimiento = Column(String, nullable=True)
    accepted_terms = Column(Boolean, default=False)
    must_change_password = Column(Boolean, default=False)
    account_status = Column(String, default="ACTIVA") # SIN_ACTIVAR, ACTIVACION_PENDIENTE, ACTIVA, BLOQUEADA
    identity_status = Column(String, default="NO_VERIFICADA") # NO_VERIFICADA, EN_VERIFICACION, VERIFICADA, RECHAZADA

    @property
    def dashboards(self):
        return [p.name.split(":")[1] for p in self.permissions if p.name.startswith("dashboard:")]

    @property
    def role_name(self):
        return self.role.name if self.role else None

    @property
    def tipo(self):
        return self.profesor_profile[0].tipo if hasattr(self, 'profesor_profile') and self.profesor_profile else None

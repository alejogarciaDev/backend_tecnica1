import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./sistema_central.db"
elif DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from sqlalchemy import event

@event.listens_for(SessionLocal, "before_flush")
def before_flush(session, flush_context, instances):
    from app.core.school_config import get_school_config
    from app.modules.schools.models import School
    try:
        cfg = get_school_config()
        # Avoid database query recursion if we are querying School itself and it has no school_id
        school = session.query(School).filter(School.domain == cfg.domain).first()
        active_school_id = school.id if school else None
    except Exception:
        active_school_id = None

    if active_school_id is not None:
        for obj in session.new:
            if hasattr(obj, "school_id") and getattr(obj, "school_id") is None:
                # Do not set school_id on School model itself
                if not isinstance(obj, School):
                    setattr(obj, "school_id", active_school_id)

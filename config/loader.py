import os
import yaml
from pathlib import Path
from typing import Optional


class SchoolConfig:
    def __init__(self, data: dict):
        self.raw = data
        school = data.get("school", {})
        db = data.get("database", {})

        self.name = school.get("name", "Mi Escuela")
        self.short_name = school.get("short_name", self.name)
        self.slogan = school.get("slogan", "")
        self.domain = school.get("domain", "localhost")
        self.logo = school.get("logo", "/imagenes/logo-default.png")
        self.favicon = school.get("favicon", "/imagenes/favicon.ico")
        self.primary_color = school.get("primary_color", "#1a3a5c")
        self.secondary_color = school.get("secondary_color", "#e67e22")
        self.font_family = school.get("font_family", "Segoe UI, sans-serif")
        self.panol_use_barcodes = school.get("panol_use_barcodes", True)

        self.address = school.get("address", "")
        self.phone = school.get("phone", "")
        self.email = school.get("email", "")

        modules = school.get("modules", {})
        self.modules = {
            "panol": modules.get("panol", True),
            "campus": modules.get("campus", True),
            "alumnos": modules.get("alumnos", True),
            "materias": modules.get("materias", True),
            "archivos": modules.get("archivos", True),
            "notificaciones": modules.get("notificaciones", True),
            "biblioteca": modules.get("biblioteca", True),
            "profesores": modules.get("profesores", True),
            "oficina_alumnos": modules.get("oficina_alumnos", True),
        }

        self.roles = school.get("roles", [])
        self.dashboards = school.get("dashboards", [])

        files = school.get("files", {})
        self.max_file_size_mb = files.get("max_size_mb", 100)
        self.allowed_file_types = files.get("allowed_types", ["*/*"])
        self.storage_path = files.get("storage_path", "data/archivos")

        login = school.get("login", {})
        self.login_title = login.get("title", "Iniciar Sesión")
        self.login_subtitle = login.get("subtitle", "Ingrese sus credenciales")
        self.login_bg_color = login.get("background_color", "#f0f2f5")

        footer = school.get("footer", {})
        self.footer_text = footer.get("text", "© {year} {school_name}")
        self.show_powered_by = footer.get("show_powered_by", True)

        self.database_url = db.get("url", "sqlite:///./sistema.db")


class ConfigLoader:
    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = config_dir or os.path.join(os.path.dirname(__file__))
        self._cache = {}

    def load_default(self) -> SchoolConfig:
        return self._load_file(os.path.join(self.config_dir, "school.default.yml"))

    def load_school(self, school_id: str) -> SchoolConfig:
        path = os.path.join(self.config_dir, "schools", f"{school_id}.yml")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Config not found for school: {school_id}")
        return self._load_file(path)

    def load_by_domain(self, domain: str) -> SchoolConfig:
        schools_dir = os.path.join(self.config_dir, "schools")
        if not os.path.isdir(schools_dir):
            raise FileNotFoundError(f"Schools dir not found: {schools_dir}")
        for fname in os.listdir(schools_dir):
            if fname.endswith((".yml", ".yaml")):
                cfg = self._load_file(os.path.join(schools_dir, fname))
                if cfg.domain == domain:
                    return cfg
        return self.load_default()

    def list_schools(self) -> list[dict]:
        schools = []
        schools_dir = os.path.join(self.config_dir, "schools")
        if not os.path.isdir(schools_dir):
            return schools
        for fname in os.listdir(schools_dir):
            if fname.endswith((".yml", ".yaml")):
                cfg = self._load_file(os.path.join(schools_dir, fname))
                schools.append({
                    "id": fname.replace(".yml", "").replace(".yaml", ""),
                    "name": cfg.name, "short_name": cfg.short_name,
                    "domain": cfg.domain, "slogan": cfg.slogan,
                    "email": cfg.email, "phone": cfg.phone,
                    "address": cfg.address,
                    "primary_color": cfg.primary_color,
                    "secondary_color": cfg.secondary_color,
                    "logo": cfg.logo, "modules": cfg.modules,
                })
        return schools

    def _load_file(self, path: str) -> SchoolConfig:
        if path in self._cache:
            return self._cache[path]
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        config = SchoolConfig(data)
        self._cache[path] = config
        return config


loader = ConfigLoader()

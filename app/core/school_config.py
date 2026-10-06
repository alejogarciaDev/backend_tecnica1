import os, sys
# Support multiple environment directory layouts (docker container, monorepo, standalone)
possible_dirs = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), *[os.pardir] * 4)),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")),
    "/app",
    "/"
]
for p in possible_dirs:
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

from config.loader import ConfigLoader, SchoolConfig

SCHOOL_CONFIG_PATH = os.getenv("SCHOOL_CONFIG_PATH")

cfg_dir = None
for candidate in ["/config", "/app/config", os.path.join(os.path.dirname(__file__), *[os.pardir] * 4, "config")]:
    if os.path.isdir(candidate):
        cfg_dir = os.path.abspath(candidate)
        break

_loader = ConfigLoader(config_dir=cfg_dir)
_active_config = None

def get_school_config() -> SchoolConfig:
    global _active_config
    if _active_config is None:
        config_file = SCHOOL_CONFIG_PATH or os.getenv("SCHOOL_ID", "")
        if config_file and os.path.exists(config_file):
            _active_config = _loader._load_file(config_file)
        elif config_file:
            try:
                _active_config = _loader.load_school(config_file)
            except FileNotFoundError:
                _active_config = _loader.load_default()
        else:
            _active_config = _loader.load_default()
    return _active_config

def reload_school_config():
    global _active_config
    _active_config = None
    _loader._cache.clear()
    return get_school_config()

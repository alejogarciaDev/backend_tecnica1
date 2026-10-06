import os
import json
import importlib
from fastapi import FastAPI
from app.core.school_config import get_school_config

class PluginLoader:
    def __init__(self, plugins_dir: str = None):
        if plugins_dir is None:
            # Point to app/plugins directory
            plugins_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugins")
        self.plugins_dir = plugins_dir
        self.loaded_plugins = {}

    def load_active_plugins(self, app: FastAPI):
        """Scan plugins directory and load enabled plugins in the active school config."""
        if not os.path.exists(self.plugins_dir):
            os.makedirs(self.plugins_dir, exist_ok=True)
            return

        cfg = get_school_config()
        # Ensure we have active plugins configuration from config file
        active_modules = cfg.modules if hasattr(cfg, 'modules') else {}

        for folder in os.listdir(self.plugins_dir):
            folder_path = os.path.join(self.plugins_dir, folder)
            if not os.path.isdir(folder_path):
                continue

            plugin_json_path = os.path.join(folder_path, "plugin.json")
            if not os.path.exists(plugin_json_path):
                continue

            try:
                with open(plugin_json_path, "r", encoding="utf-8") as f:
                    plugin_meta = json.load(f)
                
                plugin_id = plugin_meta.get("id")
                if not plugin_id:
                    continue

                # Check if this plugin is enabled in school config
                if active_modules.get(plugin_id):
                    self._load_plugin(plugin_id, app, plugin_meta)
                    
            except Exception as e:
                print(f"Failed to load metadata for plugin in folder '{folder}': {e}")

    def _load_plugin(self, plugin_id: str, app: FastAPI, meta: dict):
        """Import the plugin modules and mount router / execute custom initializers."""
        try:
            # 1. Dynamically import plugin backend models (for SQLAlchemy auto-loading)
            try:
                importlib.import_module(f"app.plugins.{plugin_id}.backend.models")
            except ModuleNotFoundError:
                pass # Models are optional for simple plugins

            # 2. Dynamically import backend routes
            try:
                routes_module = importlib.import_module(f"app.plugins.{plugin_id}.backend.routes")
                if hasattr(routes_module, "router"):
                    app.include_router(routes_module.router)
                    print(f"Mounted router for plugin: {plugin_id}")
            except ModuleNotFoundError:
                pass # Routes are optional (e.g. for pure event listener / technological plugins)

            # 3. Call initialize function if exists
            try:
                init_module = importlib.import_module(f"app.plugins.{plugin_id}.backend")
                if hasattr(init_module, "initialize"):
                    init_module.initialize(app)
                    print(f"Initialized custom logic for plugin: {plugin_id}")
            except ModuleNotFoundError:
                pass

            self.loaded_plugins[plugin_id] = meta
            print(f"Successfully loaded plugin: {meta.get('name', plugin_id)} (v{meta.get('version', '1.0.0')})")
        except Exception as e:
            print(f"Error loading plugin '{plugin_id}': {e}")

# Global instance
plugin_loader = PluginLoader()

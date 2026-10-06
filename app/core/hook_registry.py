from typing import Callable, List, Dict, Any

class HookRegistry:
    def __init__(self):
        self._actions: Dict[str, List[Callable]] = {}
        self._filters: Dict[str, List[Callable]] = {}

    def register_action(self, hook_name: str, callback: Callable):
        """Register a callback to run when an action hook is triggered."""
        if hook_name not in self._actions:
            self._actions[hook_name] = []
        self._actions[hook_name].append(callback)

    def register_filter(self, hook_name: str, callback: Callable):
        """Register a callback to process and modify a value when a filter hook is applied."""
        if hook_name not in self._filters:
            self._filters[hook_name] = []
        self._filters[hook_name].append(callback)

    def trigger_action(self, hook_name: str, *args, **kwargs):
        """Trigger all actions registered to a hook."""
        if hook_name in self._actions:
            for callback in self._actions[hook_name]:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    print(f"Error in hook action {hook_name} callback {callback.__name__}: {e}")

    def apply_filters(self, hook_name: str, value: Any, *args, **kwargs) -> Any:
        """Apply a chain of filter callbacks to a value and return the final processed value."""
        if hook_name in self._filters:
            for callback in self._filters[hook_name]:
                try:
                    value = callback(value, *args, **kwargs)
                except Exception as e:
                    print(f"Error in hook filter {hook_name} callback {callback.__name__}: {e}")
        return value

# Global instance for app-wide use
hook_registry = HookRegistry()

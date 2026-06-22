from dataclasses import dataclass, field
import importlib.util
import os
import traceback


@dataclass
class UIExtension:
    """A button or menu action contributed at a named UI insertion point."""

    id: str
    location: str
    label: str
    callback: object
    order: int = 100
    tooltip: str = ""
    object_name: str = ""
    width: int = 0
    height: int = 0
    menu_path: tuple = field(default_factory=tuple)


class UIExtensionRegistry:
    """Registry for optional UI additions without editing MainWindow."""

    LOCATIONS = {
        "library_tools",
        "web_menu",
        "primary_actions",
    }

    def __init__(self):
        self._extensions = {}
        self.load_errors = []

    def register(self, extension):
        if not isinstance(extension, UIExtension):
            raise TypeError("extension must be a UIExtension")
        if extension.location not in self.LOCATIONS:
            raise ValueError(
                f"Unknown UI location: {extension.location}"
            )
        self._extensions[extension.id] = extension
        return extension

    def at(self, location):
        return sorted(
            (
                extension
                for extension in self._extensions.values()
                if extension.location == location
            ),
            key=lambda extension: (extension.order, extension.label.casefold()),
        )

    def discover(self, folder):
        if not os.path.isdir(folder):
            return
        for filename in sorted(os.listdir(folder)):
            if filename.startswith("_") or not filename.endswith(".py"):
                continue
            path = os.path.join(folder, filename)
            module_name = (
                f"premiedrop_ui_extension_"
                f"{os.path.splitext(filename)[0]}"
            )
            try:
                spec = importlib.util.spec_from_file_location(
                    module_name, path
                )
                if spec is None or spec.loader is None:
                    raise ImportError(f"Could not load {path}")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                register = getattr(module, "register", None)
                if not callable(register):
                    raise AttributeError(
                        "UI module must define register(registry)"
                    )
                register(self)
            except Exception:
                self.load_errors.append(
                    (path, traceback.format_exc())
                )

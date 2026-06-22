from dataclasses import dataclass, field
import importlib.util
import os
import traceback


@dataclass
class ImportContext:
    """Stable data and services passed to an import provider."""

    app: object
    sections: list
    project_folder: str
    app_data_dir: str

    def all_files(self):
        return [
            path
            for section in self.sections
            for path in section.get("files", [])
            if os.path.isfile(path)
        ]

    def files_by_section(self):
        return [
            {
                "name": section.get("name", "PremieDrop"),
                "files": [
                    os.path.abspath(path)
                    for path in section.get("files", [])
                    if os.path.isfile(path)
                ],
            }
            for section in self.sections
            if any(
                os.path.isfile(path)
                for path in section.get("files", [])
            )
        ]


@dataclass
class ImportProvider:
    """Declarative editor integration shown in the Import menu."""

    id: str
    menu_label: str
    button_label: str
    handler: object = None
    group: str = ""
    group_order: int = 100
    order: int = 100
    available: bool = True
    unavailable_reason: str = ""
    tooltip: str = ""
    metadata: dict = field(default_factory=dict)

    def execute(self, context):
        if not self.available:
            raise RuntimeError(
                self.unavailable_reason
                or f"{self.menu_label} is not available."
            )
        if not callable(self.handler):
            raise NotImplementedError(
                f"No import handler is registered for {self.menu_label}."
            )
        return self.handler(context)


class ImportRegistry:
    """Registry and plugin loader for import providers."""

    def __init__(self):
        self._providers = {}
        self.load_errors = []

    def register(self, provider):
        if not isinstance(provider, ImportProvider):
            raise TypeError("provider must be an ImportProvider")
        if not provider.id:
            raise ValueError("provider.id is required")
        self._providers[provider.id] = provider
        return provider

    def get(self, provider_id):
        return self._providers.get(provider_id)

    def providers(self):
        return sorted(
            self._providers.values(),
            key=lambda provider: (
                provider.group_order,
                provider.order,
                provider.menu_label.casefold(),
            ),
        )

    def groups(self):
        grouped = {}
        for provider in self.providers():
            grouped.setdefault(provider.group, []).append(provider)
        return grouped

    def discover(self, folder):
        if not os.path.isdir(folder):
            return
        for filename in sorted(os.listdir(folder)):
            if filename.startswith("_") or not filename.endswith(".py"):
                continue
            path = os.path.join(folder, filename)
            module_name = (
                f"premiedrop_import_provider_"
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
                        "Provider module must define register(registry)"
                    )
                register(self)
            except Exception:
                self.load_errors.append(
                    (path, traceback.format_exc())
                )

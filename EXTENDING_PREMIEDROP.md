# Extending PremieDrop

PremieDrop has two extension surfaces. Extensions are loaded when the app
starts, so restart PremieDrop after changing a plugin.

## Editor import providers

Place provider modules in `import_providers/`. A module exposes
`register(registry)` and registers one or more `ImportProvider` objects.

Providers receive an `ImportContext` with:

- `context.app`: the running `MainWindow` for optional advanced services.
- `context.sections`: the current PremieDrop section structure.
- `context.project_folder`: the selected project folder.
- `context.app_data_dir`: PremieDrop's writable application-data folder.
- `context.all_files()`: every existing media file.
- `context.files_by_section()`: existing files grouped by section.

Use a stable provider `id`; it is saved as the user's selected editor.
Registering the same ID from a later-loaded module replaces the previous
provider, allowing an external module to implement a built-in placeholder.

Example:

```python
from premiedrop_ext import ImportProvider

def import_with_uxp(context):
    files = context.files_by_section()
    # Send files to your UXP bridge.

def register(registry):
    registry.register(ImportProvider(
        id="premiere_uxp",
        menu_label="UXP",
        button_label="Import to Premiere (UXP)",
        group="Premiere Pro",
        group_order=10,
        handler=import_with_uxp,
        tooltip="Import through my UXP bridge.",
    ))
```

## UI configuration

Edit `premiedrop_ext/ui_config.py` for common labels, window dimensions,
button sizes, spacing, and theme colors.

## UI plugins

Place UI modules in `ui_plugins/`. Each module exposes `register(registry)`
and adds `UIExtension` objects at named insertion points:

- `library_tools`: beside Section and URL.
- `web_menu`: inside the Web dropdown.
- `primary_actions`: beside Add Files and Web.

The callback receives the active `MainWindow`.

```python
from premiedrop_ext import UIExtension

def register(registry):
    registry.register(UIExtension(
        id="show_file_count",
        location="primary_actions",
        label="Count",
        tooltip="Print the number of loaded files",
        callback=lambda window: print(len(window.all_files())),
        order=50,
    ))
```

Plugin load failures are retained in `registry.load_errors` for diagnostics.

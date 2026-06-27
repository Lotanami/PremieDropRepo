# PremieDrop import providers

Add a Python file here to integrate another editor or replace an unfinished
integration. Every provider module must expose:

```python
from premiedrop_ext import ImportProvider

def run_import(context):
    # context.sections, context.project_folder, context.all_files()
    ...

def register(registry):
    registry.register(ImportProvider(
        id="my_editor",
        menu_label="My Editor",
        button_label="Import to My Editor",
        group="My Editor",
        handler=run_import,
    ))
```

Provider IDs are persisted, so keep them stable after release.

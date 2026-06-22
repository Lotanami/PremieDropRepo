# PremieDrop UI plugins

Add controls without editing `MainWindow.init_ui()`:

```python
from premiedrop_ext import UIExtension

def register(registry):
    registry.register(UIExtension(
        id="hello",
        location="primary_actions",
        label="Hello",
        tooltip="Example button",
        callback=lambda window: print(window),
        order=50,
    ))
```

Supported insertion points:

- `library_tools`
- `web_menu`
- `primary_actions`

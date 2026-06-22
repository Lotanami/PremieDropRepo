"""PremieDrop extension APIs.

Third-party integrations should import public types from this package rather
than importing implementation details from main_sections.py.
"""

from .imports import ImportContext, ImportProvider, ImportRegistry
from .ui import UIExtension, UIExtensionRegistry

__all__ = [
    "ImportContext",
    "ImportProvider",
    "ImportRegistry",
    "UIExtension",
    "UIExtensionRegistry",
]

"""Built-in import providers.

Replace a handler here, or add another provider module beside this file.
"""

from premiedrop_ext import ImportProvider


def call(method_name):
    def handler(context):
        return getattr(context.app, method_name)()
    return handler


def not_implemented(message):
    def handler(_context):
        raise NotImplementedError(message)
    return handler


def register(registry):
    registry.register(ImportProvider(
        id="premiere_cep",
        menu_label="CEP",
        button_label="Import to Premiere (CEP)",
        group="Premiere Pro",
        group_order=10,
        order=10,
        handler=call("copy_new_to_project"),
        tooltip="Import through the PremieDrop CEP bridge.",
    ))
    registry.register(ImportProvider(
        id="premiere_uxp",
        menu_label="UXP",
        button_label="Import to Premiere (UXP)",
        group="Premiere Pro",
        group_order=10,
        order=20,
        handler=not_implemented(
            "The Premiere Pro UXP import provider has not been implemented."
        ),
        unavailable_reason=(
            "The Premiere Pro UXP import provider has not been implemented."
        ),
        tooltip="Add the UXP implementation in import_providers/.",
    ))
    registry.register(ImportProvider(
        id="davinci_resolve",
        menu_label="R̶e̶s̶o̶l̶v̶e̶  (Unavailable)",
        button_label="Import to DaVinci (Resolve)",
        group="DaVinci Resolve",
        group_order=20,
        order=10,
        available=False,
        unavailable_reason=(
            "Automatic importing is unavailable in free DaVinci Resolve."
        ),
    ))
    registry.register(ImportProvider(
        id="davinci_studio",
        menu_label="Studio",
        button_label="Import to DaVinci (Studio)",
        group="DaVinci Resolve",
        group_order=20,
        order=20,
        handler=call("import_to_davinci_studio"),
        tooltip="Import through DaVinci Resolve Studio's scripting API.",
    ))
    registry.register(ImportProvider(
        id="final_cut",
        menu_label="Final Cut Pro",
        button_label="Import to Final Cut",
        group_order=30,
        order=40,
        handler=not_implemented(
            "The Final Cut Pro import provider has not been implemented."
        ),
        unavailable_reason=(
            "The Final Cut Pro import provider has not been implemented."
        ),
        tooltip="Add the Final Cut implementation in import_providers/.",
    ))

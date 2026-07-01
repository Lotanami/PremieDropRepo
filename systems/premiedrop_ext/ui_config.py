"""Central UI text, sizing, and theme configuration.

Change values here for common visual tweaks. For new controls, add a plugin
under ui_plugins/ instead of modifying MainWindow.init_ui().
"""

APP_TEXT = {
    "window_title": "PremieDrop v0.12",
    "title": "🎬 PremieDrop v0.12",
    "subtitle": "Your media, one drag away",
    "search_placeholder": "Search files, folders, or sections...",
    "drag_tip": "✦  Select files above and drag them into your editor",
    "add_files": "＋  Add Files",
    "web": "Web",
    "clear_all": "Clear All",
    "add_section": "+ Section",
    "download_url": "URL",
}

UI_SIZES = {
    "base_window_width": 650,
    "base_window_height": 800,
    "main_margin": 20,
    "main_spacing": 12,
    "primary_button_height": 42,
    "tool_button_height": 34,
    "web_button_width": 78,
    "url_button_width": 54,
    "clear_button_width": 100,
    "import_button_min_width": 190,
}

THEME = {
    "background": "#1a1a2e",
    "panel": "#16213e",
    "accent": "#6C63FF",
    "accent_hover": "#7b72ff",
    "text": "#eeeeff",
    "muted_text": "#8888aa",
    "success": "#1a6b3a",
}

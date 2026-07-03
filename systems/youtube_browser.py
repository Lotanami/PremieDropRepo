import ctypes
from ctypes import wintypes
import json
import mimetypes
import os
import sys
import time
import traceback
from urllib.parse import quote_plus, urlparse

from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


def append_log(log_path, message):
    if not log_path:
        return
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except OSError:
        pass


def windows_api():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
    user32.SetParent.restype = wintypes.HWND
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.SetWindowLongW.argtypes = [
        wintypes.HWND, ctypes.c_int, ctypes.c_long
    ]
    user32.SetWindowLongW.restype = ctypes.c_long
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    return user32


class YouTubeBrowserWindow(QWidget):
    def __init__(
        self, web_view_class, request_path, dock_state_path, status_path,
        log_path, command_path, initial_tab, youtube_url, myinstants_url
    ):
        super().__init__()
        self.request_path = request_path
        self.dock_state_path = dock_state_path
        self.status_path = status_path
        self.log_path = log_path
        self.command_path = command_path
        self.browser_presets_path = os.path.join(
            os.path.dirname(command_path), "browser_presets.json"
        )
        self.web_view_class = web_view_class
        self.sites = {
            "youtube": {
                "name": "YouTube",
                "url": youtube_url,
            },
            "myinstants": {
                "name": "MyInstants",
                "url": myinstants_url,
            },
            "search": {
                "name": "Web Search",
                "url": "https://www.google.com/",
            },
        }
        self.image_searches = {}
        self.next_image_search_id = 1
        self.active_image_search_id = None
        self.website_searches = {}
        self.next_website_search_id = 1
        self.active_website_search_id = None
        self.browser_presets = []
        self.load_browser_state()
        self.requested_initial_tab = initial_tab
        self.current_tab = (
            initial_tab if initial_tab in self.sites else "youtube"
        )
        self.attached = True
        self.native_parent_hwnd = 0
        self.qt_frameless = False
        self.setWindowTitle("PremieDrop Media Browser")
        self.resize(900, 760)
        self.setMinimumSize(520, 520)
        self.setStyleSheet("""
            QWidget {
                background-color: #1a1a2e;
                color: #eeeeff;
            }
            QPushButton {
                min-height: 32px;
                padding: 0px 12px;
                background-color: #24244d;
                color: #eeeeff;
                border: 1px solid #45456f;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #6C63FF;
                color: #ffffff;
                border: 2px solid #aaa6ff;
                font-weight: bold;
            }
            QPushButton:pressed {
                background-color: #4f47d8;
                color: #ffffff;
                border: 2px solid #ffffff;
            }
            QPushButton#youtube_home {
                background-color: #b3261e;
                border-color: #e0443a;
                font-weight: bold;
            }
            QPushButton#myinstants_home {
                background-color: #d35400;
                border-color: #f39c12;
                font-weight: bold;
            }
            QPushButton#images_home {
                background-color: #2563a8;
                border-color: #4f8fd1;
                font-weight: bold;
            }
            QPushButton#youtube_download {
                background-color: #1a6b3a;
                border-color: #288c50;
                font-weight: bold;
            }
            QPushButton#attach_toggle {
                background-color: #4b356f;
                border-color: #6b4d99;
                font-weight: bold;
            }
            QPushButton#close_browser {
                background-color: #6b2632;
                border-color: #a63f50;
                font-weight: bold;
            }
            QPushButton#youtube_home:hover,
            QPushButton#myinstants_home:hover,
            QPushButton#images_home:hover,
            QPushButton#youtube_download:hover,
            QPushButton#attach_toggle:hover,
            QPushButton#close_browser:hover {
                background-color: #6C63FF;
                color: #ffffff;
                border: 2px solid #ffffff;
            }
            QMenu {
                background-color: #16213e;
                color: #eeeeff;
                border: 1px solid #62629a;
                padding: 5px;
            }
            QMenu::item {
                min-width: 190px;
                padding: 8px 22px 8px 12px;
                border: 1px solid transparent;
                border-radius: 5px;
            }
            QMenu::item:selected {
                background-color: #7b72ff;
                color: #ffffff;
                border: 1px solid #ffffff;
                font-weight: bold;
            }
            QMenu::separator {
                height: 1px;
                background-color: #51517f;
                margin: 5px 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(7)

        controls = QHBoxLayout()
        controls.setSpacing(6)

        back_btn = QPushButton("◀")
        back_btn.setToolTip("Back")
        back_btn.setFixedWidth(38)
        back_btn.clicked.connect(self.go_back)
        controls.addWidget(back_btn)

        forward_btn = QPushButton("▶")
        forward_btn.setToolTip("Forward")
        forward_btn.setFixedWidth(38)
        forward_btn.clicked.connect(self.go_forward)
        controls.addWidget(forward_btn)

        reload_btn = QPushButton("↻")
        reload_btn.setToolTip("Reload")
        reload_btn.setFixedWidth(38)
        reload_btn.clicked.connect(self.reload_page)
        controls.addWidget(reload_btn)

        self.youtube_tab_btn = QPushButton("YouTube")
        self.youtube_tab_btn.setObjectName("youtube_home")
        self.youtube_tab_btn.clicked.connect(
            lambda: self.switch_tab("youtube")
        )
        controls.addWidget(self.youtube_tab_btn)

        self.myinstants_tab_btn = QPushButton("MyInstants")
        self.myinstants_tab_btn.setObjectName("myinstants_home")
        self.myinstants_tab_btn.clicked.connect(
            lambda: self.switch_tab("myinstants")
        )
        controls.addWidget(self.myinstants_tab_btn)

        self.images_tab_btn = QPushButton("🔍")
        self.images_tab_btn.setObjectName("images_home")
        self.images_tab_btn.setToolTip("Open saved image searches")
        self.images_tab_btn.setFixedWidth(72)
        self.images_menu = QMenu(self.images_tab_btn)
        self.images_menu.setToolTipsVisible(True)
        self.images_menu.setContextMenuPolicy(Qt.CustomContextMenu)
        self.images_menu.customContextMenuRequested.connect(
            self.show_saved_site_context_menu
        )
        self.images_menu.aboutToShow.connect(self.rebuild_images_menu)
        self.images_tab_btn.setMenu(self.images_menu)
        controls.addWidget(self.images_tab_btn)

        self.attach_btn = QPushButton("Pop Out")
        self.attach_btn.setObjectName("attach_toggle")
        self.attach_btn.clicked.connect(self.toggle_attachment)
        controls.addWidget(self.attach_btn)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("close_browser")
        close_btn.setToolTip("Hide the web panel without unloading its pages")
        close_btn.clicked.connect(self.hide_browser_panel)
        controls.addWidget(close_btn)

        controls.addStretch()

        self.download_btn = QPushButton("DL URL")
        self.download_btn.setObjectName("youtube_download")
        self.download_btn.setToolTip(
            "Open the current YouTube URL in PremieDrop's downloader"
        )
        self.download_btn.setFixedWidth(58)
        self.download_btn.setStyleSheet("font-size: 10px; padding: 0px 6px;")
        self.download_btn.clicked.connect(self.send_download_request)
        controls.addWidget(self.download_btn)
        layout.addLayout(controls)

        self.tabs = QStackedWidget(self)
        self.web_views = {}
        for tab_name, site in self.sites.items():
            web_view = web_view_class(self)
            web_view.setProperty("tab_name", tab_name)
            web_view.titleChanged.connect(
                lambda title, name=tab_name:
                self.update_page_title(name, title)
            )
            web_view.setUrl(QUrl(site["url"]))
            self.web_views[tab_name] = web_view
            self.tabs.addWidget(web_view)
        self.web_views["search"].urlChanged.connect(
            self.update_active_website_url
        )
        layout.addWidget(self.tabs, 1)

        self.web_views["youtube"].page().profile().downloadRequested.connect(
            self.handle_browser_download
        )

        self.dock_timer = QTimer(self)
        self.dock_timer.setInterval(150)
        self.dock_timer.timeout.connect(self.sync_with_premiedrop)
        self.dock_timer.start()
        self.sync_with_premiedrop()

        self.command_timer = QTimer(self)
        self.command_timer.setInterval(150)
        self.command_timer.timeout.connect(self.check_browser_command)
        self.command_timer.start()
        self.switch_tab(self.current_tab)
        if self.requested_initial_tab == "images":
            QTimer.singleShot(0, self.search_images)
        elif self.requested_initial_tab == "search":
            QTimer.singleShot(0, self.search_website)

    def current_web_view(self):
        if self.current_tab == "images":
            key = self.image_view_key(self.active_image_search_id)
            return self.web_views.get(key)
        return self.web_views[self.current_tab]

    def go_back(self):
        view = self.current_web_view()
        if view is not None:
            view.back()

    def go_forward(self):
        view = self.current_web_view()
        if view is not None:
            view.forward()

    def reload_page(self):
        view = self.current_web_view()
        if view is not None:
            view.reload()

    def go_home(self):
        if self.current_tab == "images":
            self.search_images()
            return
        self.current_web_view().setUrl(
            QUrl(self.sites[self.current_tab]["url"])
        )

    def search_images(self):
        query, accepted = QInputDialog.getText(
            self,
            "Search Images",
            "What images are you looking for?",
        )
        query = query.strip()
        if not accepted or not query:
            return
        search_url = (
            "https://www.google.com/search?tbm=isch&q="
            f"{quote_plus(query)}"
        )
        search_id = self.next_image_search_id
        self.next_image_search_id += 1
        self.image_searches[search_id] = {
            "label": query,
            "url": search_url,
        }
        self.open_saved_image_search(search_id)

    def search_website(self):
        query, accepted = QInputDialog.getText(
            self,
            "Search Website",
            "Enter a website address or search:",
        )
        query = query.strip()
        if not accepted or not query:
            return
        if "://" in query:
            target_url = query
        elif "." in query and " " not in query:
            target_url = f"https://{query}"
        else:
            target_url = (
                "https://www.google.com/search?q="
                f"{quote_plus(query)}"
            )
        website_id = self.next_website_search_id
        self.next_website_search_id += 1
        self.website_searches[website_id] = {
            "label": query,
            "url": target_url,
        }
        self.save_browser_state()
        self.open_saved_website(website_id)

    def open_saved_website(self, website_id):
        if website_id not in self.website_searches:
            return
        self.active_website_search_id = website_id
        self.switch_tab("search")
        self.web_views["search"].setUrl(
            QUrl(self.website_searches[website_id]["url"])
        )

    def update_active_website_url(self, url):
        website_id = self.active_website_search_id
        if website_id in self.website_searches:
            self.website_searches[website_id]["url"] = url.toString()
            self.save_browser_state()

    def image_view_key(self, search_id):
        return f"image:{search_id}"

    def create_image_view(self, search_id):
        search = self.image_searches[search_id]
        key = self.image_view_key(search_id)
        web_view = self.web_view_class(self)
        web_view.setProperty("tab_name", "images")
        web_view.setZoomFactor(0.8)
        web_view.loadFinished.connect(
            lambda _ok, view=web_view: view.setZoomFactor(0.8)
        )
        web_view.urlChanged.connect(
            lambda url, sid=search_id:
            self.save_image_search_url(sid, url)
        )
        web_view.titleChanged.connect(
            lambda title, sid=search_id:
            self.update_image_page_title(sid, title)
        )
        web_view.setUrl(QUrl(search["url"]))
        self.web_views[key] = web_view
        self.tabs.addWidget(web_view)
        return web_view

    def save_image_search_url(self, search_id, url):
        if search_id in self.image_searches:
            self.image_searches[search_id]["url"] = url.toString()

    def unload_active_image_view(self):
        search_id = self.active_image_search_id
        if search_id is None:
            return
        key = self.image_view_key(search_id)
        web_view = self.web_views.pop(key, None)
        if web_view is not None:
            self.image_searches[search_id]["url"] = (
                web_view.url().toString()
            )
            self.tabs.removeWidget(web_view)
            web_view.setUrl(QUrl("about:blank"))
            web_view.deleteLater()
        self.active_image_search_id = None

    def open_saved_image_search(self, search_id):
        if search_id not in self.image_searches:
            return
        if self.active_image_search_id != search_id:
            self.unload_active_image_view()
        key = self.image_view_key(search_id)
        web_view = self.web_views.get(key)
        if web_view is None:
            web_view = self.create_image_view(search_id)
        self.active_image_search_id = search_id
        self.current_tab = "images"
        self.download_btn.hide()
        self.tabs.setCurrentWidget(web_view)
        web_view.setZoomFactor(0.8)
        self.setWindowTitle(
            f"PremieDrop Images - {self.image_searches[search_id]['label']}"
        )
        self.update_tab_button_styles()

    def rebuild_images_menu(self):
        self.images_menu.clear()
        website_action = self.images_menu.addAction("Search Website")
        website_action.triggered.connect(self.search_website)
        image_action = self.images_menu.addAction("Search Images")
        image_action.triggered.connect(self.search_images)
        self.images_menu.addSeparator()
        save_preset_action = self.images_menu.addAction("Save Preset")
        save_preset_action.triggered.connect(
            self.save_current_website_preset
        )
        self.load_preset_menu = self.images_menu.addMenu("Load Preset")
        self.load_preset_menu.setContextMenuPolicy(Qt.CustomContextMenu)
        self.load_preset_menu.customContextMenuRequested.connect(
            self.show_preset_context_menu
        )
        self.rebuild_preset_menu()
        self.images_menu.addSeparator()
        for website_id, website in self.website_searches.items():
            domain = urlparse(website["url"]).netloc or "website"
            label = website["label"]
            if len(label) > 28:
                label = f"{label[:25]}..."
            action = self.images_menu.addAction(
                f"{label} — {domain}"
            )
            action.setToolTip(website["url"])
            action.setProperty("saved_kind", "website")
            action.setProperty("saved_id", website_id)
            action.triggered.connect(
                lambda _checked=False, sid=website_id:
                self.open_saved_website(sid)
            )
        if self.website_searches and self.image_searches:
            self.images_menu.addSeparator()
        for search_id, search in self.image_searches.items():
            domain = urlparse(search["url"]).netloc or "images"
            label = search["label"]
            if len(label) > 28:
                label = f"{label[:25]}..."
            action = self.images_menu.addAction(
                f"{label} — {domain}"
            )
            action.setToolTip(search["url"])
            action.setProperty("saved_kind", "image")
            action.setProperty("saved_id", search_id)
            action.triggered.connect(
                lambda _checked=False, sid=search_id:
                self.open_saved_image_search(sid)
            )
        if self.website_searches or self.image_searches:
            self.images_menu.addSeparator()
        new_action = self.images_menu.addAction("+ New Image Search")
        new_action.triggered.connect(self.search_images)

    def show_saved_site_context_menu(self, position):
        action = self.images_menu.actionAt(position)
        if action is None:
            return
        saved_kind = action.property("saved_kind")
        saved_id = action.property("saved_id")
        if saved_kind not in ("website", "image") or saved_id is None:
            return
        menu = QMenu(self.images_menu)
        delete_action = menu.addAction("Delete")
        chosen = menu.exec_(self.images_menu.mapToGlobal(position))
        if chosen != delete_action:
            return
        if saved_kind == "website":
            self.delete_saved_website(int(saved_id))
        else:
            self.delete_saved_image_search(int(saved_id))

    def delete_saved_website(self, website_id):
        if website_id not in self.website_searches:
            return
        del self.website_searches[website_id]
        if self.active_website_search_id == website_id:
            self.active_website_search_id = None
            self.web_views["search"].setUrl(
                QUrl(self.sites["search"]["url"])
            )
        self.save_browser_state()

    def delete_saved_image_search(self, search_id):
        if search_id not in self.image_searches:
            return
        if self.active_image_search_id == search_id:
            self.unload_active_image_view()
            self.switch_tab("search")
        self.image_searches.pop(search_id, None)

    def load_browser_state(self):
        try:
            with open(
                self.browser_presets_path, "r", encoding="utf-8"
            ) as state_file:
                state = json.load(state_file)
        except (OSError, ValueError, TypeError):
            return
        for website in state.get("websites", []):
            label = str(website.get("label", "")).strip()
            url = str(website.get("url", "")).strip()
            if not label or not url:
                continue
            website_id = self.next_website_search_id
            self.next_website_search_id += 1
            self.website_searches[website_id] = {
                "label": label,
                "url": url,
            }
        self.browser_presets = [
            {
                "name": str(preset.get("name", "")).strip(),
                "url": str(preset.get("url", "")).strip(),
            }
            for preset in state.get("presets", [])
            if preset.get("name") and preset.get("url")
        ]

    def save_browser_state(self):
        os.makedirs(os.path.dirname(self.browser_presets_path), exist_ok=True)
        temporary_path = f"{self.browser_presets_path}.tmp"
        state = {
            "websites": list(self.website_searches.values()),
            "presets": self.browser_presets,
        }
        try:
            with open(
                temporary_path, "w", encoding="utf-8"
            ) as state_file:
                json.dump(state, state_file, indent=2)
            os.replace(temporary_path, self.browser_presets_path)
        except OSError:
            pass

    def save_current_website_preset(self):
        view = self.current_web_view()
        if view is None:
            return
        url = view.url().toString()
        if not url or url == "about:blank":
            QMessageBox.information(
                self, "Nothing to Save", "Open a website first."
            )
            return
        default_name = f"Preset {len(self.browser_presets) + 1}"
        name, accepted = QInputDialog.getText(
            self,
            "Save Website Preset",
            "Preset name:",
            QLineEdit.Normal,
            default_name,
        )
        name = name.strip()
        if not accepted:
            return
        if not name:
            name = default_name
        existing = next(
            (
                preset for preset in self.browser_presets
                if preset["name"].casefold() == name.casefold()
            ),
            None,
        )
        if existing is None:
            self.browser_presets.append({"name": name, "url": url})
        else:
            existing["name"] = name
            existing["url"] = url
        self.save_browser_state()

    def rebuild_preset_menu(self):
        self.load_preset_menu.clear()
        if not self.browser_presets:
            empty_action = self.load_preset_menu.addAction(
                "No saved presets yet"
            )
            empty_action.setEnabled(False)
            return
        for index, preset in enumerate(self.browser_presets):
            action = self.load_preset_menu.addAction(preset["name"])
            action.setToolTip(preset["url"])
            action.setProperty("preset_index", index)
            action.triggered.connect(
                lambda _checked=False, preset_index=index:
                self.load_website_preset(preset_index)
            )

    def load_website_preset(self, preset_index):
        if not 0 <= preset_index < len(self.browser_presets):
            return
        preset = self.browser_presets[preset_index]
        website_id = self.next_website_search_id
        self.next_website_search_id += 1
        self.website_searches[website_id] = {
            "label": preset["name"],
            "url": preset["url"],
        }
        self.save_browser_state()
        self.open_saved_website(website_id)

    def show_preset_context_menu(self, position):
        action = self.load_preset_menu.actionAt(position)
        if action is None:
            return
        preset_index = action.property("preset_index")
        if preset_index is None:
            return
        menu = QMenu(self.load_preset_menu)
        delete_action = menu.addAction("Delete Preset")
        chosen = menu.exec_(self.load_preset_menu.mapToGlobal(position))
        if chosen != delete_action:
            return
        preset_index = int(preset_index)
        if 0 <= preset_index < len(self.browser_presets):
            self.browser_presets.pop(preset_index)
            self.save_browser_state()

    def switch_tab(self, tab_name):
        if tab_name not in self.sites:
            return
        if self.current_tab == "images":
            self.unload_active_image_view()
        if tab_name != "search":
            self.active_website_search_id = None
        self.current_tab = tab_name
        self.download_btn.setVisible(tab_name == "youtube")
        self.tabs.setCurrentWidget(self.web_views[tab_name])
        site_name = self.sites[tab_name]["name"]
        self.setWindowTitle(f"PremieDrop - {site_name}")
        self.update_tab_button_styles()

    def update_tab_button_styles(self):
        self.youtube_tab_btn.setProperty(
            "active", self.current_tab == "youtube"
        )
        self.myinstants_tab_btn.setProperty(
            "active", self.current_tab == "myinstants"
        )
        self.images_tab_btn.setProperty(
            "active", self.current_tab == "images"
        )
        for button in (
            self.youtube_tab_btn,
            self.myinstants_tab_btn,
            self.images_tab_btn,
        ):
            button.style().unpolish(button)
            button.style().polish(button)

    def check_browser_command(self):
        if not os.path.isfile(self.command_path):
            return
        try:
            with open(
                self.command_path, "r", encoding="utf-8"
            ) as command_file:
                command = json.load(command_file)
            os.remove(self.command_path)
        except (OSError, ValueError):
            return
        tab_name = command.get("tab", "")
        self.attached = True
        self.attach_btn.setText("Pop Out")
        self.show()
        self.raise_()
        self.activateWindow()
        self.publish_attachment_status()
        QTimer.singleShot(100, self.sync_with_premiedrop)
        if command.get("search_website"):
            QTimer.singleShot(0, self.search_website)
        elif command.get("search_images"):
            if self.image_searches:
                latest_search_id = max(self.image_searches)
                QTimer.singleShot(
                    0,
                    lambda sid=latest_search_id:
                    self.open_saved_image_search(sid)
                )
            else:
                QTimer.singleShot(0, self.search_images)
        else:
            self.switch_tab(tab_name)

    def hide_browser_panel(self):
        if self.current_tab == "images":
            self.unload_active_image_view()
        self.hide()
        self.attached = False
        self.attach_btn.setText("Attach to PremieDrop")
        self.publish_attachment_status()

    def closeEvent(self, event):
        event.ignore()
        self.hide_browser_panel()

    def send_download_request(
        self, url=None, request_type="", suggested_filename="",
        mime_type="", referer=""
    ):
        if not isinstance(url, str) or not url:
            url = self.current_web_view().url().toString()
        QApplication.clipboard().setText(url)
        cursor_position = QCursor.pos()
        request_dir = os.path.dirname(self.request_path)
        os.makedirs(request_dir, exist_ok=True)
        temporary_path = f"{self.request_path}.tmp"
        request = {
            "url": url,
            "request_type": request_type,
            "suggested_filename": suggested_filename,
            "mime_type": mime_type,
            "referer": referer,
            "cursor_x": cursor_position.x(),
            "cursor_y": cursor_position.y(),
            "created_at": time.time(),
        }
        try:
            with open(temporary_path, "w", encoding="utf-8") as request_file:
                json.dump(request, request_file)
            os.replace(temporary_path, self.request_path)
        except OSError as exc:
            QMessageBox.warning(
                self,
                "Could Not Send URL",
                f"PremieDrop could not receive this URL:\n\n{exc}"
            )

    def handle_browser_download(self, download_item):
        url = download_item.url().toString()
        suggested_filename = download_item.suggestedFileName()
        mime_type = download_item.mimeType()
        page = download_item.page()
        referer = page.url().toString() if page is not None else ""
        download_item.cancel()
        self.send_download_request(
            url,
            request_type="direct",
            suggested_filename=suggested_filename,
            mime_type=mime_type,
            referer=referer,
        )

    def toggle_attachment(self):
        self.attached = not self.attached
        self.attach_btn.setText(
            "Pop Out" if self.attached else "Attach to PremieDrop"
        )
        if self.attached:
            self.publish_attachment_status()
            QTimer.singleShot(100, self.sync_with_premiedrop)
        else:
            self.pop_out()
            self.publish_attachment_status()

    def sync_with_premiedrop(self):
        if not self.attached:
            return
        try:
            with open(
                self.dock_state_path, "r", encoding="utf-8"
            ) as state_file:
                state = json.load(state_file)
            parent_hwnd = int(state["parent_hwnd"])
            x = int(state["x"])
            y = int(state["y"])
            width = int(state["width"])
            height = int(state["height"])
            host_attached = bool(state.get("attached"))
        except (OSError, ValueError, KeyError, TypeError):
            append_log(self.log_path, "Browser sync skipped: dock state unavailable")
            return

        if not host_attached or width < 100 or height < 100:
            append_log(
                self.log_path,
                "Browser sync skipped: "
                f"attached={host_attached} width={width} height={height}",
            )
            return

        try:
            if os.name == "nt":
                self.attach_to_native_parent(parent_hwnd, x, y, width, height)
            else:
                self.setGeometry(x, y, width, height)
            append_log(
                self.log_path,
                f"Browser synced: parent={parent_hwnd} width={width} height={height}",
            )
        except Exception as exc:
            append_log(self.log_path, f"Browser sync failed: {exc!r}")

    def attach_to_native_parent(self, parent_hwnd, x, y, width, height):
        if not parent_hwnd:
            return
        user32 = windows_api()

        if not self.qt_frameless:
            self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
            self.show()
            QApplication.processEvents()
            self.qt_frameless = True

        hwnd = int(self.winId())
        SWP_FRAMECHANGED = 0x0020
        SWP_SHOWWINDOW = 0x0040

        # Qt WebEngine can disappear after loading when its top-level window is
        # force-reparented with SetParent. Keep it top-level and dock by geometry.
        if not user32.SetWindowPos(
            hwnd, 0, x, y, width, height,
            SWP_FRAMECHANGED | SWP_SHOWWINDOW
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        self.native_parent_hwnd = 0

    def pop_out(self):
        if os.name != "nt":
            return
        user32 = windows_api()
        hwnd = int(self.winId())
        GWL_STYLE = -16
        WS_CHILD = 0x40000000
        WS_OVERLAPPEDWINDOW = 0x00CF0000
        SWP_FRAMECHANGED = 0x0020
        SWP_SHOWWINDOW = 0x0040
        position = QCursor.pos()

        user32.SetParent(hwnd, 0)
        style = user32.GetWindowLongW(hwnd, GWL_STYLE)
        style &= ~WS_CHILD
        style |= WS_OVERLAPPEDWINDOW
        user32.SetWindowLongW(hwnd, GWL_STYLE, style)
        user32.SetWindowPos(
            hwnd, 0, position.x(), position.y(), 900, 700,
            SWP_FRAMECHANGED | SWP_SHOWWINDOW
        )
        self.native_parent_hwnd = 0
        self.setWindowFlags(Qt.Window)
        self.show()
        self.resize(900, 700)
        self.move(position)
        QApplication.processEvents()
        self.qt_frameless = False

    def publish_attachment_status(self):
        status_dir = os.path.dirname(self.status_path)
        os.makedirs(status_dir, exist_ok=True)
        temporary_path = f"{self.status_path}.tmp"
        try:
            with open(temporary_path, "w", encoding="utf-8") as status_file:
                json.dump({"attached": self.attached}, status_file)
            os.replace(temporary_path, self.status_path)
        except OSError:
            pass

    def update_page_title(self, tab_name, title):
        if tab_name != self.current_tab:
            return
        site_name = self.sites[tab_name]["name"]
        self.setWindowTitle(
            f"{title} - PremieDrop {site_name}" if title
            else f"PremieDrop - {site_name}"
        )

    def update_image_page_title(self, search_id, title):
        if (
            self.current_tab != "images"
            or self.active_image_search_id != search_id
        ):
            return
        label = self.image_searches[search_id]["label"]
        self.setWindowTitle(
            f"{title} - PremieDrop Images" if title
            else f"PremieDrop Images - {label}"
        )


def main():
    if len(sys.argv) < 9:
        return 1

    log_path = sys.argv[4]
    command_path = sys.argv[5]
    initial_tab = sys.argv[6]
    youtube_url = sys.argv[7]
    myinstants_url = sys.argv[8]
    try:
        if os.path.isfile(log_path):
            os.remove(log_path)
    except OSError:
        pass
    append_log(log_path, "Media browser helper starting")

    def log_unhandled_exception(exc_type, exc_value, exc_traceback):
        details = "".join(traceback.format_exception(
            exc_type, exc_value, exc_traceback
        ))
        append_log(log_path, f"Unhandled exception:\n{details}")
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = log_unhandled_exception

    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    import_error = None
    try:
        from PyQt5.QtWebEngineWidgets import (
            QWebEngineContextMenuData,
            QWebEngineView,
        )
    except (ImportError, OSError) as exc:
        import_error = exc
        QWebEngineView = None

    app = QApplication(sys.argv)
    app.setApplicationName("PremieDrop Media Browser")
    app.setStyle("Fusion")

    if import_error is not None:
        append_log(log_path, f"WebEngine import failed: {import_error}")
        QMessageBox.critical(
            None,
            "PyQtWebEngine Required",
            "The media browser needs PyQtWebEngine.\n\n"
            "Install it with:\n"
            "python -m pip install PyQtWebEngine\n\n"
            f"Details: {import_error}"
        )
        return 1

    class PremieDropWebView(QWebEngineView):
        def contextMenuEvent(self, event):
            context_data = self.page().contextMenuData()
            link_url = context_data.linkUrl().toString()
            media_url = context_data.mediaUrl().toString()
            target_url = link_url or media_url
            is_image = (
                context_data.mediaType()
                == QWebEngineContextMenuData.MediaTypeImage
                and bool(media_url)
            )
            menu = self.page().createStandardContextMenu()
            menu.setStyleSheet("""
                QMenu {
                    background-color: #16213e;
                    color: #eeeeff;
                    border: 1px solid #51517f;
                    padding: 5px;
                }
                QMenu::item {
                    min-width: 220px;
                    padding: 8px 24px 8px 12px;
                    border-radius: 5px;
                }
                QMenu::item:selected {
                    background-color: #6C63FF;
                    color: #ffffff;
                    font-weight: bold;
                }
                QMenu::item:disabled {
                    color: #666680;
                }
                QMenu::separator {
                    height: 1px;
                    background-color: #45456f;
                    margin: 5px 8px;
                }
            """)
            for action in list(menu.actions()):
                if action.text().lower().startswith("save image"):
                    menu.removeAction(action)

            save_image_action = None
            if is_image:
                image_filename = os.path.basename(
                    urlparse(media_url).path
                )
                image_mime = (
                    mimetypes.guess_type(image_filename)[0] or "image/"
                )
                save_image_action = QAction("Save Image", menu)
                save_image_action.triggered.connect(
                    lambda _checked=False, url=media_url,
                    filename=image_filename, mime=image_mime:
                    self.window().send_download_request(
                        url,
                        request_type="direct",
                        suggested_filename=filename,
                        mime_type=mime,
                        referer=self.url().toString(),
                    )
                )

            copy_action = QAction("Copy URL to PremieDrop", menu)
            copy_action.setEnabled(bool(target_url))
            copy_action.triggered.connect(
                lambda _checked=False, url=target_url,
                direct=bool(media_url) or self.property("tab_name") == "images":
                self.window().send_download_request(
                    url,
                    request_type="direct" if direct else "",
                    suggested_filename=os.path.basename(
                        urlparse(url).path
                    ),
                    referer=self.url().toString(),
                )
            )
            first_action = menu.actions()[0] if menu.actions() else None
            if save_image_action is not None and first_action is not None:
                menu.insertAction(first_action, save_image_action)
                menu.insertAction(first_action, copy_action)
                menu.insertSeparator(first_action)
            elif save_image_action is not None:
                menu.addAction(save_image_action)
                menu.addAction(copy_action)
            elif first_action is None:
                menu.addAction(copy_action)
            else:
                menu.insertAction(first_action, copy_action)
                menu.insertSeparator(first_action)
            menu.exec_(event.globalPos())
            menu.deleteLater()

    window = YouTubeBrowserWindow(
        PremieDropWebView, sys.argv[1], sys.argv[2], sys.argv[3],
        log_path, command_path, initial_tab, youtube_url, myinstants_url
    )
    window.show()
    append_log(log_path, f"Browser window created: hwnd={int(window.winId())}")
    QTimer.singleShot(0, window.sync_with_premiedrop)
    result = app.exec_()
    append_log(log_path, f"Media browser helper exiting: code={result}")
    return result


if __name__ == "__main__":
    sys.exit(main())

import ctypes
from ctypes import wintypes
import json
import os
import sys
import time
import traceback
from urllib.parse import quote_plus

from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QHBoxLayout,
    QInputDialog,
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
        self.sites = {
            "youtube": {
                "name": "YouTube",
                "url": youtube_url,
            },
            "myinstants": {
                "name": "MyInstants",
                "url": myinstants_url,
            },
            "images": {
                "name": "Images",
                "url": "about:blank",
            },
        }
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
            QPushButton#youtube_home:hover,
            QPushButton#myinstants_home:hover,
            QPushButton#images_home:hover,
            QPushButton#youtube_download:hover,
            QPushButton#attach_toggle:hover {
                background-color: #6C63FF;
                color: #ffffff;
                border: 2px solid #ffffff;
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
        self.images_tab_btn.setToolTip("Search images")
        self.images_tab_btn.setFixedWidth(42)
        self.images_tab_btn.clicked.connect(self.search_images)
        controls.addWidget(self.images_tab_btn)

        self.attach_btn = QPushButton("Pop Out")
        self.attach_btn.setObjectName("attach_toggle")
        self.attach_btn.clicked.connect(self.toggle_attachment)
        controls.addWidget(self.attach_btn)

        controls.addStretch()

        download_btn = QPushButton("Download Current URL")
        download_btn.setObjectName("youtube_download")
        download_btn.clicked.connect(self.send_download_request)
        controls.addWidget(download_btn)
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
            if tab_name == "images":
                web_view.setZoomFactor(0.8)
                web_view.loadFinished.connect(
                    lambda _ok, view=web_view: view.setZoomFactor(0.8)
                )
            self.web_views[tab_name] = web_view
            self.tabs.addWidget(web_view)
        layout.addWidget(self.tabs, 1)

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

    def current_web_view(self):
        return self.web_views[self.current_tab]

    def go_back(self):
        self.current_web_view().back()

    def go_forward(self):
        self.current_web_view().forward()

    def reload_page(self):
        self.current_web_view().reload()

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
        self.web_views["images"].setUrl(QUrl(search_url))
        self.switch_tab("images")

    def switch_tab(self, tab_name):
        if tab_name not in self.web_views:
            return
        self.current_tab = tab_name
        self.tabs.setCurrentWidget(self.web_views[tab_name])
        if tab_name == "images":
            self.web_views["images"].setZoomFactor(0.8)
        site_name = self.sites[tab_name]["name"]
        self.setWindowTitle(f"PremieDrop - {site_name}")
        self.youtube_tab_btn.setProperty(
            "active", tab_name == "youtube"
        )
        self.myinstants_tab_btn.setProperty(
            "active", tab_name == "myinstants"
        )
        self.images_tab_btn.setProperty(
            "active", tab_name == "images"
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
        self.switch_tab(command.get("tab", ""))

    def send_download_request(self, url=None):
        if not isinstance(url, str) or not url:
            url = self.current_web_view().url().toString()
        QApplication.clipboard().setText(url)
        cursor_position = QCursor.pos()
        request_dir = os.path.dirname(self.request_path)
        os.makedirs(request_dir, exist_ok=True)
        temporary_path = f"{self.request_path}.tmp"
        request = {
            "url": url,
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
            return

        if not host_attached or width < 100 or height < 100:
            return

        if os.name == "nt":
            self.attach_to_native_parent(parent_hwnd, width, height)
        else:
            self.setGeometry(x, y, width, height)

    def attach_to_native_parent(self, parent_hwnd, width, height):
        if not parent_hwnd:
            return
        user32 = windows_api()

        if not self.qt_frameless:
            self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
            self.show()
            QApplication.processEvents()
            self.qt_frameless = True

        hwnd = int(self.winId())
        GWL_STYLE = -16
        WS_CHILD = 0x40000000
        WS_POPUP = 0x80000000
        WS_CAPTION = 0x00C00000
        WS_THICKFRAME = 0x00040000
        WS_MINIMIZEBOX = 0x00020000
        WS_MAXIMIZEBOX = 0x00010000
        WS_SYSMENU = 0x00080000
        SWP_FRAMECHANGED = 0x0020
        SWP_SHOWWINDOW = 0x0040

        if self.native_parent_hwnd != parent_hwnd:
            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            style &= ~(
                WS_POPUP
                | WS_CAPTION
                | WS_THICKFRAME
                | WS_MINIMIZEBOX
                | WS_MAXIMIZEBOX
                | WS_SYSMENU
            )
            style |= WS_CHILD
            ctypes.set_last_error(0)
            user32.SetWindowLongW(hwnd, GWL_STYLE, style)
            error_code = ctypes.get_last_error()
            if error_code:
                raise ctypes.WinError(error_code)
            ctypes.set_last_error(0)
            user32.SetParent(hwnd, parent_hwnd)
            error_code = ctypes.get_last_error()
            if error_code:
                raise ctypes.WinError(error_code)
            self.native_parent_hwnd = parent_hwnd

        if not user32.SetWindowPos(
            hwnd, 0, 0, 0, width, height,
            SWP_FRAMECHANGED | SWP_SHOWWINDOW
        ):
            raise ctypes.WinError(ctypes.get_last_error())

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
        from PyQt5.QtWebEngineWidgets import QWebEngineView
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
            target_url = (
                context_data.linkUrl().toString()
                or context_data.mediaUrl().toString()
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
            copy_action = QAction("Copy URL to PremieDrop", menu)
            copy_action.setEnabled(bool(target_url))
            copy_action.triggered.connect(
                lambda _checked=False, url=target_url:
                self.window().send_download_request(url)
            )
            first_action = menu.actions()[0] if menu.actions() else None
            if first_action is None:
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

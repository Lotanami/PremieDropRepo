import json
import os
import sys
import time

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


HOME_URL = "https://www.youtube.com/"


class YouTubeBrowserWindow(QWidget):
    def __init__(self, web_view_class, request_path):
        super().__init__()
        self.request_path = request_path
        self.setWindowTitle("PremieDrop - YouTube")
        self.resize(1100, 760)
        self.setMinimumSize(760, 520)
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
                background-color: #343463;
                border-color: #6C63FF;
            }
            QPushButton#youtube_home {
                background-color: #b3261e;
                border-color: #e0443a;
                font-weight: bold;
            }
            QPushButton#youtube_download {
                background-color: #1a6b3a;
                border-color: #288c50;
                font-weight: bold;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(7)

        controls = QHBoxLayout()
        controls.setSpacing(6)

        back_btn = QPushButton("Back")
        back_btn.clicked.connect(self.go_back)
        controls.addWidget(back_btn)

        forward_btn = QPushButton("Forward")
        forward_btn.clicked.connect(self.go_forward)
        controls.addWidget(forward_btn)

        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self.reload_page)
        controls.addWidget(reload_btn)

        home_btn = QPushButton("YouTube")
        home_btn.setObjectName("youtube_home")
        home_btn.clicked.connect(self.go_home)
        controls.addWidget(home_btn)

        controls.addStretch()

        download_btn = QPushButton("Download Current URL")
        download_btn.setObjectName("youtube_download")
        download_btn.clicked.connect(self.send_download_request)
        controls.addWidget(download_btn)
        layout.addLayout(controls)

        self.web_view = web_view_class(self)
        self.web_view.titleChanged.connect(self.update_page_title)
        self.web_view.setUrl(QUrl(HOME_URL))
        layout.addWidget(self.web_view, 1)

    def go_back(self):
        self.web_view.back()

    def go_forward(self):
        self.web_view.forward()

    def reload_page(self):
        self.web_view.reload()

    def go_home(self):
        self.web_view.setUrl(QUrl(HOME_URL))

    def send_download_request(self):
        request_dir = os.path.dirname(self.request_path)
        os.makedirs(request_dir, exist_ok=True)
        temporary_path = f"{self.request_path}.tmp"
        request = {
            "url": self.web_view.url().toString(),
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

    def update_page_title(self, title):
        self.setWindowTitle(
            f"{title} - PremieDrop YouTube" if title
            else "PremieDrop - YouTube"
        )


def main():
    if len(sys.argv) < 2:
        return 1

    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    import_error = None
    try:
        from PyQt5.QtWebEngineWidgets import QWebEngineView
    except (ImportError, OSError) as exc:
        import_error = exc
        QWebEngineView = None

    app = QApplication(sys.argv)
    app.setApplicationName("PremieDrop YouTube")
    app.setStyle("Fusion")

    if import_error is not None:
        QMessageBox.critical(
            None,
            "PyQtWebEngine Required",
            "The YouTube browser needs PyQtWebEngine.\n\n"
            "Install it with:\n"
            "python -m pip install PyQtWebEngine\n\n"
            f"Details: {import_error}"
        )
        return 1

    window = YouTubeBrowserWindow(QWebEngineView, sys.argv[1])
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())

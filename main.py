import sys
import os
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QFileDialog,
    QAbstractItemView, QMenu, QAction, QMessageBox, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, QMimeData, QUrl, QSize
from PyQt5.QtGui import QIcon, QColor, QFont, QDrag, QPalette, QPixmap

SAVE_FILE = os.path.join(os.path.dirname(__file__), "saved_files.json")

SUPPORTED_EXTENSIONS = {
    "video": [".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v"],
    "audio": [".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".aiff"],
    "image": [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff"],
}

ALL_EXTENSIONS = [ext for exts in SUPPORTED_EXTENSIONS.values() for ext in exts]

def get_file_type(path):
    ext = os.path.splitext(path)[1].lower()
    for ftype, exts in SUPPORTED_EXTENSIONS.items():
        if ext in exts:
            return ftype
    return "other"

def get_file_icon(ftype):
    icons = {
        "video": "🎬",
        "audio": "🎵",
        "image": "🖼️",
        "other": "📄",
    }
    return icons.get(ftype, "📄")

def load_saved_files():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r") as f:
                data = json.load(f)
                return data.get("saved_files", [])
        except Exception:
            return []
    return []

def save_files(file_list):
    with open(SAVE_FILE, "w") as f:
        json.dump({"saved_files": file_list}, f, indent=2)


class DraggableList(QListWidget):
    """A list widget that supports dragging files OUT to other applications."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.CopyAction)

    def startDrag(self, supported_actions):
        selected = self.selectedItems()
        if not selected:
            return

        paths = []
        for item in selected:
            path = item.data(Qt.UserRole)
            if path and os.path.exists(path):
                paths.append(path)

        if not paths:
            return

        mime = QMimeData()
        urls = [QUrl.fromLocalFile(p) for p in paths]
        mime.setUrls(urls)

        drag = QDrag(self)
        drag.setMimeData(mime)

        # Show how many files are being dragged
        if len(paths) == 1:
            label = os.path.basename(paths[0])
        else:
            label = f"{len(paths)} files"

        pixmap = QPixmap(200, 30)
        pixmap.fill(QColor("#6C63FF"))
        drag.setPixmap(pixmap)
        drag.setHotSpot(pixmap.rect().center())

        drag.exec_(Qt.CopyAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            urls = event.mimeData().urls()
            paths = [url.toLocalFile() for url in urls]
            # Signal to the main window
            main = self.window()
            if hasattr(main, "add_files"):
                main.add_files(paths)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.saved_files = load_saved_files()
        self.init_ui()
        self.populate_list()

    def init_ui(self):
        self.setWindowTitle("PremieDrop")
        self.setMinimumSize(400, 580)
        self.resize(420, 640)
        self.setAcceptDrops(True)

        # ── Dark theme ──────────────────────────────────────────────
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a2e;
            }
            QWidget#central {
                background-color: #1a1a2e;
            }
            QLabel#title {
                color: #ffffff;
                font-size: 20px;
                font-weight: bold;
                letter-spacing: 1px;
            }
            QLabel#subtitle {
                color: #8888aa;
                font-size: 11px;
            }
            QLabel#drop_hint {
                color: #555577;
                font-size: 12px;
                padding: 8px;
            }
            QListWidget {
                background-color: #16213e;
                border: 2px dashed #2a2a4a;
                border-radius: 10px;
                color: #ccccee;
                font-size: 12px;
                padding: 4px;
                outline: none;
            }
            QListWidget::item {
                padding: 10px 8px;
                border-radius: 6px;
                margin: 2px 0px;
            }
            QListWidget::item:selected {
                background-color: #6C63FF;
                color: #ffffff;
            }
            QListWidget::item:hover {
                background-color: #22224a;
            }
            QPushButton#add_btn {
                background-color: #6C63FF;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton#add_btn:hover {
                background-color: #5a52e0;
            }
            QPushButton#add_btn:pressed {
                background-color: #4a43c0;
            }
            QPushButton#clear_btn {
                background-color: transparent;
                color: #8888aa;
                border: 1px solid #2a2a4a;
                border-radius: 8px;
                padding: 10px 16px;
                font-size: 13px;
            }
            QPushButton#clear_btn:hover {
                background-color: #22224a;
                color: #ffffff;
            }
            QFrame#divider {
                color: #2a2a4a;
            }
            QLabel#count_label {
                color: #6C63FF;
                font-size: 11px;
                font-weight: bold;
            }
            QLabel#drag_tip {
                color: #44446a;
                font-size: 11px;
                font-style: italic;
            }
        """)

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # ── Header ───────────────────────────────────────────────────
        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)

        title = QLabel("🎬 PremieDrop")
        title.setObjectName("title")
        subtitle = QLabel("Your media, one drag away")
        subtitle.setObjectName("subtitle")

        title_col.addWidget(title)
        title_col.addWidget(subtitle)

        self.count_label = QLabel("")
        self.count_label.setObjectName("count_label")
        self.count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        header.addLayout(title_col)
        header.addStretch()
        header.addWidget(self.count_label)
        layout.addLayout(header)

        # ── Divider ───────────────────────────────────────────────────
        line = QFrame()
        line.setObjectName("divider")
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #2a2a4a; border: none; max-height: 1px;")
        layout.addWidget(line)

        # ── Drop hint ────────────────────────────────────────────────
        drop_hint = QLabel("⬇  Drop files here or use Add Files button")
        drop_hint.setObjectName("drop_hint")
        drop_hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(drop_hint)

        # ── File list ────────────────────────────────────────────────
        self.file_list = DraggableList()
        self.file_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.file_list)

        # ── Drag out tip ────────────────────────────────────────────
        drag_tip = QLabel("✦  Select files above and drag them into Premiere Pro")
        drag_tip.setObjectName("drag_tip")
        drag_tip.setAlignment(Qt.AlignCenter)
        layout.addWidget(drag_tip)

        # ── Buttons ──────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        add_btn = QPushButton("＋  Add Files")
        add_btn.setObjectName("add_btn")
        add_btn.clicked.connect(self.browse_files)
        add_btn.setFixedHeight(42)

        clear_btn = QPushButton("Clear All")
        clear_btn.setObjectName("clear_btn")
        clear_btn.clicked.connect(self.clear_all)
        clear_btn.setFixedHeight(42)
        clear_btn.setFixedWidth(100)

        btn_row.addWidget(add_btn)
        btn_row.addWidget(clear_btn)
        layout.addLayout(btn_row)

    # ── File management ──────────────────────────────────────────────

    def add_files(self, paths):
        added = 0
        for path in paths:
            path = os.path.normpath(path)
            ext = os.path.splitext(path)[1].lower()
            if ext not in ALL_EXTENSIONS:
                continue
            if path not in self.saved_files:
                self.saved_files.append(path)
                added += 1
        if added:
            save_files(self.saved_files)
            self.populate_list()

    def browse_files(self):
        exts = " ".join(f"*{e}" for e in ALL_EXTENSIONS)
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Media Files",
            "",
            f"Media Files ({exts});;All Files (*.*)"
        )
        if paths:
            self.add_files(paths)

    def populate_list(self):
        self.file_list.clear()
        valid = []
        for path in self.saved_files:
            if not os.path.exists(path):
                continue  # skip missing files silently
            valid.append(path)
            ftype = get_file_type(path)
            icon = get_file_icon(ftype)
            name = os.path.basename(path)
            folder = os.path.basename(os.path.dirname(path))
            size = os.path.getsize(path)
            size_str = self.human_size(size)

            item = QListWidgetItem()
            item.setText(f"{icon}  {name}\n     {folder}  ·  {size_str}")
            item.setData(Qt.UserRole, path)
            item.setToolTip(path)
            self.file_list.addItem(item)

        # Update saved list to remove missing files
        if len(valid) != len(self.saved_files):
            self.saved_files = valid
            save_files(self.saved_files)

        count = len(valid)
        self.count_label.setText(f"{count} file{'s' if count != 1 else ''}")

    def human_size(self, size):
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def clear_all(self):
        if not self.saved_files:
            return
        reply = QMessageBox.question(
            self, "Clear All",
            "Remove all files from the list?\n(Your actual files won't be deleted)",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.saved_files = []
            save_files(self.saved_files)
            self.populate_list()

    # ── Context menu ─────────────────────────────────────────────────

    def show_context_menu(self, pos):
        item = self.file_list.itemAt(pos)
        if not item:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #16213e;
                color: #ccccee;
                border: 1px solid #2a2a4a;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #6C63FF;
                color: white;
            }
        """)

        reveal_action = QAction("📂  Reveal in File Explorer", self)
        reveal_action.triggered.connect(lambda: self.reveal_file(item))

        remove_action = QAction("🗑  Remove from List", self)
        remove_action.triggered.connect(lambda: self.remove_item(item))

        menu.addAction(reveal_action)
        menu.addSeparator()
        menu.addAction(remove_action)
        menu.exec_(self.file_list.viewport().mapToGlobal(pos))

    def reveal_file(self, item):
        path = item.data(Qt.UserRole)
        if not path:
            return
        import subprocess, platform
        system = platform.system()
        if system == "Windows":
            subprocess.Popen(f'explorer /select,"{path}"')
        elif system == "Darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path)])

    def remove_item(self, item):
        path = item.data(Qt.UserRole)
        if path in self.saved_files:
            self.saved_files.remove(path)
            save_files(self.saved_files)
            self.populate_list()

    # ── App-level drag and drop (dropping onto the window) ───────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            paths = [url.toLocalFile() for url in event.mimeData().urls()]
            self.add_files(paths)
            event.acceptProposedAction()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PremieDrop")
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

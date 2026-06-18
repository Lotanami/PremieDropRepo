import sys
import os
import json
import shutil
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QFileDialog,
    QAbstractItemView, QMenu, QAction, QMessageBox, QFrame, QSizePolicy,
    QInputDialog
)
from PyQt5.QtCore import Qt, QMimeData, QUrl, QSize
from PyQt5.QtGui import QIcon, QColor, QFont, QDrag, QPalette, QPixmap

SAVE_FILE = os.path.join(os.path.dirname(__file__), "saved_files.json")
THUMB_SIZE = 48
LARGE_VIDEO_BYTES = 5 * 1024 * 1024 * 1024

DEFAULT_SECTIONS = [
    "Large Video Files (5Gb>)",
    "Short Video Files (1Gb<)",
    "Sound effects (.mp3 etc)",
    "Images/GIFs",
]

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

def get_image_thumbnail(path):
    """Load an image file as a scaled QIcon. Returns None on failure."""
    try:
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return None
        scaled = pixmap.scaled(
            THUMB_SIZE, THUMB_SIZE,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        return QIcon(scaled)
    except Exception:
        return None

def load_saved_files():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r") as f:
                data = json.load(f)
                return data.get("saved_files", [])
        except Exception:
            return []
    return []

def make_empty_sections():
    return [{"name": name, "files": []} for name in DEFAULT_SECTIONS]

def normalize_sections(sections):
    clean = []
    seen = set()
    for section in sections:
        name = str(section.get("name", "")).strip()
        if not name or name in seen:
            continue
        files = []
        for path in section.get("files", []):
            norm = os.path.normpath(path)
            if norm not in files:
                files.append(norm)
        clean.append({"name": name, "files": files})
        seen.add(name)
    for name in DEFAULT_SECTIONS:
        if name not in seen:
            clean.append({"name": name, "files": []})
    return clean

def section_for_file(path):
    ftype = get_file_type(path)
    if ftype == "audio":
        return "Sound effects (.mp3 etc)"
    if ftype == "image":
        return "Images/GIFs"
    if ftype == "video":
        try:
            if os.path.getsize(path) > LARGE_VIDEO_BYTES:
                return "Large Video Files (5Gb>)"
        except OSError:
            pass
        return "Short Video Files (1Gb<)"
    return DEFAULT_SECTIONS[1]

def safe_folder_name(name):
    invalid = '<>:"/\\|?*'
    cleaned = "".join("_" if char in invalid else char for char in name).strip()
    return cleaned.rstrip(". ") or "Section"

def load_sections():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r") as f:
                data = json.load(f)
            if "sections" in data:
                return normalize_sections(data.get("sections", []))
            sections = make_empty_sections()
            for path in data.get("saved_files", []):
                norm = os.path.normpath(path)
                target = section_for_file(norm)
                for section in sections:
                    if section["name"] == target:
                        section["files"].append(norm)
                        break
            return normalize_sections(sections)
        except Exception:
            pass
    return make_empty_sections()

def load_project_folder():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r") as f:
                data = json.load(f)
                return data.get("project_folder", "")
        except Exception:
            return ""
    return ""

def save_files(file_list, project_folder="", sections=None):
    existing = {}
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r") as f:
                existing = json.load(f)
        except Exception:
            pass
    existing["saved_files"] = file_list
    if sections is not None:
        existing["sections"] = sections
    if project_folder:
        existing["project_folder"] = project_folder
    with open(SAVE_FILE, "w") as f:
        json.dump(existing, f, indent=2)


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
            target_section = self.section_at(event.pos())
            # Signal to the main window
            main = self.window()
            if hasattr(main, "add_files"):
                main.add_files(paths, target_section)

    def section_at(self, pos):
        item = self.itemAt(pos)
        if item:
            section_name = item.data(Qt.UserRole + 1)
            if section_name:
                return section_name

        row = self.indexAt(pos).row()
        if row < 0:
            row = self.count() - 1
        for i in range(row, -1, -1):
            section_name = self.item(i).data(Qt.UserRole + 1)
            if section_name:
                return section_name
        return None


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.sections = load_sections()
        self.saved_files = self.all_files()
        self.project_folder = load_project_folder()
        self.init_ui()
        self.populate_list()

    def all_files(self):
        files = []
        for section in self.sections:
            for path in section["files"]:
                if path not in files:
                    files.append(path)
        return files

    def save_library(self):
        self.saved_files = self.all_files()
        save_files(self.saved_files, self.project_folder, self.sections)

    def find_section(self, section_name):
        for section in self.sections:
            if section["name"] == section_name:
                return section
        return None

    def add_drop_zone_item(self, section_name, height, text="Drop files here"):
        item = QListWidgetItem()
        item.setData(Qt.UserRole, None)
        item.setData(Qt.UserRole + 1, section_name)
        item.setFlags(Qt.NoItemFlags)
        item.setSizeHint(QSize(0, height))
        self.file_list.addItem(item)

        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("""
            QLabel {
                background-color: #181d38;
                color: #7777aa;
                border: 2px dashed #3a3a66;
                border-radius: 8px;
                margin: 5px 8px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        self.file_list.setItemWidget(item, label)
        return item

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "file_list"):
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
                padding: 6px 8px;
                border-radius: 6px;
                margin: 2px 0px;
                min-height: 48px;
            }
            QListWidget::item:selected {
                background-color: #6C63FF;
                color: #ffffff;
            }
            QListWidget::item:hover {
                background-color: #22224a;
            }
            QPushButton#section_btn {
                background-color: transparent;
                color: #ccccff;
                border: 1px solid #3a3a5a;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 13px;
            }
            QPushButton#section_btn:hover {
                background-color: #22224a;
                color: #ffffff;
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
            QPushButton#copy_btn {
                background-color: #1a6b3a;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton#copy_btn:hover {
                background-color: #1e8048;
            }
            QPushButton#copy_btn:pressed {
                background-color: #166030;
            }
            QPushButton#copy_btn:disabled {
                background-color: #1a2a20;
                color: #446655;
            }
            QPushButton#set_folder_btn {
                background-color: transparent;
                color: #8888aa;
                border: 1px solid #2a2a4a;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton#set_folder_btn:hover {
                background-color: #22224a;
                color: #ffffff;
            }
            QLabel#folder_label {
                color: #555577;
                font-size: 11px;
                font-style: italic;
            }
            QLabel#folder_label[active=true] {
                color: #44aa66;
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

        # ── Project folder section ───────────────────────────────────
        folder_line = QFrame()
        folder_line.setFrameShape(QFrame.HLine)
        folder_line.setStyleSheet("background-color: #2a2a4a; border: none; max-height: 1px;")
        layout.addWidget(folder_line)

        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)

        self.folder_label = QLabel("No project folder set")
        self.folder_label.setObjectName("folder_label")
        self.folder_label.setProperty("active", False)
        self.folder_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        set_folder_btn = QPushButton("📁  Set Folder")
        set_folder_btn.setObjectName("set_folder_btn")
        set_folder_btn.setFixedHeight(32)
        set_folder_btn.clicked.connect(self.set_project_folder)

        folder_row.addWidget(self.folder_label)
        folder_row.addWidget(set_folder_btn)
        layout.addLayout(folder_row)

        # ── Buttons ──────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        add_btn = QPushButton("＋  Add Files")
        add_btn.setObjectName("add_btn")
        add_btn.clicked.connect(self.browse_files)
        add_btn.setFixedHeight(42)

        section_btn = QPushButton("+ Section")
        section_btn.setObjectName("section_btn")
        section_btn.clicked.connect(self.add_section)
        section_btn.setFixedHeight(42)

        self.copy_btn = QPushButton("⬇  Import to Project bin")
        self.copy_btn.setObjectName("copy_btn")
        self.copy_btn.clicked.connect(self.copy_new_to_project)
        self.copy_btn.setFixedHeight(42)
        self.copy_btn.setText("Copy to Media Folder")

        clear_btn = QPushButton("Clear All")
        clear_btn.setObjectName("clear_btn")
        clear_btn.clicked.connect(self.clear_all)
        clear_btn.setFixedHeight(42)
        clear_btn.setFixedWidth(100)

        btn_row.addWidget(add_btn)
        btn_row.addWidget(section_btn)
        btn_row.addWidget(self.copy_btn)
        btn_row.addWidget(clear_btn)
        layout.addLayout(btn_row)

        # Set initial folder label state
        self.update_folder_label()

    # ── File management ──────────────────────────────────────────────

    def add_files(self, paths, target_section=None):
        added = 0
        for path in paths:
            path = os.path.normpath(path)
            ext = os.path.splitext(path)[1].lower()
            if ext not in ALL_EXTENSIONS:
                continue
            if path not in self.saved_files:
                section_name = target_section or section_for_file(path)
                section = self.find_section(section_name)
                if section is None:
                    section = self.sections[0]
                section["files"].append(path)
                added += 1
        if added:
            self.save_library()
            self.populate_list()

    def add_section(self):
        name, ok = QInputDialog.getText(self, "Add Section", "Section name:")
        if not ok:
            return
        name = name.strip()
        if not name:
            return
        if self.find_section(name):
            QMessageBox.information(self, "Section Exists", f'"{name}" already exists.')
            return
        self.sections.append({"name": name, "files": []})
        self.save_library()
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

    def set_project_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Premiere Pro Project Folder",
            self.project_folder or ""
        )
        if folder:
            self.project_folder = folder
            self.save_library()
            self.update_folder_label()

    def update_folder_label(self):
        if self.project_folder and os.path.exists(self.project_folder):
            name = os.path.basename(self.project_folder)
            self.folder_label.setText(f"→  {name}")
            self.folder_label.setToolTip(self.project_folder)
            self.folder_label.setStyleSheet("color: #44aa66; font-size: 11px;")
            self.copy_btn.setEnabled(True)
            self.copy_btn.setToolTip(f"Copy files into section folders inside: {name}")
        else:
            self.folder_label.setText("No project folder set")
            self.folder_label.setToolTip("")
            self.folder_label.setStyleSheet("color: #555577; font-size: 11px; font-style: italic;")
            self.copy_btn.setEnabled(False)
            self.copy_btn.setToolTip("")

    def copy_new_to_project(self):
        if not self.project_folder or not os.path.exists(self.project_folder):
            QMessageBox.warning(self, "No Folder Set", "Please set a project folder first.")
            return
        if not self.saved_files:
            QMessageBox.information(self, "Nothing to Copy", "Your file list is empty.")
            return

        new_files = []
        missing = []
        already_there = 0

        for section in self.sections:
            section_folder = os.path.join(self.project_folder, safe_folder_name(section["name"]))
            for path in section["files"]:
                if not os.path.exists(path):
                    missing.append(path)
                    continue
                dest = os.path.join(section_folder, os.path.basename(path))
                if os.path.exists(dest):
                    already_there += 1
                    continue
                new_files.append((path, dest))

        for section in self.sections:
            try:
                os.makedirs(
                    os.path.join(self.project_folder, safe_folder_name(section["name"])),
                    exist_ok=True
                )
            except Exception:
                pass

        if not new_files:
            if already_there:
                QMessageBox.information(
                    self, "Nothing New",
                    f"All {already_there} file{'s are' if already_there != 1 else ' is'} already in the section folders."
                )
            else:
                QMessageBox.information(self, "Nothing to Copy", "No files found to copy.")
            return

        copied, failed = 0, 0
        for path, dest in new_files:
            try:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(path, dest)
                copied += 1
            except Exception:
                failed += 1

        parts = [f"{copied} new file{'s' if copied != 1 else ''} copied"]
        if already_there:
            parts.append(f"{already_there} already existed (skipped)")
        if failed:
            parts.append(f"{failed} failed")

        folder_name = os.path.basename(self.project_folder)
        QMessageBox.information(
            self, "Done",
            f"{', '.join(parts)}.\n\nFiles are organized into section folders inside: {folder_name}\nImport them in Premiere via File -> Import."
        )

    def populate_list(self):
        self.file_list.clear()
        self.file_list.setIconSize(QSize(THUMB_SIZE, THUMB_SIZE))
        total = 0
        changed = False
        visible_files = 0
        empty_sections = 0
        header_height = 30
        separator_height = 2
        file_height = 54
        drop_pad_height = 34

        for section in self.sections:
            valid_count = sum(1 for path in section["files"] if os.path.exists(path))
            visible_files += valid_count
            if valid_count == 0:
                empty_sections += 1

        section_count = max(1, len(self.sections))
        base_height = (section_count * header_height)
        base_height += max(0, section_count - 1) * separator_height
        base_height += visible_files * file_height
        base_height += (section_count - empty_sections) * drop_pad_height
        spare_height = max(0, self.file_list.viewport().height() - base_height)
        empty_drop_height = 18
        if empty_sections:
            empty_drop_height = max(18, spare_height // empty_sections)

        for index, section in enumerate(self.sections):
            valid_files = []
            for path in section["files"]:
                if os.path.exists(path):
                    valid_files.append(path)
                else:
                    changed = True
            section["files"] = valid_files

            if index:
                separator = QListWidgetItem()
                separator.setFlags(Qt.NoItemFlags)
                separator.setBackground(QColor("#2a2a4a"))
                separator.setSizeHint(QSize(0, separator_height))
                self.file_list.addItem(separator)

            header = QListWidgetItem(f"  {section['name']} ({len(valid_files)})")
            header.setData(Qt.UserRole, None)
            header.setData(Qt.UserRole + 1, section["name"])
            header.setFlags(Qt.NoItemFlags)
            header.setBackground(QColor("#24244d"))
            header.setForeground(QColor("#ffffff"))
            header.setFont(QFont("", 10, QFont.Bold))
            header.setSizeHint(QSize(0, header_height))
            self.file_list.addItem(header)

            if not valid_files:
                self.add_drop_zone_item(section["name"], empty_drop_height)

            for path in valid_files:
                total += 1
                ftype = get_file_type(path)
                emoji = get_file_icon(ftype)
                name = os.path.basename(path)
                folder = os.path.basename(os.path.dirname(path))
                size = os.path.getsize(path)
                size_str = self.human_size(size)

                item = QListWidgetItem()
                if ftype == "image":
                    thumb = get_image_thumbnail(path)
                    if thumb:
                        item.setIcon(thumb)
                        item.setText(f"  {name}\n  {folder}  -  {size_str}")
                    else:
                        item.setText(f"{emoji}  {name}\n     {folder}  -  {size_str}")
                else:
                    item.setText(f"{emoji}  {name}\n     {folder}  -  {size_str}")

                item.setData(Qt.UserRole, path)
                item.setData(Qt.UserRole + 1, section["name"])
                item.setToolTip(path)
                item.setSizeHint(QSize(0, file_height))
                self.file_list.addItem(item)

            if valid_files:
                self.add_drop_zone_item(section["name"], drop_pad_height, "Drop more files here")

        self.saved_files = self.all_files()
        if changed:
            self.save_library()

        self.count_label.setText(f"{total} file{'s' if total != 1 else ''}")
        return
        valid = []
        for path in self.saved_files:
            if not os.path.exists(path):
                continue  # skip missing files silently
            valid.append(path)
            ftype = get_file_type(path)
            emoji = get_file_icon(ftype)
            name = os.path.basename(path)
            folder = os.path.basename(os.path.dirname(path))
            size = os.path.getsize(path)
            size_str = self.human_size(size)

            item = QListWidgetItem()

            if ftype == "image":
                thumb = get_image_thumbnail(path)
                if thumb:
                    item.setIcon(thumb)
                    item.setText(f"  {name}\n  {folder}  ·  {size_str}")
                else:
                    item.setText(f"{emoji}  {name}\n     {folder}  ·  {size_str}")
            else:
                item.setText(f"{emoji}  {name}\n     {folder}  ·  {size_str}")

            item.setData(Qt.UserRole, path)
            item.setToolTip(path)
            self.file_list.addItem(item)

        # Update saved list to remove missing files
        if len(valid) != len(self.saved_files):
            self.saved_files = valid
            save_files(self.saved_files)

        count = len(valid)
        self.count_label.setText(f"{count} file{'s' if count != 1 else ''}")

    # ── Video hover preview (stub for contributors) ──────────────────
    # To implement YouTube-style hover preview:
    # 1. On file add, use ffmpeg to extract N frames evenly spaced:
    #      ffmpeg -i video.mp4 -vf fps=1/5 thumb_%03d.jpg
    #    Store frame paths in a dict keyed by source file path.
    # 2. Subclass DraggableList and override mouseMoveEvent.
    # 3. On hover, identify the item under the cursor via itemAt(event.pos()).
    # 4. Map cursor X position within the item rect to a frame index.
    # 5. Show a QLabel popup near the cursor with the corresponding frame QPixmap.
    # 6. Hide the popup on mouseLeaveEvent or when the item changes.
    # See: https://doc.qt.io/qt-5/qlistwidget.html#itemAt

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
            for section in self.sections:
                section["files"] = []
            self.save_library()
            self.populate_list()

    # ── Context menu ─────────────────────────────────────────────────

    def show_context_menu(self, pos):
        item = self.file_list.itemAt(pos)
        if not item:
            return
        section_name = item.data(Qt.UserRole + 1)
        if not item.data(Qt.UserRole):
            if section_name:
                self.show_section_menu(pos, section_name)
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
        move_menu = menu.addMenu("Move to Section")
        current_section = item.data(Qt.UserRole + 1)
        for section in self.sections:
            action = QAction(section["name"], self)
            action.setEnabled(section["name"] != current_section)
            action.triggered.connect(
                lambda checked=False, name=section["name"]: self.move_item_to_section(item, name)
            )
            move_menu.addAction(action)
        menu.addSeparator()
        menu.addAction(remove_action)
        menu.exec_(self.file_list.viewport().mapToGlobal(pos))

    def show_section_menu(self, pos, section_name):
        section = self.find_section(section_name)
        if section is None:
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

        rename_action = QAction("Rename Section", self)
        rename_action.triggered.connect(lambda: self.rename_section(section_name))

        remove_action = QAction("Remove Section", self)
        remove_action.setEnabled(len(self.sections) > 1)
        remove_action.triggered.connect(lambda: self.remove_section(section_name))

        menu.addAction(rename_action)
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
        if not path:
            return
        for section in self.sections:
            if path in section["files"]:
                section["files"].remove(path)
        self.save_library()
        self.populate_list()

    def rename_section(self, section_name):
        section = self.find_section(section_name)
        if section is None:
            return
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Section",
            "Section name:",
            text=section_name
        )
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name or new_name == section_name:
            return
        if self.find_section(new_name):
            QMessageBox.information(self, "Section Exists", f'"{new_name}" already exists.')
            return
        section["name"] = new_name
        self.save_library()
        self.populate_list()

    def remove_section(self, section_name):
        section = self.find_section(section_name)
        if section is None:
            return
        if len(self.sections) <= 1:
            QMessageBox.information(self, "Cannot Remove", "At least one section is required.")
            return

        files = list(section["files"])
        target_sections = [s for s in self.sections if s["name"] != section_name]

        if files:
            target_names = [s["name"] for s in target_sections]
            target_names.append("Remove files from library")
            choice, ok = QInputDialog.getItem(
                self,
                "Remove Section",
                f'"{section_name}" contains {len(files)} file{"s" if len(files) != 1 else ""}. Move them to:',
                target_names,
                0,
                False
            )
            if not ok:
                return
            if choice != "Remove files from library":
                target = self.find_section(choice)
                if target is not None:
                    for path in files:
                        if path not in target["files"]:
                            target["files"].append(path)

        self.sections = [s for s in self.sections if s["name"] != section_name]
        self.save_library()
        self.populate_list()

    def move_item_to_section(self, item, target_name):
        path = item.data(Qt.UserRole)
        target = self.find_section(target_name)
        if not path or target is None:
            return
        for section in self.sections:
            if path in section["files"]:
                section["files"].remove(path)
        if path not in target["files"]:
            target["files"].append(path)
        self.save_library()
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

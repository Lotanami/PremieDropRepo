import sys
import os
import json
import shutil
import platform
import hashlib
import subprocess
from datetime import datetime, timezone
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QFileDialog,
    QAbstractItemView, QMenu, QAction, QMessageBox, QFrame, QSizePolicy,
    QInputDialog, QListView, QStyledItemDelegate, QSlider, QShortcut
)
from PyQt5.QtCore import Qt, QMimeData, QUrl, QSize, QRect, QTimer, QPoint
from PyQt5.QtGui import (
    QIcon, QColor, QFont, QDrag, QPalette, QPixmap, QPainter, QPen,
    QKeySequence, QPolygon
)

try:
    import vlc
except (ImportError, OSError):
    vlc = None

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None

SAVE_FILE = os.path.join(os.path.dirname(__file__), "saved_files.json")
APP_DATA_DIR = os.path.join(
    os.environ.get("APPDATA", os.path.dirname(__file__)),
    "PremieDrop"
)
IMPORT_QUEUE_FILE = os.path.join(APP_DATA_DIR, "premiedrop_import_queue.json")
VIDEO_THUMB_DIR = os.path.join(os.path.dirname(__file__), "thumbnail_cache")
THUMB_SIZE = 112
LARGE_VIDEO_BYTES = 1 * 1024 * 1024 * 1024
VIDEO_THUMBNAIL_ICONS = {}

DEFAULT_SECTIONS = [
    "Large Video Files (1GB>)",
    "Short Video Files (1GB<)",
    "Sound effects (.mp3 etc)",
    "Images/GIFs",
]

SECTION_NAME_ALIASES = {
    "Large Video Files (5Gb>)": "Large Video Files (1GB>)",
    "Large Video Files (5GB>)": "Large Video Files (1GB>)",
    "Large Video Files (1Gb>)": "Large Video Files (1GB>)",
    "Short Video Files (1Gb<)": "Short Video Files (1GB<)",
}

BASE_WINDOW_WIDTH = 550
BASE_WINDOW_HEIGHT = 800
IMAGE_PREVIEW_HEIGHT = 300
IMAGE_PREVIEW_SCALE = 0.50
IMAGE_PREVIEW_TEXT_SIZE = 11
IMAGE_PREVIEW_PADDING = 8
IMAGE_PREVIEW_TEXT_GAP = 6

def scaled_image_preview_height():
    return max(100, int(IMAGE_PREVIEW_HEIGHT * IMAGE_PREVIEW_SCALE))

def scaled_image_preview_value(value, minimum=1):
    return max(minimum, int(round(value * IMAGE_PREVIEW_SCALE)))

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

def get_ffmpeg_path():
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path
    if imageio_ffmpeg is not None:
        try:
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass
    return None

def get_video_thumbnail(path):
    """Extract and cache a representative video frame as a QIcon."""
    try:
        modified = os.path.getmtime(path)
        cache_key = f"{os.path.abspath(path)}|{modified}"
        if cache_key in VIDEO_THUMBNAIL_ICONS:
            return VIDEO_THUMBNAIL_ICONS[cache_key]

        ffmpeg_path = get_ffmpeg_path()
        if not ffmpeg_path:
            return None

        os.makedirs(VIDEO_THUMB_DIR, exist_ok=True)
        digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()
        thumbnail_path = os.path.join(VIDEO_THUMB_DIR, f"{digest}.jpg")

        if not os.path.exists(thumbnail_path):
            command = [
                ffmpeg_path,
                "-hide_banner",
                "-loglevel", "error",
                "-ss", "1",
                "-i", path,
                "-frames:v", "1",
                "-vf", "scale=320:180:force_original_aspect_ratio=decrease",
                "-q:v", "3",
                "-y",
                thumbnail_path,
            ]
            startupinfo = None
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                startupinfo=startupinfo,
                timeout=15,
                check=False,
            )

        pixmap = QPixmap(thumbnail_path)
        if pixmap.isNull():
            return None
        icon = QIcon(pixmap)
        VIDEO_THUMBNAIL_ICONS[cache_key] = icon
        return icon
    except (OSError, subprocess.SubprocessError):
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
    sections_by_name = {}
    for section in sections:
        name = str(section.get("name", "")).strip()
        name = SECTION_NAME_ALIASES.get(name, name)
        if not name:
            continue
        target = sections_by_name.get(name)
        if target is None:
            target = {"name": name, "files": []}
            sections_by_name[name] = target
            clean.append(target)
        for path in section.get("files", []):
            norm = os.path.normpath(path)
            if norm not in target["files"]:
                target["files"].append(norm)
    for name in DEFAULT_SECTIONS:
        if name not in sections_by_name:
            target = {"name": name, "files": []}
            sections_by_name[name] = target
            clean.append(target)
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
                return "Large Video Files (1GB>)"
        except OSError:
            pass
        return "Short Video Files (1GB<)"
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

def write_import_queue(project_folder, entries):
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    payload = {
        "version": 1,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_folder": os.path.abspath(project_folder),
        "files": entries,
    }
    with open(IMPORT_QUEUE_FILE, "w", encoding="utf-8") as queue_file:
        json.dump(payload, queue_file, indent=2)

def invalidate_import_queue(project_folder=""):
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    payload = {
        "version": 1,
        "status": "stale",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_folder": os.path.abspath(project_folder) if project_folder else "",
        "files": [],
        "invalidated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with open(IMPORT_QUEUE_FILE, "w", encoding="utf-8") as queue_file:
            json.dump(payload, queue_file, indent=2)
    except Exception:
        try:
            os.remove(IMPORT_QUEUE_FILE)
        except OSError:
            pass

def sync_import_queue_folder(project_folder):
    if not project_folder:
        return
    selected = os.path.normcase(os.path.abspath(os.path.normpath(project_folder)))
    try:
        with open(IMPORT_QUEUE_FILE, "r", encoding="utf-8") as queue_file:
            payload = json.load(queue_file)
        queued_folder = payload.get("project_folder", "")
        queued = os.path.normcase(
            os.path.abspath(os.path.normpath(queued_folder))
        ) if queued_folder else ""
        if queued == selected:
            return
    except Exception:
        pass
    invalidate_import_queue(project_folder)


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


class DropZoneItem(QListWidgetItem):
    """A list item painted as a standalone dashed drop target."""

    def __init__(self, section_name, has_files, size):
        text = "Drop more\nfiles here" if has_files else "Drop files\nhere"
        super().__init__(text)
        self.setData(Qt.UserRole, None)
        self.setData(Qt.UserRole + 1, section_name)
        self.setData(Qt.UserRole + 2, True)
        self.setFlags(Qt.NoItemFlags)
        self.setTextAlignment(Qt.AlignCenter)
        self.setSizeHint(size)


class SectionItemDelegate(QStyledItemDelegate):
    """Paints drop-zone items directly without nesting another widget."""

    def paint(self, painter, option, index):
        if not index.data(Qt.UserRole + 2):
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRect(option.rect).adjusted(3, 3, -3, -3)
        painter.setBrush(QColor("#1b213d"))
        painter.setPen(QPen(QColor("#66669a"), 2, Qt.DashLine))
        painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(QColor("#9999cc"))
        painter.setFont(option.font)
        painter.drawText(rect.adjusted(5, 5, -5, -5), Qt.AlignCenter, index.data(Qt.DisplayRole))
        painter.restore()


class AutoSortDropBox(QLabel):
    """Dedicated drop target that sends files through the auto-sort rules."""

    def __init__(self, parent=None):
        super().__init__("Autosort Files", parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(74)
        self.setStyleSheet("""
            QLabel {
                background-color: #16213e;
                color: #ccccff;
                border: 2px dashed #3a3a66;
                border-radius: 10px;
                font-size: 13px;
                font-weight: bold;
            }
            QLabel:hover {
                background-color: #1d2750;
                border-color: #6C63FF;
                color: #ffffff;
            }
        """)

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
            paths = [url.toLocalFile() for url in event.mimeData().urls()]
            main = self.window()
            if hasattr(main, "add_files"):
                main.add_files(paths)
            event.acceptProposedAction()


class SectionDropBox(QWidget):
    """Responsive horizontal section with its header inside a dotted border."""

    def __init__(self, main_window, section_name, files, height):
        super().__init__()
        self.main_window = main_window
        self.section_name = section_name
        self.setAcceptDrops(True)
        self.setFixedHeight(height)
        self.setObjectName("section_box")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("""
            QWidget#section_box {
                background-color: #181d38;
                border: 2px solid #51517f;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 5)
        layout.setSpacing(3)

        header = QLabel(f"{section_name} ({len(files)})")
        header.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setFixedHeight(22)
        header.setStyleSheet("""
            QLabel {
                color: #ffffff;
                background-color: #24244d;
                border: none;
                border-radius: 5px;
                padding: 0px 8px;
                font-size: 10px;
                font-weight: bold;
            }
        """)
        layout.addWidget(header)

        self.file_list = DraggableList()
        self.file_list.setFrameShape(QFrame.NoFrame)
        self.file_list.setViewMode(QListView.IconMode)
        self.file_list.setFlow(QListView.LeftToRight)
        self.file_list.setWrapping(False)
        self.file_list.setResizeMode(QListView.Adjust)
        self.file_list.setMovement(QListView.Static)
        self.file_list.setSpacing(4)
        self.file_list.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                color: #ccccee;
                font-size: 10px;
                padding: 0px;
                outline: none;
            }
            QListWidget::item {
                background-color: #202644;
                padding: 3px;
                border-radius: 6px;
                margin: 0px;
            }
            QListWidget::item:selected {
                background-color: #6C63FF;
                color: #ffffff;
            }
            QListWidget::item:hover {
                background-color: #22224a;
            }
        """)
        self.file_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(
            lambda pos: self.main_window.show_context_menu_from_list(self.file_list, pos)
        )
        self.file_list.itemClicked.connect(self.main_window.preview_item)
        self.file_list.setItemDelegate(SectionItemDelegate(self.file_list))
        self.file_list.setFixedHeight(max(30, height - 34))
        self.file_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.file_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        slot_count = max(1, len(files) + 1)
        available_width = max(180, main_window.file_list.viewport().width() - 28)
        tile_width = max(52, min(150, (available_width - ((slot_count - 1) * 4)) // slot_count))
        tile_height = max(32, height - 38)
        # Leave one compact line for the filename and give the rest to the thumbnail.
        icon_size = max(24, min(THUMB_SIZE, tile_height - 18, tile_width - 12))
        row_width = min(available_width, (slot_count * tile_width) + ((slot_count - 1) * 4))
        self.file_list.setFixedWidth(row_width)
        self.file_list.setGridSize(QSize(tile_width, tile_height))
        self.file_list.setIconSize(QSize(icon_size, icon_size))

        for path in files:
            item = self.main_window.make_file_item(path, section_name)
            item.setText(os.path.basename(path))
            item.setTextAlignment(Qt.AlignCenter)
            item.setSizeHint(QSize(tile_width, tile_height))
            self.file_list.addItem(item)

        drop_item = DropZoneItem(
            section_name,
            bool(files),
            QSize(tile_width, tile_height)
        )
        self.file_list.addItem(drop_item)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addStretch()
        row.addWidget(self.file_list)
        row.addStretch()
        layout.addLayout(row)

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
            paths = [url.toLocalFile() for url in event.mimeData().urls()]
            self.main_window.add_files(paths, self.section_name)
            event.acceptProposedAction()


class FullscreenVideoWindow(QWidget):
    """Borderless host for the VLC video surface."""

    def __init__(self, preview):
        super().__init__(None)
        self.preview = preview
        self.setStyleSheet("background-color: black;")
        self.setWindowTitle("PremieDrop Preview")

    def closeEvent(self, event):
        if self.preview.fullscreen_window is self:
            self.preview.exit_fullscreen()
            event.ignore()
            return
        super().closeEvent(event)


def white_media_icon(kind):
    """Create a crisp white media-control icon independent of OS theme."""
    pixmap = QPixmap(20, 20)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(Qt.white, 2, Qt.SolidLine, Qt.SquareCap))
    painter.setBrush(Qt.white)

    if kind == "play":
        painter.drawPolygon(QPolygon([
            QPoint(6, 4), QPoint(16, 10), QPoint(6, 16)
        ]))
    elif kind == "pause":
        painter.drawRect(5, 4, 3, 12)
        painter.drawRect(12, 4, 3, 12)
    elif kind in ("rewind", "forward"):
        first = [QPoint(10, 4), QPoint(3, 10), QPoint(10, 16)]
        second = [QPoint(17, 4), QPoint(10, 10), QPoint(17, 16)]
        if kind == "forward":
            first = [QPoint(10, 4), QPoint(17, 10), QPoint(10, 16)]
            second = [QPoint(3, 4), QPoint(10, 10), QPoint(3, 16)]
        painter.drawPolygon(QPolygon(first))
        painter.drawPolygon(QPolygon(second))
    elif kind == "fullscreen":
        painter.setBrush(Qt.NoBrush)
        painter.drawLine(4, 8, 4, 4)
        painter.drawLine(4, 4, 8, 4)
        painter.drawLine(12, 4, 16, 4)
        painter.drawLine(16, 4, 16, 8)
        painter.drawLine(4, 12, 4, 16)
        painter.drawLine(4, 16, 8, 16)
        painter.drawLine(12, 16, 16, 16)
        painter.drawLine(16, 16, 16, 12)

    painter.end()
    return QIcon(pixmap)


class VideoPreview(QWidget):
    """Embedded VLC player used to preview stored video and audio files."""

    def __init__(self, parent=None, standalone=False, on_closed=None):
        super().__init__(parent)
        self.standalone = standalone
        self.on_closed = on_closed
        self.closing = False
        self.player = None
        self.instance = None
        self.current_path = ""
        self.current_is_video = False
        self.fullscreen_window = None
        self.user_seeking = False
        self.setObjectName("video_preview")
        self.setAttribute(Qt.WA_StyledBackground, True)
        if self.standalone:
            self.setAttribute(Qt.WA_DeleteOnClose, True)
            self.setWindowTitle("PremieDrop Video Preview")
            self.setMinimumSize(640, 420)
            self.resize(800, 520)
        self.setStyleSheet("""
            QWidget#video_preview {
                background-color: #111426;
                border: 1px solid #51517f;
                border-radius: 8px;
            }
            QWidget#video_surface {
                background-color: #050507;
                border: none;
            }
            QLabel#preview_name {
                color: #ddddef;
                font-size: 11px;
                font-weight: bold;
            }
            QLabel#preview_time {
                color: #8888aa;
                font-size: 10px;
            }
            QPushButton#preview_control {
                background-color: #24244d;
                color: #ffffff;
                border: 1px solid #3a3a66;
                border-radius: 5px;
                min-width: 30px;
                min-height: 26px;
            }
            QPushButton#preview_control:hover {
                background-color: #353568;
            }
            QSlider::groove:horizontal {
                background-color: #30304f;
                height: 4px;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background-color: #6C63FF;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background-color: #ffffff;
                width: 12px;
                margin: -4px 0px;
                border-radius: 6px;
            }
        """)

        self.preview_layout = QVBoxLayout(self)
        self.preview_layout.setContentsMargins(8, 8, 8, 8)
        self.preview_layout.setSpacing(6)

        title_row = QHBoxLayout()
        self.name_label = QLabel("Media preview")
        self.name_label.setObjectName("preview_name")
        self.name_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.close_btn = QPushButton("X")
        self.close_btn.setObjectName("preview_control")
        self.close_btn.setToolTip("Close preview")
        self.close_btn.setFixedSize(28, 26)
        self.close_btn.clicked.connect(self.close_preview)
        title_row.addWidget(self.name_label)
        title_row.addStretch()
        self.escape_hint = QLabel("Press Esc to exit")
        self.escape_hint.setObjectName("preview_time")
        self.escape_hint.setVisible(self.standalone)
        title_row.addWidget(self.escape_hint)
        title_row.addWidget(self.close_btn)
        self.preview_layout.addLayout(title_row)

        self.video_surface = QWidget()
        self.video_surface.setObjectName("video_surface")
        self.video_surface.setMinimumHeight(130)
        self.preview_layout.addWidget(self.video_surface, 1)

        self.controls = QHBoxLayout()
        self.controls.setSpacing(8)
        self.rewind_btn = QPushButton()
        self.rewind_btn.setObjectName("preview_control")
        self.rewind_btn.setIcon(white_media_icon("rewind"))
        self.rewind_btn.setToolTip("Rewind 5 seconds (Left arrow)")
        self.rewind_btn.clicked.connect(lambda: self.skip_seconds(-5))

        self.play_btn = QPushButton()
        self.play_btn.setObjectName("preview_control")
        self.play_btn.setIcon(white_media_icon("play"))
        self.play_btn.setToolTip("Play or pause (Space)")
        self.play_btn.clicked.connect(self.toggle_playback)

        self.forward_btn = QPushButton()
        self.forward_btn.setObjectName("preview_control")
        self.forward_btn.setIcon(white_media_icon("forward"))
        self.forward_btn.setToolTip("Forward 5 seconds (Right arrow)")
        self.forward_btn.clicked.connect(lambda: self.skip_seconds(5))

        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.sliderPressed.connect(self.start_seeking)
        self.seek_slider.sliderReleased.connect(self.finish_seeking)

        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setObjectName("preview_time")

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(72)
        self.volume_slider.setToolTip("Volume")
        self.volume_slider.valueChanged.connect(self.set_volume)

        self.fullscreen_btn = QPushButton()
        self.fullscreen_btn.setObjectName("preview_control")
        self.fullscreen_btn.setIcon(white_media_icon("fullscreen"))
        self.fullscreen_btn.setToolTip("Fullscreen (F)")
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)

        self.controls.addWidget(self.rewind_btn)
        self.controls.addWidget(self.play_btn)
        self.controls.addWidget(self.forward_btn)
        self.controls.addWidget(self.seek_slider, 1)
        self.controls.addWidget(self.time_label)
        self.controls.addWidget(self.volume_slider)
        self.controls.addWidget(self.fullscreen_btn)
        self.preview_layout.addLayout(self.controls)

        self.shortcuts = []
        for key, callback in (
            (Qt.Key_Left, lambda: self.skip_seconds(-5)),
            (Qt.Key_Right, lambda: self.skip_seconds(5)),
            (Qt.Key_Space, self.toggle_playback),
            (Qt.Key_F, self.toggle_fullscreen),
            (Qt.Key_Escape, self.handle_escape),
        ):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)

        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.update_controls)

    def ensure_player(self):
        if self.player is not None:
            return True
        if vlc is None:
            QMessageBox.information(
                self,
                "VLC Required",
                "Install VLC Media Player and the Python package:\n\npip install python-vlc"
            )
            return False
        try:
            self.instance = vlc.Instance("--no-video-title-show")
            self.player = self.instance.media_player_new()
            self.player.audio_set_volume(self.volume_slider.value())
            return True
        except Exception as exc:
            QMessageBox.warning(
                self,
                "VLC Could Not Start",
                f"VLC could not be initialized.\n\n{exc}"
            )
            self.player = None
            return False

    def enable_compact_audio_mode(self):
        self.preview_layout.setContentsMargins(4, 3, 4, 3)
        self.preview_layout.setSpacing(2)
        self.controls.setSpacing(3)
        self.setFixedHeight(56)
        self.name_label.setMaximumHeight(18)
        self.name_label.setStyleSheet("font-size: 9px; font-weight: bold;")
        self.close_btn.setFixedSize(20, 18)
        self.close_btn.setStyleSheet(
            "min-width: 18px; min-height: 16px; padding: 0px;"
        )
        self.rewind_btn.hide()
        self.forward_btn.hide()
        self.fullscreen_btn.hide()
        self.play_btn.setFixedSize(24, 22)
        self.play_btn.setStyleSheet(
            "min-width: 22px; min-height: 20px; padding: 0px;"
        )
        self.time_label.setFixedWidth(54)
        self.time_label.setStyleSheet("font-size: 9px;")
        self.volume_slider.setFixedWidth(38)
        self.seek_slider.setMinimumWidth(72)

    def bind_video_surface(self):
        if self.player is None:
            return
        window_id = int(self.video_surface.winId())
        system = platform.system()
        if system == "Windows":
            self.player.set_hwnd(window_id)
        elif system == "Darwin":
            self.player.set_nsobject(window_id)
        else:
            self.player.set_xwindow(window_id)

    def load_media(self, path, show_video):
        if not self.ensure_player():
            return False
        self.exit_fullscreen()
        self.player.stop()
        self.current_is_video = show_video
        self.video_surface.setVisible(show_video)
        self.fullscreen_btn.setVisible(show_video)
        if self.standalone:
            self.setMinimumHeight(420)
            self.setMaximumHeight(16777215)
        else:
            self.setFixedHeight(250 if show_video else 56)
        self.show()
        self.current_path = path
        self.name_label.setText(os.path.basename(path))
        self.name_label.setToolTip(path)
        self.seek_slider.setValue(0)
        self.time_label.setText("0:00 / 0:00")
        media = self.instance.media_new_path(os.path.abspath(path))
        self.player.set_media(media)
        if show_video:
            self.bind_video_surface()
        self.player.play()
        self.set_playing_icon(True)
        self.timer.start()
        return True

    def load_video(self, path):
        return self.load_media(path, show_video=True)

    def load_audio(self, path):
        return self.load_media(path, show_video=False)

    def toggle_playback(self):
        if self.player is None:
            return
        if self.player.is_playing():
            self.player.pause()
            self.set_playing_icon(False)
        else:
            self.player.play()
            self.set_playing_icon(True)

    def set_playing_icon(self, playing):
        self.play_btn.setIcon(white_media_icon("pause" if playing else "play"))

    def skip_seconds(self, seconds):
        if self.player is None:
            return
        length = max(0, self.player.get_length())
        current = max(0, self.player.get_time())
        target = max(0, current + (seconds * 1000))
        if length:
            target = min(length, target)
        self.player.set_time(target)

    def toggle_fullscreen(self):
        if not self.current_is_video or self.player is None:
            return
        if self.fullscreen_window is not None:
            self.exit_fullscreen()
            return

        window = FullscreenVideoWindow(self)
        fullscreen_layout = QVBoxLayout(window)
        fullscreen_layout.setContentsMargins(0, 0, 0, 0)
        self.video_surface.setParent(window)
        fullscreen_layout.addWidget(self.video_surface)
        self.fullscreen_window = window

        for key, callback in (
            (Qt.Key_Escape, self.exit_fullscreen),
            (Qt.Key_F, self.exit_fullscreen),
            (Qt.Key_Space, self.toggle_playback),
            (Qt.Key_Left, lambda: self.skip_seconds(-5)),
            (Qt.Key_Right, lambda: self.skip_seconds(5)),
        ):
            shortcut = QShortcut(QKeySequence(key), window)
            shortcut.activated.connect(callback)

        window.showFullScreen()
        self.video_surface.show()
        QTimer.singleShot(0, self.bind_video_surface)

    def exit_fullscreen(self):
        window = self.fullscreen_window
        if window is None:
            return
        self.fullscreen_window = None
        self.video_surface.setParent(self)
        self.preview_layout.insertWidget(1, self.video_surface, 1)
        self.video_surface.show()
        window.close()
        window.deleteLater()
        QTimer.singleShot(0, self.bind_video_surface)

    def handle_escape(self):
        if self.fullscreen_window is not None:
            self.exit_fullscreen()
        elif self.standalone:
            self.close_preview()

    def start_seeking(self):
        self.user_seeking = True

    def finish_seeking(self):
        if self.player is not None:
            self.player.set_position(self.seek_slider.value() / 1000.0)
        self.user_seeking = False

    def set_volume(self, value):
        if self.player is not None:
            self.player.audio_set_volume(value)

    def update_controls(self):
        if self.player is None:
            return
        length = max(0, self.player.get_length())
        current = max(0, self.player.get_time())
        if not self.user_seeking and length:
            self.seek_slider.setValue(int((current / length) * 1000))
        self.time_label.setText(
            f"{self.format_time(current)} / {self.format_time(length)}"
        )
        if not self.player.is_playing() and current >= max(0, length - 500):
            self.set_playing_icon(False)

    @staticmethod
    def format_time(milliseconds):
        seconds = max(0, milliseconds // 1000)
        return f"{seconds // 60}:{seconds % 60:02d}"

    def close_preview(self):
        if self.closing:
            return
        self.closing = True
        self.exit_fullscreen()
        if self.player is not None:
            self.player.stop()
        self.set_playing_icon(False)
        self.current_path = ""
        self.current_is_video = False
        self.timer.stop()
        if self.standalone:
            self.close()
            return
        self.closing = False
        self.hide()
        main_window = self.window()
        if hasattr(main_window, "audio_preview_closed"):
            main_window.audio_preview_closed()
        elif hasattr(main_window, "schedule_section_refresh"):
            main_window.schedule_section_refresh()

    def hide_for_switch(self):
        if self.player is not None:
            self.player.stop()
        self.set_playing_icon(False)
        self.current_path = ""
        self.current_is_video = False
        self.timer.stop()
        self.hide()

    def release(self):
        self.exit_fullscreen()
        self.timer.stop()
        if self.player is not None:
            self.player.stop()
            self.player.release()
            self.player = None
        if self.instance is not None:
            self.instance.release()
            self.instance = None

    def closeEvent(self, event):
        self.release()
        callback = self.on_closed
        self.on_closed = None
        if callback is not None:
            callback(self)
        event.accept()


class ImagePreview(QWidget):
    """Aspect-ratio-preserving image preview embedded below the sections."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_path = ""
        self.source_pixmap = QPixmap()
        self.setObjectName("image_preview")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("""
            QWidget#image_preview {
                background-color: #111426;
                border: 1px solid #51517f;
                border-radius: 8px;
            }
            QLabel#image_preview_name {
                color: #ddddef;
                font-size: 11px;
                font-weight: bold;
            }
            QLabel#image_surface {
                background-color: transparent;
                border: none;
            }
            QPushButton#image_close {
                background-color: #24244d;
                color: #ffffff;
                border: 1px solid #3a3a66;
                border-radius: 5px;
                min-width: 28px;
                min-height: 26px;
            }
            QPushButton#image_close:hover {
                background-color: #353568;
            }
        """)

        self.image_layout = QVBoxLayout(self)

        title_row = QHBoxLayout()
        self.name_label = QLabel("Image preview")
        self.name_label.setObjectName("image_preview_name")
        self.close_btn = QPushButton("X")
        self.close_btn.setObjectName("image_close")
        self.close_btn.setToolTip("Close image preview")
        self.close_btn.clicked.connect(self.close_preview)
        title_row.addWidget(self.name_label)
        title_row.addStretch()
        title_row.addWidget(self.close_btn)
        self.image_layout.addLayout(title_row)

        self.image_surface = QLabel()
        self.image_surface.setObjectName("image_surface")
        self.image_surface.setAlignment(Qt.AlignCenter)
        self.image_layout.addWidget(self.image_surface, 1)
        self.apply_scale_settings()

    def apply_scale_settings(self):
        padding = scaled_image_preview_value(IMAGE_PREVIEW_PADDING, 2)
        gap = scaled_image_preview_value(IMAGE_PREVIEW_TEXT_GAP, 1)
        font_size = scaled_image_preview_value(IMAGE_PREVIEW_TEXT_SIZE, 7)
        close_width = scaled_image_preview_value(28, 18)
        close_height = scaled_image_preview_value(26, 18)
        self.image_layout.setContentsMargins(padding, padding, padding, padding)
        self.image_layout.setSpacing(gap)
        self.name_label.setStyleSheet(
            f"font-size: {font_size}px; font-weight: bold;"
        )
        self.close_btn.setFixedSize(close_width, close_height)
        self.close_btn.setStyleSheet(
            f"min-width: {close_width}px; min-height: {close_height}px; padding: 0px;"
        )

    def load_image(self, path):
        pixmap = QPixmap(path)
        if pixmap.isNull():
            QMessageBox.warning(self, "Image Preview", "This image could not be loaded.")
            return False
        self.current_path = path
        self.source_pixmap = pixmap
        self.apply_scale_settings()
        self.name_label.setText(os.path.basename(path))
        self.name_label.setToolTip(path)
        self.resize_to_image()
        self.show()
        QTimer.singleShot(0, self.update_scaled_image)
        return True

    def resize_to_image(self):
        if self.source_pixmap.isNull():
            return
        main_window = self.window()
        available_width = max(
            160,
            main_window.centralWidget().width() - 40
        )
        padding = scaled_image_preview_value(IMAGE_PREVIEW_PADDING, 2)
        gap = scaled_image_preview_value(IMAGE_PREVIEW_TEXT_GAP, 1)
        title_height = max(
            self.close_btn.height(),
            self.name_label.fontMetrics().height()
        ) + gap + (padding * 2)
        image_height = max(60, scaled_image_preview_height() - title_height)
        aspect_ratio = self.source_pixmap.width() / self.source_pixmap.height()
        image_width = max(80, int(image_height * aspect_ratio))

        if image_width > available_width - (padding * 2):
            image_width = available_width - (padding * 2)
            image_height = max(60, int(image_width / aspect_ratio))

        self.image_surface.setFixedSize(image_width, image_height)
        self.setFixedSize(
            image_width + (padding * 2),
            image_height + title_height
        )

    def update_scaled_image(self):
        if self.source_pixmap.isNull():
            self.image_surface.clear()
            return
        target = self.image_surface.size()
        if target.width() <= 0 or target.height() <= 0:
            return
        self.image_surface.setPixmap(
            self.source_pixmap.scaled(
                target,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_scaled_image()

    def hide_for_switch(self):
        self.current_path = ""
        self.source_pixmap = QPixmap()
        self.image_surface.clear()
        self.hide()

    def close_preview(self):
        self.hide_for_switch()
        main_window = self.window()
        if hasattr(main_window, "embedded_preview_closed"):
            main_window.embedded_preview_closed()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.section_refresh_pending = False
        self.video_windows = []
        self.embedded_previous_size = None
        self.sections = load_sections()
        self.saved_files = self.all_files()
        self.project_folder = load_project_folder()
        sync_import_queue_folder(self.project_folder)
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
                margin: 4px 8px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        self.file_list.setItemWidget(item, label)
        return item

    def make_file_item(self, path, section_name):
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
        elif ftype == "video":
            thumb = get_video_thumbnail(path)
            if thumb:
                item.setIcon(thumb)
                item.setText(f"  {name}\n  {folder}  -  {size_str}")
            else:
                item.setText(f"{emoji}  {name}\n     {folder}  -  {size_str}")
        else:
            item.setText(f"{emoji}  {name}\n     {folder}  -  {size_str}")

        item.setData(Qt.UserRole, path)
        item.setData(Qt.UserRole + 1, section_name)
        item.setToolTip(path)
        item.setSizeHint(QSize(0, 54))
        return item

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "file_list"):
            self.schedule_section_refresh()

    def schedule_section_refresh(self):
        if self.section_refresh_pending:
            return
        self.section_refresh_pending = True
        QTimer.singleShot(0, self.refresh_section_layout)

    def refresh_section_layout(self):
        self.section_refresh_pending = False
        if not hasattr(self, "file_list"):
            return
        central = self.centralWidget()
        if central is not None and central.layout() is not None:
            central.layout().activate()
        self.file_list.updateGeometry()
        self.populate_list()

    def minimum_height_for_sections(self):
        return BASE_WINDOW_HEIGHT

    def embedded_preview_active(self):
        audio_active = (
            hasattr(self, "video_preview")
            and not self.video_preview.isHidden()
        )
        image_active = (
            hasattr(self, "image_preview")
            and not self.image_preview.isHidden()
        )
        return audio_active or image_active

    def update_window_minimum_size(self, expand=False):
        minimum_height = self.minimum_height_for_sections()
        self.setMinimumWidth(BASE_WINDOW_WIDTH)
        if self.embedded_preview_active():
            locked_height = max(minimum_height, self.height())
            self.setMinimumHeight(locked_height)
            self.setMaximumHeight(locked_height)
        else:
            self.setMaximumHeight(16777215)
            self.setMinimumHeight(minimum_height)

    def init_ui(self):
        self.setWindowTitle("PremieDrop")
        minimum_height = self.minimum_height_for_sections()
        self.setMinimumSize(BASE_WINDOW_WIDTH, minimum_height)
        self.resize(BASE_WINDOW_WIDTH, minimum_height)
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

        self.video_preview = VideoPreview(self)
        self.video_preview.enable_compact_audio_mode()
        self.video_preview.setMinimumWidth(200)
        self.video_preview.setMaximumWidth(250)
        self.video_preview.hide()

        header.addLayout(title_col)
        header.addSpacing(8)
        header.addWidget(self.video_preview, 1)
        header.addStretch()
        header.addWidget(self.count_label)
        layout.addLayout(header)

        # ── Divider ───────────────────────────────────────────────────
        line = QFrame()
        line.setObjectName("divider")
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #2a2a4a; border: none; max-height: 1px;")
        layout.addWidget(line)

        # ── File list ────────────────────────────────────────────────
        self.autosort_drop_box = AutoSortDropBox()
        layout.addWidget(self.autosort_drop_box)

        self.file_list = DraggableList()
        self.file_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.file_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.file_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.file_list)

        self.image_preview = ImagePreview(self)
        self.image_preview.hide()
        layout.addWidget(self.image_preview, 0, Qt.AlignHCenter)

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

        self.copy_btn = QPushButton("Import All to Premiere")
        self.copy_btn.setObjectName("copy_btn")
        self.copy_btn.clicked.connect(self.copy_new_to_project)
        self.copy_btn.setFixedHeight(42)
        self.copy_btn.setText("Import All to Premiere")

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

    def preview_item(self, item):
        path = item.data(Qt.UserRole)
        file_type = get_file_type(path) if path else None
        if file_type not in ("video", "audio", "image"):
            return
        if file_type == "video":
            video_window = VideoPreview(
                standalone=True,
                on_closed=self.video_window_closed
            )
            self.video_windows.append(video_window)
            if not video_window.load_video(path):
                self.video_windows.remove(video_window)
                video_window.deleteLater()
            return

        if file_type == "audio":
            loaded = self.video_preview.load_audio(path)
            if loaded:
                locked_height = max(BASE_WINDOW_HEIGHT, self.height())
                self.setMinimumHeight(locked_height)
                self.setMaximumHeight(locked_height)
                self.schedule_section_refresh()
            return

        image_was_hidden = self.image_preview.isHidden()
        if image_was_hidden:
            self.embedded_previous_size = self.size()
        loaded = self.image_preview.load_image(path)
        preview_height = self.image_preview.height() + 20

        if loaded:
            self.setMinimumWidth(BASE_WINDOW_WIDTH)
            self.setMaximumHeight(16777215)
            self.setMinimumHeight(BASE_WINDOW_HEIGHT)
            base_size = self.embedded_previous_size or self.size()
            target_width = max(BASE_WINDOW_WIDTH, base_size.width())
            target_height = max(
                BASE_WINDOW_HEIGHT + preview_height,
                base_size.height() + preview_height
            )
            self.resize(target_width, target_height)
            self.setMinimumHeight(target_height)
            self.setMaximumHeight(target_height)
            self.schedule_section_refresh()
        elif image_was_hidden:
            self.embedded_previous_size = None

    def audio_preview_closed(self):
        if self.image_preview.isHidden():
            self.setMaximumHeight(16777215)
            self.setMinimumHeight(BASE_WINDOW_HEIGHT)
        else:
            locked_height = max(BASE_WINDOW_HEIGHT, self.height())
            self.setMinimumHeight(locked_height)
            self.setMaximumHeight(locked_height)
        self.schedule_section_refresh()

    def restore_image_preview_size(self):
        previous_size = self.embedded_previous_size
        self.embedded_previous_size = None
        self.setMaximumHeight(16777215)
        self.setMinimumSize(BASE_WINDOW_WIDTH, BASE_WINDOW_HEIGHT)
        if previous_size is not None:
            self.resize(
                max(BASE_WINDOW_WIDTH, previous_size.width()),
                max(BASE_WINDOW_HEIGHT, previous_size.height())
            )
        self.schedule_section_refresh()

    def video_window_closed(self, window):
        if window in self.video_windows:
            self.video_windows.remove(window)

    def embedded_preview_closed(self):
        previous_size = self.embedded_previous_size
        self.embedded_previous_size = None
        self.setMaximumHeight(16777215)
        self.setMinimumSize(BASE_WINDOW_WIDTH, BASE_WINDOW_HEIGHT)
        if previous_size is not None:
            restored_width = max(BASE_WINDOW_WIDTH, previous_size.width())
            restored_height = max(BASE_WINDOW_HEIGHT, previous_size.height())
            QTimer.singleShot(
                0,
                lambda: self.restore_embedded_window_size(
                    restored_width,
                    restored_height
                )
            )
        self.schedule_section_refresh()

    def restore_embedded_window_size(self, width, height):
        self.setMaximumHeight(16777215)
        self.setMinimumHeight(BASE_WINDOW_HEIGHT)
        self.resize(width, height)
        if not self.video_preview.isHidden():
            locked_height = max(BASE_WINDOW_HEIGHT, height)
            self.setMinimumHeight(locked_height)
            self.setMaximumHeight(locked_height)
        self.schedule_section_refresh()

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
        self.update_window_minimum_size(expand=True)
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
            folder_changed = os.path.normcase(os.path.normpath(folder)) != os.path.normcase(
                os.path.normpath(self.project_folder)
            )
            self.project_folder = folder
            if folder_changed:
                invalidate_import_queue(folder)
            self.save_library()
            self.update_folder_label()

    def update_folder_label(self):
        if self.project_folder and os.path.exists(self.project_folder):
            name = os.path.basename(self.project_folder)
            self.folder_label.setText(f"→  {name}")
            self.folder_label.setToolTip(self.project_folder)
            self.folder_label.setStyleSheet("color: #44aa66; font-size: 11px;")
            self.copy_btn.setEnabled(True)
            self.copy_btn.setToolTip(
                f"Copy all PremieDrop files into {name} and import them through the CEP panel"
            )
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
        ready_files = []
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
                    ready_files.append({
                        "path": os.path.abspath(dest),
                        "section": section["name"],
                    })
                    continue
                new_files.append((path, dest, section["name"]))

        for section in self.sections:
            try:
                os.makedirs(
                    os.path.join(self.project_folder, safe_folder_name(section["name"])),
                    exist_ok=True
                )
            except Exception:
                pass

        copied, failed = 0, 0
        for path, dest, section_name in new_files:
            try:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(path, dest)
                copied += 1
                ready_files.append({
                    "path": os.path.abspath(dest),
                    "section": section_name,
                })
            except Exception:
                failed += 1

        if not ready_files:
            QMessageBox.information(
                self,
                "Nothing to Prepare",
                "No valid files were available to copy or queue."
            )
            return

        try:
            write_import_queue(self.project_folder, ready_files)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Queue Could Not Be Written",
                f"Files were copied, but the Premiere import queue could not be created.\n\n{exc}"
            )
            return

        parts = [f"{copied} new file{'s' if copied != 1 else ''} copied"]
        if already_there:
            parts.append(f"{already_there} already existed (skipped)")
        if failed:
            parts.append(f"{failed} failed")

        folder_name = os.path.basename(self.project_folder)
        QMessageBox.information(
            self,
            "Import Sent",
            f"{', '.join(parts)}.\n\n"
            f"{len(ready_files)} file{'s are' if len(ready_files) != 1 else ' is'} "
            f"ready in {folder_name}.\n\n"
            "If the PremieDrop Bridge panel is open in Premiere, import starts automatically."
        )

    def populate_list(self):
        self.file_list.clear()
        total = 0
        changed = False
        section_count = max(1, len(self.sections))
        viewport_height = max(120, self.file_list.viewport().height() - 8)
        separator_height = 4
        separator_space = max(0, section_count - 1) * separator_height
        section_height = max(54, (viewport_height - separator_space) // section_count)

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

            total += len(valid_files)
            section_item = QListWidgetItem()
            section_item.setData(Qt.UserRole, None)
            section_item.setData(Qt.UserRole + 1, section["name"])
            section_item.setFlags(Qt.NoItemFlags)
            section_item.setSizeHint(QSize(0, section_height))
            self.file_list.addItem(section_item)
            section_box = SectionDropBox(
                self,
                section["name"],
                valid_files,
                section_height
            )
            self.file_list.setItemWidget(section_item, section_box)

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
        self.show_context_menu_from_list(self.file_list, pos)

    def show_context_menu_from_list(self, list_widget, pos):
        item = list_widget.itemAt(pos)
        if not item:
            return
        section_name = item.data(Qt.UserRole + 1)
        if not item.data(Qt.UserRole):
            if section_name:
                self.show_section_menu(list_widget, pos, section_name)
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
        menu.exec_(list_widget.viewport().mapToGlobal(pos))

    def show_section_menu(self, list_widget, pos, section_name):
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
        menu.exec_(list_widget.viewport().mapToGlobal(pos))

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
        if self.video_preview.current_path == path:
            self.video_preview.close_preview()
        if self.image_preview.current_path == path:
            self.image_preview.close_preview()
        for window in list(self.video_windows):
            if window.current_path == path:
                window.close_preview()
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
        self.update_window_minimum_size()
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

    def closeEvent(self, event):
        for window in list(self.video_windows):
            window.close_preview()
        self.image_preview.hide_for_switch()
        self.video_preview.release()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PremieDrop")
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

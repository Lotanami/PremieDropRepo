import sys
import os
import json
import shutil
import platform
import hashlib
import subprocess
import re
import mimetypes
import importlib.util
import time
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus, unquote, urlparse
from urllib.request import Request, urlopen
from datetime import datetime, timezone

from premiedrop_ext import ImportContext, ImportRegistry, UIExtensionRegistry
from premiedrop_ext.ui_config import APP_TEXT, UI_SIZES, THEME

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QFileDialog,
    QAbstractItemView, QMenu, QAction, QMessageBox, QFrame, QSizePolicy,
    QInputDialog, QListView, QStyledItemDelegate, QSlider, QShortcut,
    QDialog, QLineEdit, QComboBox, QProgressBar, QToolButton
)
from PyQt5.QtCore import (
    Qt, QMimeData, QUrl, QSize, QRect, QTimer, QPoint, QThread, pyqtSignal
)
from PyQt5.QtGui import (
    QIcon, QColor, QFont, QDrag, QPalette, QPixmap, QPainter, QPen,
    QKeySequence, QPolygon, QCursor, QMovie
)

try:
    import vlc
except (ImportError, OSError):
    vlc = None

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

APP_ROOT = os.path.dirname(__file__)
APP_DATA_DIR = os.path.join(
    os.environ.get("APPDATA", os.path.dirname(__file__)),
    "PremieDrop"
)
SAVE_FILE = os.path.join(APP_DATA_DIR, "saved_files.json")
LEGACY_SAVE_FILE = os.path.join(APP_ROOT, "saved_files.json")
IMPORT_QUEUE_FILE = os.path.join(APP_DATA_DIR, "premiedrop_import_queue.json")
YOUTUBE_DOWNLOAD_REQUEST_FILE = os.path.join(
    APP_DATA_DIR, "youtube_download_request.json"
)
YOUTUBE_DOCK_STATE_FILE = os.path.join(
    APP_DATA_DIR, "youtube_dock_state.json"
)
YOUTUBE_BROWSER_STATUS_FILE = os.path.join(
    APP_DATA_DIR, "youtube_browser_status.json"
)
YOUTUBE_BROWSER_LOG_FILE = os.path.join(
    APP_DATA_DIR, "youtube_browser.log"
)
YOUTUBE_BROWSER_COMMAND_FILE = os.path.join(
    APP_DATA_DIR, "youtube_browser_command.json"
)
APP_ICON_FILE = os.path.join(
    getattr(sys, "_MEIPASS", os.path.dirname(__file__)),
    "premiedrop.ico",
)
PRESETS_FILE = os.path.join(APP_DATA_DIR, "library_presets.json")
EDITOR_SETTINGS_FILE = os.path.join(
    APP_DATA_DIR, "editor_import_settings.json"
)
VIDEO_THUMB_DIR = os.path.join(APP_DATA_DIR, "thumbnail_cache")
THUMB_SIZE = 112
LARGE_VIDEO_BYTES = 1 * 1024 * 1024 * 1024
VIDEO_THUMBNAIL_ICONS = {}
BROWSER_STORAGE_APP_NAMES = (
    "PremieDrop",
    "PremieDrop Media Browser",
    "PremieDrop MyInstants",
    "PremieDrop YouTube",
)
BROWSER_STORAGE_CHILDREN = ("cache", "QtWebEngine")
LATEST_RELEASE_API = (
    "https://api.github.com/repos/Lotanami/PremieDropRepo/releases/latest"
)

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

BASE_WINDOW_WIDTH = UI_SIZES["base_window_width"]
BASE_WINDOW_HEIGHT = UI_SIZES["base_window_height"]
YOUTUBE_PANEL_MIN_WIDTH = 520
YOUTUBE_PANEL_PREFERRED_WIDTH = 900
ATTACHED_BROWSER_WINDOW_WIDTH = 1250
YOUTUBE_HOME_URL = "https://www.youtube.com/"
MYINSTANTS_HOME_URL = "https://www.myinstants.com/en/categories/memes/gb/"
TENOR_HOME_URL = "https://tenor.com/"
IMAGE_PREVIEW_HEIGHT = 300
IMAGE_PREVIEW_SCALE = 0.50
IMAGE_PREVIEW_TEXT_SIZE = 11
IMAGE_PREVIEW_PADDING = 8
IMAGE_PREVIEW_TEXT_GAP = 6

def scaled_image_preview_height():
    return max(100, int(IMAGE_PREVIEW_HEIGHT * IMAGE_PREVIEW_SCALE))

def scaled_image_preview_value(value, minimum=1):
    return max(minimum, int(round(value * IMAGE_PREVIEW_SCALE)))

def human_size(size):
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} B"
        size /= 1024
    return f"{size:.1f} TB"

def local_app_data_dir():
    root = os.environ.get("LOCALAPPDATA")
    if root:
        return root
    if os.name == "nt":
        return os.path.join(os.path.expanduser("~"), "AppData", "Local")
    return os.path.join(os.path.expanduser("~"), ".cache")

def path_is_inside(parent, child):
    try:
        return os.path.commonpath([
            os.path.abspath(parent),
            os.path.abspath(child),
        ]) == os.path.abspath(parent)
    except ValueError:
        return False

def clear_browser_storage_on_startup():
    local_root = os.path.abspath(local_app_data_dir())
    for app_name in BROWSER_STORAGE_APP_NAMES:
        app_storage_dir = os.path.abspath(os.path.join(local_root, app_name))
        if not path_is_inside(local_root, app_storage_dir):
            continue
        for child_name in BROWSER_STORAGE_CHILDREN:
            storage_path = os.path.abspath(
                os.path.join(app_storage_dir, child_name)
            )
            if not path_is_inside(app_storage_dir, storage_path):
                continue
            if not os.path.isdir(storage_path):
                continue
            try:
                shutil.rmtree(storage_path)
            except OSError:
                pass

SUPPORTED_EXTENSIONS = {
    "video": [".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v"],
    "audio": [".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".aiff"],
    "image": [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"],
}

ALL_EXTENSIONS = [ext for exts in SUPPORTED_EXTENSIONS.values() for ext in exts]

def get_file_type(path):
    ext = os.path.splitext(path)[1].lower()
    for ftype, exts in SUPPORTED_EXTENSIONS.items():
        if ext in exts:
            return ftype
    return "other"

def direct_download_section(filename="", mime_type=""):
    extension = os.path.splitext(filename)[1].lower()
    if extension in SUPPORTED_EXTENSIONS["image"] or mime_type.startswith("image/"):
        return "Images/GIFs"
    if extension in SUPPORTED_EXTENSIONS["audio"] or mime_type.startswith("audio/"):
        return "Sound effects (.mp3 etc)"
    if extension in SUPPORTED_EXTENSIONS["video"] or mime_type.startswith("video/"):
        return "Short Video Files (1GB<)"
    return ""

def looks_like_direct_download(url, filename="", mime_type=""):
    if direct_download_section(filename, mime_type):
        return True
    extension = os.path.splitext(urlparse(url).path)[1].lower()
    return extension in ALL_EXTENSIONS

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

def load_save_data():
    for path in (SAVE_FILE, LEGACY_SAVE_FILE):
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            continue
    return {}

def load_saved_files():
    return load_save_data().get("saved_files", [])

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


def media_duration_frames(path, frame_rate=24):
    if get_file_type(path) == "image" and not path.lower().endswith(".gif"):
        return frame_rate * 5
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path:
        creation_flags = (
            getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if os.name == "nt" else 0
        )
        try:
            result = subprocess.run(
                [ffmpeg_path, "-hide_banner", "-i", path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors="replace",
                timeout=15,
                creationflags=creation_flags,
            )
            match = re.search(
                r"Duration:\s*(\d+):(\d+):([\d.]+)",
                result.stderr,
            )
            if match:
                hours, minutes, seconds = match.groups()
                total_seconds = (
                    int(hours) * 3600
                    + int(minutes) * 60
                    + float(seconds)
                )
                return max(1, round(total_seconds * frame_rate))
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    return frame_rate * 5


def fcpxml_time(frames, frame_rate=24):
    return f"{max(1, int(frames))}/{frame_rate}s"


def write_davinci_fcpxml(path, sections, frame_rate=24):
    root = ET.Element("fcpxml", {"version": "1.10"})
    resources = ET.SubElement(root, "resources")
    format_id = "r1"
    ET.SubElement(
        resources,
        "format",
        {
            "id": format_id,
            "name": "FFVideoFormat1080p24",
            "frameDuration": f"1/{frame_rate}s",
            "width": "1920",
            "height": "1080",
            "colorSpace": "1-1-1 (Rec. 709)",
        },
    )

    timeline_items = []
    asset_number = 2
    total_frames = 0
    for section in sections:
        first_in_section = True
        for media_path in section["files"]:
            duration_frames = media_duration_frames(
                media_path, frame_rate
            )
            asset_id = f"r{asset_number}"
            asset_number += 1
            media_type = get_file_type(media_path)
            asset_attributes = {
                "id": asset_id,
                "name": os.path.basename(media_path),
                "start": "0s",
                "duration": fcpxml_time(duration_frames, frame_rate),
            }
            if media_type in ("video", "image"):
                asset_attributes["hasVideo"] = "1"
                asset_attributes["format"] = format_id
            if media_type in ("video", "audio"):
                asset_attributes["hasAudio"] = "1"
            asset = ET.SubElement(
                resources, "asset", asset_attributes
            )
            ET.SubElement(
                asset,
                "media-rep",
                {
                    "kind": "original-media",
                    "src": bytes(
                        QUrl.fromLocalFile(
                            os.path.abspath(media_path)
                        ).toEncoded()
                    ).decode("ascii"),
                },
            )
            timeline_items.append({
                "asset_id": asset_id,
                "name": os.path.basename(media_path),
                "duration_frames": duration_frames,
                "offset_frames": total_frames,
                "section": section["name"] if first_in_section else "",
            })
            first_in_section = False
            total_frames += duration_frames

    library = ET.SubElement(root, "library")
    event = ET.SubElement(library, "event", {"name": "PremieDrop"})
    project = ET.SubElement(
        event, "project", {"name": "PremieDrop Import"}
    )
    sequence = ET.SubElement(
        project,
        "sequence",
        {
            "format": format_id,
            "duration": fcpxml_time(total_frames, frame_rate),
            "tcStart": "0s",
            "tcFormat": "NDF",
            "audioLayout": "stereo",
            "audioRate": "48k",
        },
    )
    spine = ET.SubElement(sequence, "spine")
    for item in timeline_items:
        clip = ET.SubElement(
            spine,
            "asset-clip",
            {
                "ref": item["asset_id"],
                "offset": fcpxml_time(
                    item["offset_frames"], frame_rate
                ) if item["offset_frames"] else "0s",
                "name": item["name"],
                "start": "0s",
                "duration": fcpxml_time(
                    item["duration_frames"], frame_rate
                ),
            },
        )
        if item["section"]:
            ET.SubElement(
                clip,
                "marker",
                {
                    "start": "0s",
                    "duration": f"1/{frame_rate}s",
                    "value": item["section"],
                },
            )

    if hasattr(ET, "indent"):
        ET.indent(root, space="  ")
    xml_body = ET.tostring(
        root, encoding="unicode", short_empty_elements=True
    )
    with open(path, "w", encoding="utf-8", newline="\n") as xml_file:
        xml_file.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        xml_file.write("<!DOCTYPE fcpxml>\n")
        xml_file.write(xml_body)
        xml_file.write("\n")
    ET.parse(path)
    return len(timeline_items), total_frames


def connect_to_davinci_resolve():
    loaded_module = sys.modules.get("DaVinciResolveScript")
    if loaded_module is not None and hasattr(loaded_module, "scriptapp"):
        return loaded_module.scriptapp("Resolve")

    program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
    api_root = os.environ.get(
        "RESOLVE_SCRIPT_API",
        os.path.join(
            program_data,
            "Blackmagic Design",
            "DaVinci Resolve",
            "Support",
            "Developer",
            "Scripting",
        ),
    )
    module_path = os.path.join(
        api_root, "Modules", "DaVinciResolveScript.py"
    )
    if not os.path.isfile(module_path):
        raise RuntimeError(
            "The DaVinci Resolve scripting module was not found."
        )

    if not os.environ.get("RESOLVE_SCRIPT_LIB"):
        library_candidates = [
            os.path.join(
                os.environ.get("PROGRAMFILES", r"C:\Program Files"),
                "Blackmagic Design",
                "DaVinci Resolve",
                "fusionscript.dll",
            ),
            r"E:\fusionscript.dll",
        ]
        for library_path in library_candidates:
            if os.path.isfile(library_path):
                os.environ["RESOLVE_SCRIPT_LIB"] = library_path
                break

    spec = importlib.util.spec_from_file_location(
        "DaVinciResolveScript", module_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(
            "The DaVinci Resolve scripting module could not be loaded."
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules["DaVinciResolveScript"] = module
    spec.loader.exec_module(module)
    loaded_module = sys.modules.get("DaVinciResolveScript", module)
    if not hasattr(loaded_module, "scriptapp"):
        raise RuntimeError(
            "The DaVinci Resolve scripting library did not initialize."
        )
    return loaded_module.scriptapp("Resolve")

def load_sections():
    data = load_save_data()
    if "sections" in data:
        return normalize_sections(data.get("sections", []))
    if data:
        sections = make_empty_sections()
        for path in data.get("saved_files", []):
            norm = os.path.normpath(path)
            target = section_for_file(norm)
            for section in sections:
                if section["name"] == target:
                    section["files"].append(norm)
                    break
        return normalize_sections(sections)
    return make_empty_sections()

def load_project_folder():
    return load_save_data().get("project_folder", "")

def load_last_download_folder():
    return load_save_data().get("last_download_folder", "")

def save_files(
    file_list, project_folder="", sections=None, last_download_folder=None
):
    existing = load_save_data()
    existing["saved_files"] = file_list
    if sections is not None:
        existing["sections"] = sections
    if project_folder:
        existing["project_folder"] = project_folder
    if last_download_folder is not None:
        existing["last_download_folder"] = last_download_folder
    os.makedirs(os.path.dirname(SAVE_FILE), exist_ok=True)
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)

def load_presets():
    try:
        with open(PRESETS_FILE, "r", encoding="utf-8") as preset_file:
            presets = json.load(preset_file)
        return presets if isinstance(presets, dict) else {}
    except (OSError, ValueError):
        return {}

def save_presets(presets):
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    with open(PRESETS_FILE, "w", encoding="utf-8") as preset_file:
        json.dump(presets, preset_file, indent=2)


def load_editor_settings():
    try:
        with open(
            EDITOR_SETTINGS_FILE, "r", encoding="utf-8"
        ) as settings_file:
            settings = json.load(settings_file)
        return settings if isinstance(settings, dict) else {}
    except (OSError, ValueError):
        return {}


def save_editor_settings(settings):
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    with open(
        EDITOR_SETTINGS_FILE, "w", encoding="utf-8"
    ) as settings_file:
        json.dump(settings, settings_file, indent=2)

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


class ClickableFolderLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.active = False
        self.hovered = False
        self.setCursor(Qt.ArrowCursor)

    def set_active(self, active):
        self.active = active
        self.setCursor(Qt.PointingHandCursor if active else Qt.ArrowCursor)
        self.refresh_style()

    def refresh_style(self):
        if self.active:
            decoration = "text-decoration: underline;" if self.hovered else ""
            self.setStyleSheet(
                "color: #44aa66; font-size: 11px; "
                f"{decoration}"
            )
        else:
            self.setStyleSheet(
                "color: #555577; font-size: 11px; font-style: italic;"
            )

    def enterEvent(self, event):
        self.hovered = True
        self.refresh_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered = False
        self.refresh_style()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.active and event.button() == Qt.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class FolderContentsDialog(QDialog):
    def __init__(self, folder, parent=None):
        super().__init__(parent)
        self.root_folder = os.path.abspath(folder)
        self.current_folder = self.root_folder
        self.setWindowTitle("Folder Contents")
        self.resize(520, 520)
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a2e;
                color: #ddddef;
            }
            QLabel {
                color: #aaaac6;
                font-size: 11px;
            }
            QListWidget {
                background-color: #16213e;
                border: 1px solid #2a2a4a;
                border-radius: 8px;
                color: #ddddef;
                padding: 4px;
            }
            QListWidget::item {
                padding: 7px 8px;
                border-radius: 5px;
            }
            QListWidget::item:selected {
                background-color: #6C63FF;
                color: #ffffff;
            }
            QPushButton {
                min-height: 30px;
                padding: 5px 12px;
                background-color: #24244d;
                color: white;
                border: 1px solid #45456f;
                border-radius: 5px;
            }
            QPushButton:disabled {
                color: #666680;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        self.path_label = QLabel("")
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)

        self.file_list = QListWidget()
        self.file_list.setIconSize(QSize(THUMB_SIZE, THUMB_SIZE))
        self.file_list.itemDoubleClicked.connect(self.open_item)
        layout.addWidget(self.file_list, 1)

        button_row = QHBoxLayout()
        self.up_btn = QPushButton("Up")
        self.up_btn.clicked.connect(self.go_up)
        self.add_btn = QPushButton("Add Selected")
        self.add_btn.clicked.connect(self.add_selected)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_row.addWidget(self.up_btn)
        button_row.addStretch()
        button_row.addWidget(self.add_btn)
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)

        self.refresh()

    def refresh(self):
        self.file_list.clear()
        self.path_label.setText(self.current_folder)
        self.up_btn.setEnabled(self.current_folder != self.root_folder)
        try:
            entries = sorted(
                os.scandir(self.current_folder),
                key=lambda entry: (not entry.is_dir(), entry.name.casefold()),
            )
        except OSError as exc:
            QMessageBox.warning(self, "Folder Error", str(exc))
            return

        for entry in entries:
            try:
                is_dir = entry.is_dir()
            except OSError:
                continue
            label = f"[Folder] {entry.name}" if is_dir else entry.name
            if not is_dir:
                try:
                    label = f"{label}  -  {human_size(os.path.getsize(entry.path))}"
                except OSError:
                    pass
            item = QListWidgetItem(label)
            if is_dir:
                item.setText(f"[Folder] {entry.name}")
                item.setSizeHint(QSize(0, 38))
            else:
                file_type = get_file_type(entry.path)
                if file_type == "image":
                    thumbnail = get_image_thumbnail(entry.path)
                    if thumbnail:
                        item.setIcon(thumbnail)
                elif file_type == "video":
                    thumbnail = get_video_thumbnail(entry.path)
                    if thumbnail:
                        item.setIcon(thumbnail)
                if file_type in ("image", "video"):
                    item.setSizeHint(QSize(0, THUMB_SIZE + 12))
                else:
                    item.setSizeHint(QSize(0, 42))
            item.setData(Qt.UserRole, entry.path)
            item.setData(Qt.UserRole + 1, is_dir)
            item.setToolTip(entry.path)
            self.file_list.addItem(item)

    def open_item(self, item):
        path = item.data(Qt.UserRole)
        if item.data(Qt.UserRole + 1):
            self.current_folder = path
            self.refresh()

    def go_up(self):
        parent = os.path.dirname(self.current_folder)
        if path_is_inside(self.root_folder, parent):
            self.current_folder = parent
            self.refresh()

    def add_selected(self):
        main = self.parent()
        paths = []
        for item in self.file_list.selectedItems():
            path = item.data(Qt.UserRole)
            if not item.data(Qt.UserRole + 1) and path:
                paths.append(path)
        if paths and hasattr(main, "add_files"):
            main.add_files(paths)


class SectionDropBox(QWidget):
    """Responsive horizontal section with its header inside a dotted border."""

    def __init__(self, main_window, section_name, files, height, total_count=None):
        super().__init__()
        self.main_window = main_window
        self.section_name = section_name
        total_count = len(files) if total_count is None else total_count
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

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(4)

        count_text = str(total_count)
        if len(files) != total_count:
            count_text = f"{len(files)}/{total_count}"
        header = QLabel(f"{section_name} ({count_text})")
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
        header_row.addWidget(header, 1)

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedHeight(22)
        clear_btn.setToolTip(f"Remove all files from {section_name}")
        clear_btn.setEnabled(total_count > 0)
        clear_btn.clicked.connect(
            lambda: self.main_window.clear_section(self.section_name)
        )
        clear_btn.setStyleSheet("""
            QPushButton {
                min-width: 42px;
                padding: 0px 7px;
                background-color: #24244d;
                color: #aaaac6;
                border: 1px solid #45456f;
                border-radius: 5px;
                font-size: 9px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #653b59;
                color: #ffffff;
                border-color: #9a587e;
            }
            QPushButton:disabled {
                color: #555577;
                border-color: #30304f;
            }
        """)
        header_row.addWidget(clear_btn)
        layout.addLayout(header_row)

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
    elif kind == "restart":
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(QRect(4, 4, 12, 12), 35 * 16, 285 * 16)
        painter.setBrush(Qt.white)
        painter.drawPolygon(QPolygon([
            QPoint(4, 4), QPoint(4, 10), QPoint(9, 7)
        ]))
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


class ClickSeekSlider(QSlider):
    """Horizontal slider that supports both direct clicks and dragging."""

    jumpRequested = pyqtSignal(int)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.width() > 0:
            if event.pos().x() >= self.width() - 8:
                value = self.maximum()
                self.setValue(value)
                self.jumpRequested.emit(value)
                event.accept()
                return
            current_ratio = (
                (self.value() - self.minimum())
                / max(1, self.maximum() - self.minimum())
            )
            handle_x = current_ratio * self.width()
            if abs(event.pos().x() - handle_x) <= 12:
                super().mousePressEvent(event)
                return
            ratio = event.pos().x() / self.width()
            ratio = max(0.0, min(1.0, ratio))
            value = round(
                self.minimum()
                + ratio * (self.maximum() - self.minimum())
            )
            self.setValue(value)
            self.jumpRequested.emit(value)
            event.accept()
            return
        super().mousePressEvent(event)


class VideoSurface(QWidget):
    """VLC render target that reports size changes for overlay placement."""

    def __init__(self, preview):
        super().__init__()
        self.preview = preview
        self.setObjectName("video_surface")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.preview.position_center_restart_button()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.preview.toggle_playback(show_feedback=True)
            event.accept()
            return
        super().mousePressEvent(event)


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
        self.playback_finished = False
        self.video_loading_started_at = 0
        self.video_size_attempts = 0
        self.setObjectName("video_preview")
        self.setAttribute(Qt.WA_StyledBackground, True)
        if self.standalone:
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
            QPushButton#center_restart {
                background-color: rgba(0, 0, 0, 150);
                color: #ffffff;
                border: 2px solid rgba(255, 255, 255, 210);
                border-radius: 37px;
            }
            QPushButton#center_restart:hover {
                background-color: rgba(20, 20, 28, 210);
                border-color: #ffffff;
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

        self.video_surface = VideoSurface(self)
        self.video_surface.setMinimumHeight(130)
        self.preview_layout.addWidget(self.video_surface, 1)

        self.video_loading_cover = QLabel(self)
        self.video_loading_cover.setObjectName("video_loading_cover")
        self.video_loading_cover.setAttribute(Qt.WA_NativeWindow, True)
        self.video_loading_cover.setStyleSheet(
            "background-color: #050507; border: none;"
        )
        self.video_loading_cover.hide()

        self.center_restart_btn = QPushButton(self)
        self.center_restart_btn.setObjectName("center_restart")
        self.center_restart_btn.setAttribute(Qt.WA_NativeWindow, True)
        self.center_restart_btn.setIcon(white_media_icon("restart"))
        self.center_restart_btn.setIconSize(QSize(34, 34))
        self.center_restart_btn.setToolTip("Restart preview")
        self.center_restart_btn.setFixedSize(74, 74)
        self.center_restart_btn.setStyleSheet("""
            QPushButton#center_restart {
                background-color: rgba(0, 0, 0, 170);
                color: #ffffff;
                border: 2px solid rgba(255, 255, 255, 220);
                border-radius: 37px;
            }
            QPushButton#center_restart:hover {
                background-color: rgba(20, 20, 28, 225);
                border-color: #ffffff;
            }
        """)
        self.center_restart_btn.clicked.connect(
            lambda _checked=False: self.play_btn.click()
        )
        self.center_restart_btn.hide()

        self.center_feedback = QLabel(self)
        self.center_feedback.setObjectName("center_feedback")
        self.center_feedback.setAlignment(Qt.AlignCenter)
        self.center_feedback.setAttribute(Qt.WA_NativeWindow, True)
        self.center_feedback.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.center_feedback.setFixedSize(74, 74)
        self.center_feedback.setStyleSheet("""
            QLabel#center_feedback {
                background-color: rgba(0, 0, 0, 150);
                border-radius: 37px;
            }
        """)
        self.center_feedback.hide()
        self.feedback_hide_timer = QTimer(self)
        self.feedback_hide_timer.setSingleShot(True)
        self.feedback_hide_timer.timeout.connect(self.center_feedback.hide)

        self.seek_time_feedback = QLabel(self)
        self.seek_time_feedback.setObjectName("seek_time_feedback")
        self.seek_time_feedback.setAlignment(Qt.AlignCenter)
        self.seek_time_feedback.setAttribute(Qt.WA_NativeWindow, True)
        self.seek_time_feedback.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.seek_time_feedback.setStyleSheet("""
            QLabel#seek_time_feedback {
                background-color: rgba(0, 0, 0, 175);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 150);
                border-radius: 11px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        self.seek_time_feedback.hide()
        self.seek_feedback_hide_timer = QTimer(self)
        self.seek_feedback_hide_timer.setSingleShot(True)
        self.seek_feedback_hide_timer.timeout.connect(self.seek_time_feedback.hide)

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

        self.seek_slider = ClickSeekSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.jumpRequested.connect(self.seek_to_slider_value)
        self.seek_slider.sliderPressed.connect(self.start_seeking)
        self.seek_slider.sliderReleased.connect(self.finish_seeking)
        self.seek_slider.valueChanged.connect(self.track_seek_preview)

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
            (Qt.Key_R, self.restart_playback),
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
            try:
                self.player.video_set_mouse_input(False)
                self.player.video_set_key_input(False)
            except Exception:
                pass
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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.position_center_restart_button()

    def position_center_restart_button(self):
        if not hasattr(self, "center_restart_btn"):
            return
        parent = self.center_restart_btn.parentWidget()
        if parent is None:
            return
        surface_top_left = self.video_surface.mapTo(parent, QPoint(0, 0))
        center_x = max(
            0,
            surface_top_left.x()
            + (self.video_surface.width() - self.center_restart_btn.width()) // 2,
        )
        center_y = max(
            0,
            surface_top_left.y()
            + (self.video_surface.height() - self.center_restart_btn.height()) // 2,
        )
        self.center_restart_btn.move(center_x, center_y)
        self.center_feedback.move(center_x, center_y)
        self.position_video_loading_cover()
        self.position_seek_time_feedback()

    def position_video_loading_cover(self):
        if not hasattr(self, "video_loading_cover"):
            return
        parent = self.video_loading_cover.parentWidget()
        if parent is None:
            return
        surface_top_left = self.video_surface.mapTo(parent, QPoint(0, 0))
        self.video_loading_cover.setGeometry(
            surface_top_left.x(),
            surface_top_left.y(),
            self.video_surface.width(),
            self.video_surface.height(),
        )

    def show_video_loading_cover(self):
        if not self.current_is_video:
            return
        self.video_loading_started_at = time.time()
        self.position_video_loading_cover()
        self.video_loading_cover.show()
        self.video_loading_cover.raise_()

    def maybe_hide_video_loading_cover(self, length, current):
        if not self.video_loading_cover.isVisible():
            return
        elapsed = time.time() - self.video_loading_started_at
        first_frame_ready = (
            self.player is not None
            and self.player.is_playing()
            and (current > 120 or elapsed > 1.25)
        )
        if length and first_frame_ready:
            self.video_loading_cover.hide()

    def position_seek_time_feedback(self):
        if not hasattr(self, "seek_time_feedback"):
            return
        parent = self.seek_time_feedback.parentWidget()
        if parent is None:
            return
        surface_top_left = self.video_surface.mapTo(parent, QPoint(0, 0))
        x = max(
            0,
            surface_top_left.x()
            + (self.video_surface.width() - self.seek_time_feedback.width()) // 2,
        )
        y = max(
            0,
            surface_top_left.y()
            + self.video_surface.height()
            - self.seek_time_feedback.height()
            - 18,
        )
        self.seek_time_feedback.move(x, y)

    def slider_value_to_time(self, value):
        if self.player is None:
            return 0, 0
        length = max(0, self.player.get_length())
        max_value = max(1, self.seek_slider.maximum())
        value = max(self.seek_slider.minimum(), min(self.seek_slider.maximum(), value))
        return (round((value / max_value) * length) if length else 0), length

    def set_seek_time_display(self, target, length):
        text = self.format_time(target)
        if length:
            text = f"{text} / {self.format_time(length)}"
        self.seek_time_feedback.setText(text)
        self.seek_time_feedback.adjustSize()
        self.position_seek_time_feedback()
        self.time_label.setText(text)

    def show_seek_time_feedback(self, target, length, temporary=True):
        if not self.current_is_video:
            return
        self.set_seek_time_display(target, length)
        self.seek_time_feedback.show()
        self.seek_time_feedback.raise_()
        if temporary:
            self.seek_feedback_hide_timer.start(1100)
        else:
            self.seek_feedback_hide_timer.stop()

    def hide_seek_time_feedback(self):
        self.seek_feedback_hide_timer.stop()
        self.seek_time_feedback.hide()

    def load_media(self, path, show_video):
        if not self.ensure_player():
            return False
        self.exit_fullscreen()
        self.player.stop()
        self.current_is_video = show_video
        self.set_playback_finished(False)
        self.video_surface.setVisible(show_video)
        self.fullscreen_btn.setVisible(show_video)
        if show_video:
            self.show_video_loading_cover()
        else:
            self.video_loading_cover.hide()
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
        self.hide_seek_time_feedback()
        media = self.instance.media_new_path(os.path.abspath(path))
        self.player.set_media(media)
        if show_video:
            self.bind_video_surface()
            QTimer.singleShot(0, self.position_center_restart_button)
        self.player.play()
        self.set_playing_icon(True)
        self.timer.start()
        if show_video and self.standalone:
            self.video_size_attempts = 0
            QTimer.singleShot(100, self.lock_video_minimum_size)
        return True

    def load_video(self, path):
        return self.load_media(path, show_video=True)

    def lock_video_minimum_size(self):
        if (
            not self.standalone
            or not self.current_is_video
            or self.player is None
        ):
            return
        try:
            video_width, video_height = self.player.video_get_size(0)
        except Exception:
            video_width, video_height = 0, 0

        if video_width <= 0 or video_height <= 0:
            self.video_size_attempts += 1
            if self.video_size_attempts < 30:
                QTimer.singleShot(150, self.lock_video_minimum_size)
            return

        margins = self.preview_layout.contentsMargins()
        title_height = max(
            self.name_label.sizeHint().height(),
            self.close_btn.height(),
            self.escape_hint.sizeHint().height(),
        )
        controls_height = self.controls.sizeHint().height()
        vertical_spacing = self.preview_layout.spacing() * 2
        preview_width = max(1, round(video_width * 0.25))
        preview_height = max(1, round(video_height * 0.25))
        minimum_width = (
            preview_width + margins.left() + margins.right()
        )
        minimum_height = (
            preview_height
            + title_height
            + controls_height
            + margins.top()
            + margins.bottom()
            + vertical_spacing
        )

        self.video_surface.setMinimumSize(preview_width, preview_height)
        self.setMinimumSize(minimum_width, minimum_height)
        self.resize(
            max(self.width(), minimum_width),
            max(self.height(), minimum_height),
        )

    def load_audio(self, path):
        return self.load_media(path, show_video=False)

    def toggle_playback(self, show_feedback=False):
        if self.player is None:
            return
        if self.playback_finished:
            self.restart_playback()
            if show_feedback:
                self.show_center_feedback("play", temporary=True)
            return
        if self.player.is_playing():
            self.player.pause()
            self.set_playing_icon(False)
            self.show_paused_feedback()
        else:
            self.set_playback_finished(False)
            self.player.play()
            self.set_playing_icon(True)
            if show_feedback:
                self.show_center_feedback("play", temporary=True)
            else:
                self.hide_center_feedback()

    def set_playing_icon(self, playing):
        if self.playback_finished and not playing:
            self.play_btn.setIcon(white_media_icon("restart"))
            self.play_btn.setToolTip("Restart preview (Space)")
            return
        self.play_btn.setIcon(white_media_icon("pause" if playing else "play"))
        self.play_btn.setToolTip("Play or pause (Space)")

    def restart_playback(self):
        if self.player is None:
            return
        self.set_playback_finished(False)
        self.hide_center_feedback()
        self.player.stop()
        if self.current_is_video:
            self.bind_video_surface()
            self.show_video_loading_cover()
        self.seek_slider.setValue(0)
        self.time_label.setText("0:00 / 0:00")
        self.hide_seek_time_feedback()
        self.player.play()
        self.set_playing_icon(True)
        self.timer.start()

    def show_center_feedback(self, icon_kind, temporary):
        if not self.current_is_video:
            return
        self.center_feedback.setPixmap(
            white_media_icon(icon_kind).pixmap(QSize(34, 34))
        )
        self.position_center_restart_button()
        self.center_feedback.show()
        self.center_feedback.raise_()
        if temporary:
            self.feedback_hide_timer.start(650)
        else:
            self.feedback_hide_timer.stop()

    def show_paused_feedback(self):
        if (
            self.current_is_video
            and self.player is not None
            and not self.player.is_playing()
            and not self.playback_finished
        ):
            self.show_center_feedback("pause", temporary=False)

    def hide_center_feedback(self):
        self.feedback_hide_timer.stop()
        self.center_feedback.hide()

    def set_playback_finished(self, finished):
        self.playback_finished = finished
        visible = finished and self.current_is_video
        if visible:
            self.hide_center_feedback()
        self.position_center_restart_button()
        self.center_restart_btn.setVisible(visible)
        if visible:
            self.center_restart_btn.raise_()

    def seek_to_slider_value(self, value):
        if self.player is None:
            return
        max_value = max(1, self.seek_slider.maximum())
        value = max(self.seek_slider.minimum(), min(self.seek_slider.maximum(), value))
        length = max(0, self.player.get_length())
        target = round((value / max_value) * length) if length else 0
        self.seek_slider.setValue(value)
        self.seek_to_time(
            target,
            requested_end=value >= self.seek_slider.maximum(),
            show_feedback=True,
        )

    def seek_to_time(self, target, requested_end=False, show_feedback=False):
        if self.player is None:
            return
        length = max(0, self.player.get_length())
        if length:
            target = max(0, min(target, length))
            vlc_target = max(0, length - 50) if target >= length else target
        else:
            vlc_target = max(0, target)
        was_finished = self.playback_finished
        self.set_playback_finished(False)

        def apply_seek(pause_after_finished_restart=False):
            if self.player is None:
                return
            self.player.set_time(vlc_target)
            if requested_end and length:
                self.seek_slider.setValue(self.seek_slider.maximum())
                self.time_label.setText(
                    f"{self.format_time(length)} / {self.format_time(length)}"
                )
                self.player.pause()
                self.set_playback_finished(True)
                self.set_playing_icon(False)
                if show_feedback:
                    self.show_seek_time_feedback(length, length, temporary=True)
                return
            if pause_after_finished_restart:
                self.player.pause()
            self.set_playing_icon(self.player.is_playing())
            self.show_paused_feedback()
            if show_feedback:
                self.show_seek_time_feedback(target, length, temporary=True)

        if was_finished:
            self.player.stop()
            if self.current_is_video:
                self.bind_video_surface()
            self.player.play()
            QTimer.singleShot(80, lambda: apply_seek(True))
            return

        apply_seek(False)

    def skip_seconds(self, seconds):
        if self.player is None:
            return
        length = max(0, self.player.get_length())
        current = max(0, self.player.get_time())
        target = max(0, current + (seconds * 1000))
        if length:
            target = min(length, target)
        self.seek_to_time(
            target,
            requested_end=bool(length and target >= length),
            show_feedback=True,
        )

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
        self.video_loading_cover.setParent(window)
        self.center_restart_btn.setParent(window)
        self.center_feedback.setParent(window)
        self.seek_time_feedback.setParent(window)
        self.fullscreen_window = window

        for key, callback in (
            (Qt.Key_Escape, self.exit_fullscreen),
            (Qt.Key_F, self.exit_fullscreen),
            (Qt.Key_Space, self.toggle_playback),
            (Qt.Key_Left, lambda: self.skip_seconds(-5)),
            (Qt.Key_Right, lambda: self.skip_seconds(5)),
            (Qt.Key_R, self.restart_playback),
        ):
            shortcut = QShortcut(QKeySequence(key), window)
            shortcut.activated.connect(callback)

        window.showFullScreen()
        self.video_surface.show()
        self.video_loading_cover.setVisible(self.video_loading_cover.isVisible())
        self.video_loading_cover.raise_()
        self.center_restart_btn.setVisible(
            self.playback_finished and self.current_is_video
        )
        self.center_restart_btn.raise_()
        self.center_feedback.setVisible(self.center_feedback.isVisible())
        self.center_feedback.raise_()
        self.seek_time_feedback.setVisible(self.seek_time_feedback.isVisible())
        self.seek_time_feedback.raise_()
        QTimer.singleShot(0, self.position_center_restart_button)
        QTimer.singleShot(0, self.bind_video_surface)

    def exit_fullscreen(self):
        window = self.fullscreen_window
        if window is None:
            return
        self.fullscreen_window = None
        self.video_surface.setParent(self)
        self.video_loading_cover.setParent(self)
        self.center_restart_btn.setParent(self)
        self.center_feedback.setParent(self)
        self.seek_time_feedback.setParent(self)
        self.preview_layout.insertWidget(1, self.video_surface, 1)
        self.video_surface.show()
        self.video_loading_cover.setVisible(self.video_loading_cover.isVisible())
        self.video_loading_cover.raise_()
        self.center_restart_btn.setVisible(
            self.playback_finished and self.current_is_video
        )
        self.center_restart_btn.raise_()
        self.center_feedback.setVisible(self.center_feedback.isVisible())
        self.center_feedback.raise_()
        self.seek_time_feedback.setVisible(self.seek_time_feedback.isVisible())
        self.seek_time_feedback.raise_()
        window.close()
        window.deleteLater()
        if not self.closing:
            QTimer.singleShot(0, self.position_center_restart_button)
            QTimer.singleShot(0, self.bind_video_surface)

    def handle_escape(self):
        if self.fullscreen_window is not None:
            self.exit_fullscreen()
        elif self.standalone:
            self.close_preview()

    def start_seeking(self):
        self.user_seeking = True
        target, length = self.slider_value_to_time(self.seek_slider.value())
        self.show_seek_time_feedback(target, length, temporary=False)

    def finish_seeking(self):
        if self.player is not None:
            self.seek_to_slider_value(self.seek_slider.value())
        self.user_seeking = False
        self.seek_feedback_hide_timer.start(1100)

    def track_seek_preview(self, value):
        if not self.user_seeking or self.player is None:
            return
        target, length = self.slider_value_to_time(value)
        self.show_seek_time_feedback(target, length, temporary=False)

    def set_volume(self, value):
        if self.player is not None:
            self.player.audio_set_volume(value)

    def update_controls(self):
        if self.player is None:
            return
        length = max(0, self.player.get_length())
        current = max(0, self.player.get_time())
        self.maybe_hide_video_loading_cover(length, current)
        if not self.user_seeking and length:
            self.seek_slider.setValue(int((current / length) * 1000))
        if self.user_seeking:
            target, preview_length = self.slider_value_to_time(
                self.seek_slider.value()
            )
            self.set_seek_time_display(target, preview_length)
            return
        self.time_label.setText(
            f"{self.format_time(current)} / {self.format_time(length)}"
        )
        finished = bool(
            length and not self.player.is_playing()
            and current >= max(0, length - 500)
        )
        if finished != self.playback_finished:
            self.set_playback_finished(finished)
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
        self.timer.stop()
        if self.player is not None and not self.standalone:
            self.player.stop()
        self.current_path = ""
        self.current_is_video = False
        self.set_playback_finished(False)
        self.video_loading_cover.hide()
        self.hide_seek_time_feedback()
        self.hide_center_feedback()
        self.set_playing_icon(False)
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
        self.current_path = ""
        self.current_is_video = False
        self.set_playback_finished(False)
        self.video_loading_cover.hide()
        self.hide_seek_time_feedback()
        self.hide_center_feedback()
        self.set_playing_icon(False)
        self.timer.stop()
        self.hide()

    def release(self):
        self.exit_fullscreen()
        self.timer.stop()
        if self.player is not None:
            try:
                self.player.stop()
                if platform.system() == "Windows":
                    self.player.set_hwnd(0)
                self.player.set_media(None)
                self.player.release()
            except Exception:
                pass
            self.player = None
        if self.instance is not None:
            try:
                self.instance.release()
            except Exception:
                pass
            self.instance = None

    def closeEvent(self, event):
        if not self.standalone:
            self.release()
            event.accept()
            return

        event.ignore()
        self.hide()
        self.timer.stop()
        for shortcut in self.shortcuts:
            shortcut.setEnabled(False)
        callback = self.on_closed
        self.on_closed = None
        if callback is not None:
            callback(self)
        QTimer.singleShot(100, self.finish_standalone_close)

    def finish_standalone_close(self):
        self.release()
        self.deleteLater()


class ImagePreview(QWidget):
    """Aspect-ratio-preserving image preview embedded below the sections."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_path = ""
        self.source_pixmap = QPixmap()
        self.movie = None
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
        self.stop_movie()
        if os.path.splitext(path)[1].lower() == ".gif":
            movie = QMovie(path)
            movie.setCacheMode(QMovie.CacheAll)
            if not movie.isValid() or not movie.jumpToFrame(0):
                QMessageBox.warning(
                    self, "Image Preview", "This GIF could not be loaded."
                )
                return False
            self.current_path = path
            self.movie = movie
            self.source_pixmap = movie.currentPixmap()
            self.apply_scale_settings()
            self.name_label.setText(os.path.basename(path))
            self.name_label.setToolTip(path)
            self.resize_to_image()
            self.image_surface.setMovie(movie)
            self.show()
            QTimer.singleShot(0, self.update_scaled_image)
            movie.start()
            return True

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
        if self.movie is not None:
            self.movie.setScaledSize(target)
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
        self.stop_movie()
        self.current_path = ""
        self.source_pixmap = QPixmap()
        self.image_surface.clear()
        self.hide()

    def stop_movie(self):
        if self.movie is not None:
            self.movie.stop()
            self.image_surface.setMovie(None)
            self.movie.setFileName("")
            self.movie.deleteLater()
            self.movie = None

    def close_preview(self):
        self.hide_for_switch()
        main_window = self.window()
        if hasattr(main_window, "embedded_preview_closed"):
            main_window.embedded_preview_closed()


class ArrowComboBox(QComboBox):
    """Combo box with a theme-independent white dropdown triangle."""

    POPUP_BACKGROUND = QColor("#202044")

    def __init__(self, parent=None):
        super().__init__(parent)
        view = self.view()
        view.setFrameShape(QFrame.NoFrame)
        view.setContentsMargins(0, 0, 0, 0)
        view.setAutoFillBackground(True)
        view.viewport().setAutoFillBackground(True)
        self._apply_popup_palette(view)
        self._apply_popup_palette(view.viewport())

    def _apply_popup_palette(self, widget):
        palette = widget.palette()
        for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
            palette.setColor(group, QPalette.Window, self.POPUP_BACKGROUND)
            palette.setColor(group, QPalette.Base, self.POPUP_BACKGROUND)
            palette.setColor(group, QPalette.AlternateBase, self.POPUP_BACKGROUND)
        widget.setPalette(palette)

    def showPopup(self):
        super().showPopup()
        view = self.view()
        popup = view.window()

        self._apply_popup_palette(view)
        self._apply_popup_palette(view.viewport())
        self._apply_popup_palette(popup)
        popup.setAutoFillBackground(True)
        popup.setAttribute(Qt.WA_StyledBackground, True)
        if isinstance(popup, QFrame):
            popup.setFrameShape(QFrame.NoFrame)
        popup.setStyleSheet(
            "background-color: #202044;"
            "border: 1px solid #51517f;"
            "padding: 0px;"
            "margin: 0px;"
        )
        if popup.layout():
            popup.layout().setContentsMargins(0, 0, 0, 0)
            popup.layout().setSpacing(0)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#ffffff"))
        center_x = self.width() - 13
        center_y = self.height() // 2 + 1
        painter.drawPolygon(QPolygon([
            QPoint(center_x - 5, center_y - 3),
            QPoint(center_x + 5, center_y - 3),
            QPoint(center_x, center_y + 4),
        ]))


class DownloadDialog(QDialog):
    """Collect URL download settings without blocking the main UI."""

    def __init__(
        self, sections, default_folder, parent=None, initial_url="",
        direct_file=False, suggested_filename="", mime_type="", referer=""
    ):
        super().__init__(parent)
        self.direct_file = direct_file
        self.suggested_filename = suggested_filename
        self.mime_type = mime_type
        self.referer = referer
        self.setWindowTitle("Download Media")
        self.setMinimumWidth(430)
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a2e;
                color: #ddddef;
            }
            QLabel {
                color: #aaaac6;
                font-size: 11px;
            }
            QLineEdit, QComboBox {
                min-height: 30px;
                padding: 3px 7px;
                background-color: #16213e;
                color: #eeeeff;
                border: 1px solid #3a3a66;
                border-radius: 5px;
            }
            QComboBox::drop-down {
                width: 24px;
                background-color: #24244d;
                border-left: 1px solid #3a3a66;
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
            }
            QComboBox::down-arrow {
                image: none;
                width: 0px;
                height: 0px;
            }
            QComboBox QAbstractItemView {
                background-color: #202044;
                alternate-background-color: #202044;
                color: #eeeeff;
                border: 1px solid #51517f;
                selection-background-color: #6C63FF;
                selection-color: #ffffff;
                outline: none;
                padding: 0px;
                margin: 0px;
            }
            QComboBox QAbstractItemView QWidget {
                background-color: #202044;
            }
            QComboBox QAbstractItemView::item {
                min-height: 26px;
                padding: 3px 7px;
                background-color: #202044;
                color: #eeeeff;
            }
            QComboBox QAbstractItemView::item:hover,
            QComboBox QAbstractItemView::item:selected {
                background-color: #6C63FF;
                color: #ffffff;
            }
            QComboBox QScrollBar:vertical {
                width: 8px;
                background-color: #202044;
                margin: 0px;
            }
            QComboBox QScrollBar::handle:vertical {
                min-height: 18px;
                background-color: #51517f;
                border-radius: 4px;
            }
            QComboBox QScrollBar::add-line:vertical,
            QComboBox QScrollBar::sub-line:vertical,
            QComboBox QScrollBar::add-page:vertical,
            QComboBox QScrollBar::sub-page:vertical {
                height: 0px;
                background-color: #202044;
            }
            QPushButton {
                min-height: 30px;
                padding: 5px 12px;
                background-color: #24244d;
                color: white;
                border: 1px solid #45456f;
                border-radius: 5px;
            }
            QPushButton#download_confirm {
                background-color: #6C63FF;
                border-color: #6C63FF;
                font-weight: bold;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Media URL"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://...")
        self.url_input.setText(initial_url)
        layout.addWidget(self.url_input)

        option_row = QHBoxLayout()
        mode_col = QVBoxLayout()
        mode_col.addWidget(QLabel("Download as"))
        self.mode_combo = ArrowComboBox()
        if direct_file:
            self.mode_combo.addItem("Original file")
            self.mode_combo.setEnabled(False)
        else:
            self.mode_combo.addItems(["Video (MP4)", "Audio (MP3)"])
        self.mode_combo.currentIndexChanged.connect(self.update_mode)
        mode_col.addWidget(self.mode_combo)

        quality_col = QVBoxLayout()
        quality_col.addWidget(QLabel("Quality"))
        self.quality_combo = ArrowComboBox()
        quality_col.addWidget(self.quality_combo)

        section_col = QVBoxLayout()
        section_col.addWidget(QLabel("PremieDrop section"))
        self.section_combo = ArrowComboBox()
        self.section_combo.addItems([section["name"] for section in sections])
        section_col.addWidget(self.section_combo)

        option_row.addLayout(mode_col)
        option_row.addLayout(quality_col)
        option_row.addLayout(section_col)
        layout.addLayout(option_row)

        layout.addWidget(QLabel("Save folder"))
        folder_row = QHBoxLayout()
        self.folder_input = QLineEdit(default_folder)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.choose_folder)
        folder_row.addWidget(self.folder_input, 1)
        folder_row.addWidget(browse_btn)
        layout.addLayout(folder_row)

        permission_note = QLabel("Download only media you have permission to use.")
        permission_note.setStyleSheet("color: #777799; font-size: 10px;")
        layout.addWidget(permission_note)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        download_btn = QPushButton("Download")
        download_btn.setObjectName("download_confirm")
        download_btn.clicked.connect(self.validate_and_accept)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(download_btn)
        layout.addLayout(buttons)

        self.update_mode()

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Choose Download Folder",
            self.folder_input.text()
        )
        if folder:
            self.folder_input.setText(folder)

    def update_mode(self):
        if self.direct_file:
            self.quality_combo.clear()
            self.quality_combo.addItem("Original")
            self.quality_combo.setEnabled(False)
            preferred = direct_download_section(
                self.suggested_filename, self.mime_type
            )
            index = self.section_combo.findText(preferred)
            if index >= 0:
                self.section_combo.setCurrentIndex(index)
            return

        is_audio = self.mode_combo.currentIndex() == 1
        self.quality_combo.clear()
        if is_audio:
            self.quality_combo.addItems(["320 kbps", "192 kbps", "128 kbps"])
            preferred = "Sound effects (.mp3 etc)"
        else:
            self.quality_combo.addItems(["Best", "1080p", "720p", "480p"])
            preferred = "Short Video Files (1GB<)"
        index = self.section_combo.findText(preferred)
        if index >= 0:
            self.section_combo.setCurrentIndex(index)

    def validate_and_accept(self):
        url = self.url_input.text().strip()
        folder = self.folder_input.text().strip()
        if not url.startswith(("http://", "https://")):
            QMessageBox.warning(self, "Invalid URL", "Enter a valid HTTP or HTTPS URL.")
            return
        if not folder:
            QMessageBox.warning(self, "No Folder", "Choose where the download should be saved.")
            return
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, "Folder Error", str(exc))
            return
        self.accept()

    def settings(self):
        return {
            "url": self.url_input.text().strip(),
            "folder": os.path.normpath(self.folder_input.text().strip()),
            "download_type": "direct" if self.direct_file else "media",
            "suggested_filename": self.suggested_filename,
            "mime_type": self.mime_type,
            "referer": self.referer,
            "mode": "audio" if self.mode_combo.currentIndex() == 1 else "video",
            "quality": self.quality_combo.currentText(),
            "section": self.section_combo.currentText(),
        }


class DownloadWorker(QThread):
    progress = pyqtSignal(int, str)
    completed = pyqtSignal(str, str)
    failed = pyqtSignal(str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings

    def progress_hook(self, data):
        status = data.get("status")
        if status == "downloading":
            downloaded = data.get("downloaded_bytes", 0)
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            percent = int(downloaded * 100 / total) if total else 0
            speed = data.get("_speed_str", "").strip()
            eta = data.get("_eta_str", "").strip()
            detail = "Downloading"
            if speed:
                detail += f" at {speed}"
            if eta:
                detail += f" - ETA {eta}"
            self.progress.emit(percent, detail)
        elif status == "finished":
            self.progress.emit(100, "Processing media...")

    def format_selector(self):
        quality = self.settings["quality"]
        if self.settings["mode"] == "audio":
            return "bestaudio/best"
        if quality == "Best":
            return "bv*[vcodec!*=av01][vcodec!*=vp9]+ba/b"
        height = "".join(character for character in quality if character.isdigit())
        return (
        f"bv*[height<={height}][vcodec!*=av01][vcodec!*=vp9]+ba/"
        f"b[height<={height}]/best[height<={height}]"
    )

    def find_output_path(self, info, prepared_path):
        expected_extension = "mp3" if self.settings["mode"] == "audio" else "mp4"
        expected = os.path.splitext(prepared_path)[0] + "." + expected_extension
        if os.path.exists(expected):
            return expected

        video_id = str(info.get("id", ""))
        candidates = []
        for name in os.listdir(self.settings["folder"]):
            path = os.path.join(self.settings["folder"], name)
            if not os.path.isfile(path):
                continue
            if video_id and f"[{video_id}]" not in name:
                continue
            if os.path.splitext(name)[1].lower() not in ALL_EXTENSIONS:
                continue
            candidates.append(path)
        if candidates:
            return max(candidates, key=os.path.getmtime)
        return expected

    def run(self):
        if yt_dlp is None:
            self.failed.emit(
                'yt-dlp is not installed. Run: python -m pip install "yt-dlp[default]"'
            )
            return

        settings = self.settings
        options = {
            "format": self.format_selector(),
            "outtmpl": os.path.join(
                settings["folder"],
                "%(title).180B [%(id)s].%(ext)s"
            ),
            "noplaylist": True,
            "progress_hooks": [self.progress_hook],
            "quiet": True,
            "no_warnings": True,
            "windowsfilenames": platform.system() == "Windows",
            "restrictfilenames": True,  # <-- add this line
            "keepvideo": False,
            "nopart": True,
            "noresumethreshold": 0,
            "continuedl": False,
        }

        ffmpeg_path = get_ffmpeg_path()
        if ffmpeg_path:
            options["ffmpeg_location"] = ffmpeg_path

        if settings["mode"] == "audio":
            bitrate = settings["quality"].split()[0]
            options["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": bitrate,
            }]
        else:
            options["merge_output_format"] = "mp4"
            options["postprocessors"] = [
                {
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            },
            ]
            options["postprocessor_args"] = {
                "merger": ["-c:a", "aac", "-b:a", "192k", "-c:v", "copy"]
            }

        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                info = downloader.extract_info(settings["url"], download=True)
                prepared_path = downloader.prepare_filename(info)
            output_path = self.find_output_path(info, prepared_path)
            if not os.path.exists(output_path):
                raise FileNotFoundError("The download completed but its output file was not found.")
            self.completed.emit(output_path, settings["section"])
        except Exception as exc:
            self.failed.emit(str(exc))


class DirectFileDownloadWorker(QThread):
    progress = pyqtSignal(int, str)
    completed = pyqtSignal(str, str)
    failed = pyqtSignal(str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings

    def safe_filename(self, name):
        name = unquote(name or "").strip()
        name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
        name = name.rstrip(". ")
        return name[:180] or "download"

    def response_filename(self, response):
        content_disposition = response.headers.get(
            "Content-Disposition", ""
        )
        encoded_match = re.search(
            r"filename\\*=UTF-8''([^;]+)", content_disposition, re.I
        )
        if encoded_match:
            return unquote(encoded_match.group(1))
        quoted_match = re.search(
            r'filename="?([^";]+)"?', content_disposition, re.I
        )
        if quoted_match:
            return quoted_match.group(1)
        return ""

    def unique_path(self, folder, filename):
        base, extension = os.path.splitext(filename)
        candidate = os.path.join(folder, filename)
        number = 2
        while os.path.exists(candidate):
            candidate = os.path.join(
                folder, f"{base} ({number}){extension}"
            )
            number += 1
        return candidate

    def run(self):
        settings = self.settings
        output_path = ""
        try:
            request = Request(
                settings["url"],
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 Chrome/124 Safari/537.36"
                    ),
                    "Accept": "*/*",
                    **(
                        {"Referer": settings["referer"]}
                        if settings.get("referer") else {}
                    ),
                },
            )
            with urlopen(request, timeout=45) as response:
                response_mime = response.headers.get_content_type()
                if response_mime in ("text/html", "application/xhtml+xml"):
                    raise ValueError(
                        "This link points to a webpage, not a downloadable file."
                    )
                filename = (
                    settings.get("suggested_filename")
                    or self.response_filename(response)
                    or os.path.basename(urlparse(response.url).path)
                    or "download"
                )
                filename = self.safe_filename(filename)
                if not os.path.splitext(filename)[1]:
                    extension = mimetypes.guess_extension(response_mime) or ""
                    if extension == ".jpe":
                        extension = ".jpg"
                    filename += extension
                output_path = self.unique_path(settings["folder"], filename)
                total = int(response.headers.get("Content-Length", 0) or 0)
                downloaded = 0
                with open(output_path, "wb") as output_file:
                    while True:
                        chunk = response.read(256 * 1024)
                        if not chunk:
                            break
                        output_file.write(chunk)
                        downloaded += len(chunk)
                        percent = int(downloaded * 100 / total) if total else 0
                        self.progress.emit(
                            percent,
                            f"Downloading {filename}"
                        )
            self.completed.emit(output_path, settings["section"])
        except Exception as exc:
            if output_path and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except OSError:
                    pass
            self.failed.emit(str(exc))


class UpdateInstallerWorker(QThread):
    progress = pyqtSignal(int, str)
    completed = pyqtSignal(str, str)
    failed = pyqtSignal(str)

    def run(self):
        try:
            self.progress.emit(0, "Checking latest release...")
            request = Request(
                LATEST_RELEASE_API,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "PremieDrop-Updater",
                },
            )
            with urlopen(request, timeout=30) as response:
                release = json.loads(response.read().decode("utf-8"))

            asset = None
            for candidate in release.get("assets", []):
                name = str(candidate.get("name", ""))
                if (
                    name.lower().startswith("premiedropinstaller")
                    and name.lower().endswith(".exe")
                ):
                    asset = candidate
                    break
            if asset is None:
                raise RuntimeError(
                    "No PremieDrop installer was found on the latest release."
                )

            download_url = asset.get("browser_download_url")
            filename = asset.get("name") or "PremieDropInstaller-latest.exe"
            if not download_url:
                raise RuntimeError("The latest installer asset has no download URL.")

            update_dir = os.path.join(
                local_app_data_dir(), "PremieDrop", "updates"
            )
            os.makedirs(update_dir, exist_ok=True)
            destination = os.path.join(update_dir, filename)
            temporary = f"{destination}.download"

            self.progress.emit(5, f"Downloading {filename}...")
            with urlopen(
                Request(download_url, headers={"User-Agent": "PremieDrop-Updater"}),
                timeout=60,
            ) as response:
                total = int(response.headers.get("Content-Length", "0") or 0)
                downloaded = 0
                with open(temporary, "wb") as installer_file:
                    while True:
                        chunk = response.read(1024 * 512)
                        if not chunk:
                            break
                        installer_file.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            percent = min(99, max(5, int(downloaded * 100 / total)))
                            self.progress.emit(percent, f"Downloading {filename}...")

            os.replace(temporary, destination)
            self.progress.emit(100, "Installer ready.")
            self.completed.emit(destination, release.get("tag_name", "latest"))
        except Exception as exc:
            try:
                if "temporary" in locals() and os.path.exists(temporary):
                    os.remove(temporary)
            except OSError:
                pass
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        extension_root = os.path.dirname(__file__)
        self.import_registry = ImportRegistry()
        self.import_registry.discover(
            os.path.join(extension_root, "import_providers")
        )
        self.ui_extension_registry = UIExtensionRegistry()
        self.ui_extension_registry.discover(
            os.path.join(extension_root, "ui_plugins")
        )
        self.write_extension_diagnostics()
        self.section_refresh_pending = False
        self.video_windows = []
        self.embedded_previous_size = None
        self.download_worker = None
        self.update_worker = None
        self.closing_for_update_installer = False
        self.youtube_browser_process = None
        self.youtube_browser_launch_time = 0
        self.embedded_browser_view = None
        self.embedded_browser_url = None
        self.embedded_browser_load_label = None
        self.embedded_browser_menu = None
        self.embedded_browser_presets = []
        self.embedded_browser_presets_path = os.path.join(
            APP_DATA_DIR, "browser_presets.json"
        )
        self.embedded_last_default_browser_tab = "youtube"
        self.youtube_panel_attached = False
        self.youtube_panel_width = 0
        self.youtube_base_width = BASE_WINDOW_WIDTH
        self.youtube_request_timer = QTimer(self)
        self.youtube_request_timer.setInterval(200)
        self.youtube_request_timer.timeout.connect(
            self.check_youtube_browser
        )
        self.youtube_request_timer.start()
        self.sections = load_sections()
        self.load_embedded_browser_presets()
        self.saved_files = self.all_files()
        self.project_folder = load_project_folder()
        self.last_download_folder = load_last_download_folder()
        sync_import_queue_folder(self.project_folder)
        self.init_ui()
        self.populate_list()

    def showEvent(self, event):
        super().showEvent(event)
        self.ensure_video_preview()

    def ensure_video_preview(self):
        if self.video_preview is not None:
            return self.video_preview
        self.video_preview = VideoPreview(self)
        self.video_preview.enable_compact_audio_mode()
        self.video_preview.setMinimumWidth(200)
        self.video_preview.setMaximumWidth(250)
        self.video_preview.hide()
        self._video_preview_header.insertSpacing(1, 8)
        self._video_preview_header.insertWidget(2, self.video_preview, 1)
        return self.video_preview

    def all_files(self):
        files = []
        for section in self.sections:
            for path in section["files"]:
                if path not in files:
                    files.append(path)
        return files

    def save_library(self):
        self.saved_files = self.all_files()
        save_files(
            self.saved_files,
            self.project_folder,
            self.sections,
            self.last_download_folder,
        )

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
        self.update_window_size_label()
        if hasattr(self, "file_list"):
            self.schedule_section_refresh()

    def update_window_size_label(self):
        if hasattr(self, "window_size_label"):
            self.window_size_label.setText(
                f"{self.width()} × {self.height()}"
            )

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
            self.video_preview is not None
            and not self.video_preview.isHidden()
        )
        image_active = (
            hasattr(self, "image_preview")
            and not self.image_preview.isHidden()
        )
        return audio_active or image_active

    def required_window_width(self):
        if self.youtube_panel_attached:
            return self.youtube_base_width + YOUTUBE_PANEL_MIN_WIDTH
        return self.youtube_base_width

    def update_window_minimum_size(self, expand=False):
        minimum_height = self.minimum_height_for_sections()
        self.setMinimumWidth(self.required_window_width())
        if self.embedded_preview_active():
            locked_height = max(minimum_height, self.height())
            self.setMinimumHeight(locked_height)
            self.setMaximumHeight(locked_height)
        else:
            self.setMaximumHeight(16777215)
            self.setMinimumHeight(minimum_height)

    def init_ui(self):
        self.setWindowTitle(APP_TEXT["window_title"])
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
            QPushButton#section_btn:pressed {
                background-color: #181833;
            }
            QPushButton#section_btn:disabled {
                background-color: transparent;
                color: #555577;
                border-color: #222233;
            }
            QPushButton#download_btn {
                background-color: #2b4c7e;
                color: #ffffff;
                border: 1px solid #416da8;
                border-radius: 8px;
                padding: 8px 10px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton#download_btn:hover {
                background-color: #35619c;
            }
            QPushButton#download_btn:pressed {
                background-color: #27466f;
            }
            QPushButton#download_btn:disabled {
                background-color: #20283a;
                color: #777788;
                border-color: #30394f;
            }
            QPushButton#web_btn {
                background-color: #4b356f;
                color: #ffffff;
                border: 1px solid #6b4d99;
                border-radius: 8px;
                padding: 8px 10px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton#web_btn:hover {
                background-color: #60448c;
            }
            QPushButton#web_btn:pressed {
                background-color: #3b2958;
            }

            QPushButton#web_btn:disabled {
                background-color: #252033;
                color: #666677;
                border-color: #333344;
            }
            QMenu#web_menu {
                background-color: #16213e;
                color: #eeeeff;
                border: 1px solid #51517f;
                padding: 5px;
            }
            QMenu#web_menu::item {
                min-width: 150px;
                padding: 8px 22px 8px 12px;
                border-radius: 5px;
            }
            QMenu#web_menu::item:selected {
                background-color: #7b72ff;
                color: #ffffff;
                border: 1px solid #d7d4ff;
                font-weight: bold;
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
            QPushButton#clear_btn:pressed {
                background-color: #181833;
            }
            QPushButton#clear_btn:disabled {
                color: #555577;
                border-color: #222233;
            }
            QToolButton#copy_btn {
                background-color: #1a6b3a;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QToolButton#copy_btn:hover {
                background-color: #1e8048;
            }
            QToolButton#copy_btn:pressed {
                background-color: #166030;
            }
            QToolButton#copy_btn:disabled {
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
            QPushButton#set_folder_btn:pressed {
                background-color: #181833;
            }
            QPushButton#set_folder_btn:disabled {
                color: #555577;
                border-color: #222233;
            }
            QPushButton#update_btn {
                background-color: transparent;
                color: #aaaaff;
                border: 1px solid #3a3a66;
                border-radius: 7px;
                padding: 5px 10px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton#update_btn:hover {
                background-color: #24244d;
                color: #ffffff;
            }
            QPushButton#update_btn:pressed {
                background-color: #181833;
            }
            QPushButton#update_btn:disabled {
                color: #555577;
                border-color: #2a2a4a;
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
            QLabel#window_size_label {
                color: #777799;
                font-size: 10px;
                font-family: Consolas;
            }
            QLabel#drag_tip {
                color: #44446a;
                font-size: 11px;
                font-style: italic;
            }
            QLineEdit#library_search {
                min-height: 28px;
                padding: 0px 10px;
                background-color: #16213e;
                color: #eeeeff;
                border: 1px solid #3a3a66;
                border-radius: 7px;
                font-size: 11px;
                selection-background-color: #6C63FF;
            }
            QLineEdit#library_search:focus {
                border-color: #6C63FF;
            }
        """)

        self.apply_theme_config()

        window_body = QWidget()
        window_body.setObjectName("central")
        self.setCentralWidget(window_body)
        window_body_layout = QHBoxLayout(window_body)
        window_body_layout.setContentsMargins(0, 0, 0, 0)
        window_body_layout.setSpacing(0)

        central = QWidget()
        central.setObjectName("central")
        central.setFixedWidth(BASE_WINDOW_WIDTH)
        window_body_layout.addWidget(central)

        self.youtube_host = QWidget()
        self.youtube_host.setObjectName("youtube_host")
        self.youtube_host.setStyleSheet(
            "background-color: #111126; border-left: 1px solid #35355f;"
        )
        self.youtube_host.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        self.youtube_host.setFixedWidth(0)
        self.youtube_host_layout = QVBoxLayout(self.youtube_host)
        self.youtube_host_layout.setContentsMargins(8, 8, 8, 8)
        self.youtube_host_layout.setSpacing(6)
        window_body_layout.addWidget(self.youtube_host)

        layout = QVBoxLayout(central)
        margin = UI_SIZES["main_margin"]
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(UI_SIZES["main_spacing"])

        # ── Header ───────────────────────────────────────────────────
        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)

        title = QLabel(APP_TEXT["title"])
        title.setObjectName("title")

        title_col.addWidget(title)

        self.count_label = QLabel("")
        self.count_label.setObjectName("count_label")
        self.count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.window_size_label = QLabel("")
        self.window_size_label.setObjectName("window_size_label")
        self.window_size_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.update_window_size_label()

        self.video_preview = None
        self._video_preview_header = header
        self.update_btn = QPushButton("Install Update")
        self.update_btn.setObjectName("update_btn")
        self.update_btn.setToolTip("Download and run the latest PremieDrop installer")
        self.update_btn.setFixedHeight(28)
        self.update_btn.clicked.connect(self.install_update)
        header.addLayout(title_col)
        header.addStretch()
        header.addWidget(self.update_btn)
        header.addWidget(self.window_size_label)
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

        self.search_input = QLineEdit()
        self.search_input.setObjectName("library_search")
        self.search_input.setPlaceholderText(
            APP_TEXT["search_placeholder"]
        )
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.populate_list)
        layout.addWidget(self.search_input)

        self.download_progress_row = QWidget()
        download_progress_layout = QHBoxLayout(self.download_progress_row)
        download_progress_layout.setContentsMargins(0, 0, 0, 0)
        download_progress_layout.setSpacing(8)
        self.download_status = QLabel("Downloading...")
        self.download_status.setStyleSheet("color: #aaaac6; font-size: 10px;")
        self.download_progress = QProgressBar()
        self.download_progress.setRange(0, 100)
        self.download_progress.setTextVisible(True)
        self.download_progress.setStyleSheet("""
            QProgressBar {
                min-height: 14px;
                background-color: #16213e;
                color: #ffffff;
                border: 1px solid #35355f;
                border-radius: 4px;
                text-align: center;
                font-size: 9px;
            }
            QProgressBar::chunk {
                background-color: #6C63FF;
                border-radius: 3px;
            }
        """)
        download_progress_layout.addWidget(self.download_status)
        download_progress_layout.addWidget(self.download_progress, 1)
        self.download_progress_row.hide()
        layout.addWidget(self.download_progress_row)

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
        library_tools_row = QHBoxLayout()
        library_tools_row.setSpacing(6)

        section_btn = QPushButton(APP_TEXT["add_section"])
        section_btn.setObjectName("section_btn")
        section_btn.clicked.connect(self.add_section)
        section_btn.setFixedHeight(UI_SIZES["tool_button_height"])

        download_btn = QPushButton(APP_TEXT["download_url"])
        download_btn.setObjectName("download_btn")
        download_btn.setToolTip("Download media from a URL")
        download_btn.clicked.connect(self.open_download_dialog)
        download_btn.setFixedHeight(UI_SIZES["tool_button_height"])
        download_btn.setFixedWidth(UI_SIZES["url_button_width"])

        load_preset_btn = QPushButton("Load Preset")
        load_preset_btn.setObjectName("set_folder_btn")
        load_preset_btn.clicked.connect(self.load_library_preset)
        load_preset_btn.setFixedHeight(34)

        save_preset_btn = QPushButton("Save Preset")
        save_preset_btn.setObjectName("set_folder_btn")
        save_preset_btn.clicked.connect(self.save_library_preset)
        save_preset_btn.setFixedHeight(34)

        library_tools_row.addWidget(section_btn)
        library_tools_row.addWidget(download_btn)
        self.add_ui_extensions(
            "library_tools", layout=library_tools_row
        )
        library_tools_row.addStretch()
        library_tools_row.addWidget(load_preset_btn)
        library_tools_row.addWidget(save_preset_btn)
        layout.addLayout(library_tools_row)

        # ── Project folder section ───────────────────────────────────
        folder_line = QFrame()
        folder_line.setFrameShape(QFrame.HLine)
        folder_line.setStyleSheet("background-color: #2a2a4a; border: none; max-height: 1px;")
        layout.addWidget(folder_line)

        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)

        self.folder_label = ClickableFolderLabel("No project folder set")
        self.folder_label.setObjectName("folder_label")
        self.folder_label.setProperty("active", False)
        self.folder_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.folder_label.clicked.connect(self.show_project_folder_contents)

        set_folder_btn = QPushButton("📁  Set Folder")
        set_folder_btn.setObjectName("set_folder_btn")
        set_folder_btn.setFixedHeight(32)
        set_folder_btn.clicked.connect(self.set_project_folder)

        self.auto_organize_btn = QPushButton("Auto Organize")
        self.auto_organize_btn.setObjectName("set_folder_btn")
        self.auto_organize_btn.setToolTip(
            "Move loose media in the project folder into preset section folders"
        )
        self.auto_organize_btn.clicked.connect(self.auto_organize_assets)
        self.auto_organize_btn.setFixedHeight(32)

        self.reload_assets_btn = QPushButton("Reload Assets")
        self.reload_assets_btn.setObjectName("set_folder_btn")
        self.reload_assets_btn.setToolTip(
            "Rescan preset section folders into the PremieDrop library"
        )
        self.reload_assets_btn.clicked.connect(self.reload_assets)
        self.reload_assets_btn.setFixedHeight(32)

        folder_row.addWidget(self.folder_label)
        folder_row.addWidget(set_folder_btn)
        folder_row.addStretch()
        folder_row.addWidget(self.auto_organize_btn)
        folder_row.addWidget(self.reload_assets_btn)
        layout.addLayout(folder_row)

        # ── Buttons ──────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        add_btn = QPushButton(APP_TEXT["add_files"])
        add_btn.setObjectName("add_btn")
        add_btn.clicked.connect(self.browse_files)
        add_btn.setFixedHeight(UI_SIZES["primary_button_height"])

        web_btn = QPushButton(APP_TEXT["web"])
        web_btn.setObjectName("web_btn")
        web_btn.setToolTip("Open the persistent media browser")
        web_btn.setFixedHeight(UI_SIZES["primary_button_height"])
        web_btn.setFixedWidth(UI_SIZES["web_button_width"])
        web_menu = QMenu(web_btn)
        web_menu.setObjectName("web_menu")
        youtube_action = web_menu.addAction("YouTube")
        youtube_action.triggered.connect(self.open_youtube_browser)
        myinstants_action = web_menu.addAction("MyInstants")
        myinstants_action.triggered.connect(self.open_myinstants_browser)
        tenor_action = web_menu.addAction("Tenor")
        tenor_action.triggered.connect(self.open_tenor_browser)
        web_menu.addSeparator()
        youtube_search_action = web_menu.addAction("Search YouTube...")
        youtube_search_action.triggered.connect(self.search_youtube_browser)
        myinstants_search_action = web_menu.addAction("Search MyInstants...")
        myinstants_search_action.triggered.connect(self.search_myinstants_browser)
        tenor_search_action = web_menu.addAction("Search Tenor GIFs...")
        tenor_search_action.triggered.connect(self.search_tenor_browser)
        giphy_search_action = web_menu.addAction("Search Giphy GIFs...")
        giphy_search_action.triggered.connect(self.search_giphy_browser)
        web_menu.addSeparator()
        website_action = web_menu.addAction("Search Website")
        website_action.triggered.connect(self.open_website_search)
        images_action = web_menu.addAction("Search Images")
        images_action.triggered.connect(self.open_image_search)
        self.add_ui_extensions("web_menu", menu=web_menu)
        web_btn.setMenu(web_menu)

        editor_settings = load_editor_settings()
        self.last_premiere_target = editor_settings.get(
            "last_premiere_target", "premiere_cep"
        )
        if self.last_premiere_target not in (
            "premiere_cep", "premiere_uxp"
        ):
            self.last_premiere_target = "premiere_cep"
        self.import_target = editor_settings.get(
            "selected_target", self.last_premiere_target
        )
        self.copy_btn = QToolButton()
        self.copy_btn.setObjectName("copy_btn")
        self.copy_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.copy_btn.setPopupMode(QToolButton.MenuButtonPopup)
        self.copy_btn.clicked.connect(self.import_to_selected_editor)
        self.copy_btn.setFixedHeight(
            UI_SIZES["primary_button_height"]
        )
        self.copy_btn.setMinimumWidth(
            UI_SIZES["import_button_min_width"]
        )
        self.copy_btn.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed
        )
        import_menu = QMenu(self.copy_btn)
        import_menu.setObjectName("web_menu")
        self.import_actions = {}
        self.build_import_provider_menu(import_menu)

        self.copy_btn.setMenu(import_menu)
        if (
            self.import_target not in self.import_actions
            or not self.import_registry.get(self.import_target).available
        ):
            self.import_target = self.last_premiere_target
        self.select_import_target(self.import_target)

        clear_btn = QPushButton(APP_TEXT["clear_all"])
        clear_btn.setObjectName("clear_btn")
        clear_btn.clicked.connect(self.clear_all)
        clear_btn.setFixedHeight(UI_SIZES["primary_button_height"])
        clear_btn.setFixedWidth(UI_SIZES["clear_button_width"])

        btn_row.addWidget(add_btn)
        btn_row.addWidget(web_btn)
        self.add_ui_extensions(
            "primary_actions", layout=btn_row
        )
        btn_row.addWidget(self.copy_btn, 1)
        btn_row.addWidget(clear_btn)
        layout.addLayout(btn_row)

        # Set initial folder label state
        self.update_folder_label()

    # ── File management ──────────────────────────────────────────────

    def open_youtube_browser(self):
        self.open_media_browser("youtube")

    def open_myinstants_browser(self):
        self.open_media_browser("myinstants")

    def open_tenor_browser(self):
        self.open_media_browser("tenor")

    def search_youtube_browser(self):
        self.open_media_browser("youtube_search")

    def search_myinstants_browser(self):
        self.open_media_browser("myinstants_search")

    def search_tenor_browser(self):
        self.open_media_browser("tenor_search")

    def search_giphy_browser(self):
        self.open_media_browser("giphy_search")

    def open_image_search(self):
        self.open_media_browser("images")

    def open_website_search(self):
        self.open_media_browser("search")

    def ensure_embedded_browser(self):
        if self.embedded_browser_view is not None:
            return self.embedded_browser_view

        try:
            from PyQt5.QtWebEngineWidgets import QWebEngineView
        except (ImportError, OSError) as exc:
            QMessageBox.critical(
                self,
                "Media Browser Unavailable",
                "The embedded browser could not load PyQtWebEngine.\n\n"
                f"Details: {exc}",
            )
            return None

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        back_btn = QToolButton()
        back_btn.setText("‹")
        back_btn.setToolTip("Back")
        back_btn.setFixedSize(30, 30)

        forward_btn = QToolButton()
        forward_btn.setText("›")
        forward_btn.setToolTip("Forward")
        forward_btn.setFixedSize(30, 30)

        reload_btn = QToolButton()
        reload_btn.setText("↻")
        reload_btn.setToolTip("Reload")
        reload_btn.setFixedSize(30, 30)

        close_btn = QToolButton()
        close_btn.setText("×")
        close_btn.setToolTip("Close browser")
        close_btn.setFixedSize(30, 30)

        browser_tool_style = (
            "QToolButton {"
            "background-color: #101024;"
            "color: #ffffff;"
            "border: 1px solid #35355f;"
            "border-radius: 5px;"
            "font-size: 18px;"
            "font-weight: bold;"
            "}"
            "QToolButton:hover {"
            "background-color: #24244d;"
            "border-color: #6C63FF;"
            "}"
        )
        for button in (back_btn, forward_btn, reload_btn, close_btn):
            button.setStyleSheet(browser_tool_style)

        self.embedded_browser_url = QToolButton()
        self.embedded_browser_url.setText("Open website")
        self.embedded_browser_url.setToolTip("Open website")
        self.embedded_browser_url.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.embedded_browser_url.setPopupMode(QToolButton.InstantPopup)
        self.embedded_browser_url.setFixedHeight(30)
        self.embedded_browser_url.setMinimumWidth(220)
        self.embedded_browser_url.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed
        )
        self.embedded_browser_url.setStyleSheet(
            "background-color: #101024; color: #eeeeff; "
            "border: 1px solid #35355f; border-radius: 5px; "
            "padding: 0 10px; text-align: left;"
        )
        self.embedded_browser_menu = QMenu(self.embedded_browser_url)
        self.embedded_browser_menu.setObjectName("web_menu")
        self.embedded_browser_menu.aboutToShow.connect(
            self.refresh_embedded_site_menu
        )
        self.embedded_browser_url.setMenu(self.embedded_browser_menu)

        toolbar.addWidget(back_btn)
        toolbar.addWidget(forward_btn)
        toolbar.addWidget(reload_btn)
        toolbar.addWidget(self.embedded_browser_url, 1)
        toolbar.addWidget(close_btn)
        self.youtube_host_layout.addLayout(toolbar)

        self.embedded_browser_load_label = QLabel("")
        self.embedded_browser_load_label.setStyleSheet(
            "color: #8888aa; font-size: 11px;"
        )
        self.youtube_host_layout.addWidget(self.embedded_browser_load_label)

        view = QWebEngineView(self.youtube_host)
        view.setStyleSheet("background-color: #111126;")
        self.youtube_host_layout.addWidget(view, 1)
        self.embedded_browser_view = view

        back_btn.clicked.connect(view.back)
        forward_btn.clicked.connect(view.forward)
        reload_btn.clicked.connect(view.reload)
        close_btn.clicked.connect(self.close_embedded_browser)
        view.urlChanged.connect(
            lambda url: self.update_embedded_browser_url(url.toString())
        )
        view.loadStarted.connect(
            lambda: self.embedded_browser_load_label.setText("Loading...")
        )
        view.loadFinished.connect(
            lambda ok: self.embedded_browser_load_label.setText(
                "" if ok else "Page failed to load."
            )
        )
        self.refresh_embedded_site_menu()
        return view

    def load_embedded_browser_presets(self):
        self.embedded_browser_presets = []
        try:
            with open(
                self.embedded_browser_presets_path, "r", encoding="utf-8"
            ) as presets_file:
                data = json.load(presets_file)
        except (OSError, ValueError):
            return

        for item in data.get("presets", []):
            name = item.get("name", "")
            url = item.get("url", "")
            if isinstance(name, str) and isinstance(url, str) and name and url:
                self.embedded_browser_presets.append({"name": name, "url": url})

        existing_urls = {preset["url"] for preset in self.embedded_browser_presets}
        for item in data.get("websites", []):
            name = item.get("label", "") or item.get("name", "")
            url = item.get("url", "")
            if (
                isinstance(name, str)
                and isinstance(url, str)
                and name
                and url
                and url not in existing_urls
            ):
                self.embedded_browser_presets.append({"name": name, "url": url})
                existing_urls.add(url)

    def save_embedded_browser_presets(self):
        os.makedirs(os.path.dirname(self.embedded_browser_presets_path), exist_ok=True)
        temporary_path = f"{self.embedded_browser_presets_path}.tmp"
        data = {
            "websites": [],
            "presets": self.embedded_browser_presets,
        }
        try:
            with open(temporary_path, "w", encoding="utf-8") as presets_file:
                json.dump(data, presets_file, indent=2)
            os.replace(temporary_path, self.embedded_browser_presets_path)
        except OSError:
            pass

    def update_embedded_browser_url(self, url):
        if self.embedded_browser_url is None:
            return
        text = url if url and url != "about:blank" else "Open website"
        self.embedded_browser_url.setText(text)
        self.embedded_browser_url.setToolTip(text)

    def refresh_embedded_site_menu(self):
        if self.embedded_browser_menu is None:
            return
        self.embedded_browser_menu.clear()
        youtube_action = self.embedded_browser_menu.addAction("YouTube")
        youtube_action.triggered.connect(
            lambda _checked=False: self.open_media_browser("youtube")
        )
        myinstants_action = self.embedded_browser_menu.addAction("MyInstants")
        myinstants_action.triggered.connect(
            lambda _checked=False: self.open_media_browser("myinstants")
        )
        tenor_action = self.embedded_browser_menu.addAction("Tenor")
        tenor_action.triggered.connect(
            lambda _checked=False: self.open_media_browser("tenor")
        )
        self.embedded_browser_menu.addSeparator()
        youtube_search_action = self.embedded_browser_menu.addAction(
            "Search YouTube..."
        )
        youtube_search_action.triggered.connect(
            lambda _checked=False: self.open_media_browser("youtube_search")
        )
        myinstants_search_action = self.embedded_browser_menu.addAction(
            "Search MyInstants..."
        )
        myinstants_search_action.triggered.connect(
            lambda _checked=False: self.open_media_browser("myinstants_search")
        )
        tenor_search_action = self.embedded_browser_menu.addAction(
            "Search Tenor GIFs..."
        )
        tenor_search_action.triggered.connect(
            lambda _checked=False: self.open_media_browser("tenor_search")
        )
        giphy_search_action = self.embedded_browser_menu.addAction(
            "Search Giphy GIFs..."
        )
        giphy_search_action.triggered.connect(
            lambda _checked=False: self.open_media_browser("giphy_search")
        )
        self.embedded_browser_menu.addSeparator()
        website_action = self.embedded_browser_menu.addAction("Search Website...")
        website_action.triggered.connect(
            lambda _checked=False: self.open_media_browser("search")
        )
        images_action = self.embedded_browser_menu.addAction("Search Images...")
        images_action.triggered.connect(
            lambda _checked=False: self.open_media_browser("images")
        )

        if self.embedded_browser_presets:
            self.embedded_browser_menu.addSeparator()
        for index, preset in enumerate(self.embedded_browser_presets):
            preset_action = self.embedded_browser_menu.addAction(
                f"Preset: {preset['name']}"
            )
            preset_action.triggered.connect(
                lambda _checked=False, i=index:
                self.open_embedded_browser_url(
                    self.embedded_browser_presets[i]["url"]
                )
            )

        self.embedded_browser_menu.addSeparator()
        save_action = self.embedded_browser_menu.addAction("Save Current as Preset")
        save_action.triggered.connect(self.save_current_embedded_preset)
        remove_action = self.embedded_browser_menu.addAction("Remove Current Preset")
        remove_action.setEnabled(self.current_embedded_preset_index() is not None)
        remove_action.triggered.connect(self.remove_current_embedded_preset)
        remove_saved_action = self.embedded_browser_menu.addAction(
            "Remove Saved Preset..."
        )
        remove_saved_action.setEnabled(bool(self.embedded_browser_presets))
        remove_saved_action.triggered.connect(self.remove_saved_embedded_preset)

    def save_current_embedded_preset(self):
        if self.embedded_browser_view is None:
            return
        url = self.embedded_browser_view.url().toString()
        if not url or url == "about:blank":
            return
        title = self.embedded_browser_view.title().strip()
        default_name = title or urlparse(url).netloc or f"Preset {len(self.embedded_browser_presets) + 1}"
        name, accepted = QInputDialog.getText(
            self,
            "Save Website Preset",
            "Preset name:",
            text=default_name,
        )
        name = name.strip()
        if not accepted or not name:
            return
        self.embedded_browser_presets = [
            preset
            for preset in self.embedded_browser_presets
            if not (preset["name"] == name or preset["url"] == url)
        ]
        self.embedded_browser_presets.append({"name": name, "url": url})
        self.save_embedded_browser_presets()
        self.refresh_embedded_site_menu()

    def current_embedded_preset_index(self):
        if self.embedded_browser_view is None:
            return None
        url = self.embedded_browser_view.url().toString()
        for index, preset in enumerate(self.embedded_browser_presets):
            if preset["url"] == url:
                return index
        return None

    def remove_current_embedded_preset(self):
        preset_index = self.current_embedded_preset_index()
        if preset_index is None:
            return
        self.embedded_browser_presets.pop(preset_index)
        self.save_embedded_browser_presets()
        self.refresh_embedded_site_menu()

    def remove_saved_embedded_preset(self):
        if not self.embedded_browser_presets:
            return
        preset_names = [preset["name"] for preset in self.embedded_browser_presets]
        name, accepted = QInputDialog.getItem(
            self,
            "Remove Website Preset",
            "Preset to remove:",
            preset_names,
            0,
            False,
        )
        if not accepted or not name:
            return
        self.embedded_browser_presets = [
            preset
            for preset in self.embedded_browser_presets
            if preset["name"] != name
        ]
        self.save_embedded_browser_presets()
        self.refresh_embedded_site_menu()

    def close_embedded_browser(self):
        if self.embedded_browser_view is not None:
            self.embedded_browser_view.setUrl(
                QUrl(
                    self.embedded_browser_url_for_tab(
                        self.embedded_last_default_browser_tab
                    )
                )
            )
        self.set_youtube_panel_attached(False)

    def open_embedded_browser_url(self, target_url):
        if not target_url:
            return
        view = self.ensure_embedded_browser()
        if view is None:
            return
        self.set_youtube_panel_attached(True)
        view.setUrl(QUrl(target_url))
        view.setFocus()
        self.update_embedded_browser_url(target_url)
        self.refresh_embedded_site_menu()

    def embedded_browser_url_for_tab(self, tab_name):
        if tab_name == "youtube":
            return YOUTUBE_HOME_URL
        if tab_name == "myinstants":
            return MYINSTANTS_HOME_URL
        if tab_name == "tenor":
            return TENOR_HOME_URL
        if tab_name in (
            "youtube_search", "myinstants_search", "tenor_search",
            "giphy_search",
        ):
            site_key = tab_name.removesuffix("_search")
            return self.default_site_search_url(site_key)
        if tab_name == "images":
            query, accepted = QInputDialog.getText(
                self,
                "Search Images",
                "What images are you looking for?",
            )
            query = query.strip()
            if not accepted or not query:
                return ""
            return f"https://www.google.com/search?tbm=isch&q={quote_plus(query)}"
        if tab_name == "search":
            query, accepted = QInputDialog.getText(
                self,
                "Search Website",
                "Enter a website address or search:",
            )
            query = query.strip()
            if not accepted or not query:
                return ""
            if "://" in query:
                return query
            if "." in query and " " not in query:
                return f"https://{query}"
            return f"https://www.google.com/search?q={quote_plus(query)}"
        return ""

    def default_site_search_url(self, site_key):
        names = {
            "youtube": "YouTube",
            "myinstants": "MyInstants",
            "tenor": "Tenor GIFs",
            "giphy": "Giphy GIFs",
        }
        query, accepted = QInputDialog.getText(
            self,
            f"Search {names.get(site_key, 'Website')}",
            "Search for:",
        )
        query = query.strip()
        if not accepted or not query:
            return ""
        if site_key == "youtube":
            return (
                "https://www.youtube.com/results?search_query="
                f"{quote_plus(query)}"
            )
        if site_key == "myinstants":
            return (
                "https://www.myinstants.com/en/search/?name="
                f"{quote_plus(query)}"
            )
        if site_key == "tenor":
            slug = quote_plus(query).replace("+", "-")
            return f"https://tenor.com/search/{slug}-gifs"
        if site_key == "giphy":
            slug = quote_plus(query).replace("+", "-")
            return f"https://giphy.com/search/{slug}"
        return ""

    def apply_theme_config(self):
        stylesheet = self.styleSheet()
        replacements = {
            "#1a1a2e": THEME["background"],
            "#16213e": THEME["panel"],
            "#6C63FF": THEME["accent"],
            "#7b72ff": THEME["accent_hover"],
            "#eeeeff": THEME["text"],
            "#8888aa": THEME["muted_text"],
            "#1a6b3a": THEME["success"],
        }
        for original, configured in replacements.items():
            stylesheet = stylesheet.replace(original, configured)
        self.setStyleSheet(stylesheet)

    def add_ui_extensions(self, location, layout=None, menu=None):
        for extension in self.ui_extension_registry.at(location):
            callback = extension.callback
            if menu is not None:
                target_menu = menu
                for menu_label in extension.menu_path:
                    child_menu = next(
                        (
                            action.menu()
                            for action in target_menu.actions()
                            if action.menu() is not None
                            and action.text() == menu_label
                        ),
                        None,
                    )
                    target_menu = (
                        child_menu
                        if child_menu is not None
                        else target_menu.addMenu(menu_label)
                    )
                action = target_menu.addAction(extension.label)
                action.setToolTip(extension.tooltip)
                action.triggered.connect(
                    lambda _checked=False, fn=callback: fn(self)
                )
                continue
            if layout is None:
                continue
            button = QPushButton(extension.label)
            if extension.object_name:
                button.setObjectName(extension.object_name)
            if extension.tooltip:
                button.setToolTip(extension.tooltip)
            if extension.width:
                button.setFixedWidth(extension.width)
            button.setFixedHeight(
                extension.height
                or (
                    UI_SIZES["tool_button_height"]
                    if location == "library_tools"
                    else UI_SIZES["primary_button_height"]
                )
            )
            button.clicked.connect(
                lambda _checked=False, fn=callback: fn(self)
            )
            layout.addWidget(button)

    def build_import_provider_menu(self, import_menu):
        group_menus = {}
        for provider in self.import_registry.providers():
            target_menu = import_menu
            if provider.group:
                target_menu = group_menus.get(provider.group)
                if target_menu is None:
                    target_menu = import_menu.addMenu(provider.group)
                    group_menus[provider.group] = target_menu
            action = target_menu.addAction(provider.menu_label)
            action.setCheckable(provider.available)
            action.setEnabled(provider.available)
            action.setToolTip(
                provider.tooltip or provider.unavailable_reason
            )
            if provider.available:
                action.triggered.connect(
                    lambda _checked=False, provider_id=provider.id:
                    self.select_import_target(provider_id)
                )
            self.import_actions[provider.id] = action

    def select_import_target(self, target):
        provider = self.import_registry.get(target)
        if provider is None or not provider.available:
            return
        self.import_target = target
        if target in ("premiere_cep", "premiere_uxp"):
            self.last_premiere_target = target
        for action_target, action in self.import_actions.items():
            action.setChecked(action_target == target)
        self.copy_btn.setText(provider.button_label)
        self.update_import_button_tooltip()
        save_editor_settings({
            "selected_target": self.import_target,
            "last_premiere_target": self.last_premiere_target,
        })

    def update_import_button_tooltip(self):
        if not hasattr(self, "copy_btn"):
            return
        provider = self.import_registry.get(self.import_target)
        if provider is None:
            self.copy_btn.setToolTip("")
            return
        if provider.tooltip:
            self.copy_btn.setToolTip(provider.tooltip)
            return
        if self.project_folder and os.path.exists(self.project_folder):
            folder_name = os.path.basename(self.project_folder)
            self.copy_btn.setToolTip(
                f"Import all PremieDrop files from {folder_name} "
                f"with {provider.menu_label}"
            )
        else:
            self.copy_btn.setToolTip(
                f"{provider.menu_label} selected; set a project folder "
                "before importing"
            )

    def import_to_selected_editor(self):
        provider = self.import_registry.get(self.import_target)
        if provider is None:
            QMessageBox.warning(
                self,
                "Import Provider Missing",
                f"The provider '{self.import_target}' is not installed."
            )
            return
        context = ImportContext(
            app=self,
            sections=self.sections,
            project_folder=self.project_folder,
            app_data_dir=APP_DATA_DIR,
        )
        try:
            provider.execute(context)
        except Exception as exc:
            QMessageBox.warning(
                self,
                f"{provider.menu_label} Import Failed",
                str(exc),
            )

    def find_or_create_davinci_bin(self, media_pool, root_folder, name):
        for folder in root_folder.GetSubFolderList() or []:
            if folder.GetName() == name:
                return folder
        return media_pool.AddSubFolder(root_folder, name)

    def import_to_davinci_resolve(self):
        queued_sections = []
        for section in self.sections:
            paths = [
                os.path.abspath(path)
                for path in section["files"]
                if os.path.isfile(path)
            ]
            if paths:
                queued_sections.append({
                    "name": section["name"],
                    "files": paths,
                })
        if not queued_sections:
            QMessageBox.information(
                self,
                "Nothing to Import",
                "No valid PremieDrop files are available to import."
            )
            return

        default_folder = (
            self.project_folder
            if self.project_folder and os.path.isdir(self.project_folder)
            else os.path.join(
                os.path.expanduser("~"), "Documents", "PremieDrop Exports"
            )
        )
        os.makedirs(default_folder, exist_ok=True)
        default_path = os.path.join(
            default_folder,
            f"PremieDrop Import {datetime.now():%Y-%m-%d %H-%M-%S}.fcpxml",
        )
        export_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save DaVinci Resolve Timeline",
            default_path,
            "Final Cut Pro XML (*.fcpxml)",
        )
        if not export_path:
            return
        if not export_path.lower().endswith(".fcpxml"):
            export_path += ".fcpxml"

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            file_count, _total_frames = write_davinci_fcpxml(
                export_path, queued_sections
            )
        except (OSError, ValueError, ET.ParseError) as exc:
            QMessageBox.warning(
                self,
                "Could Not Create Resolve Timeline",
                f"The FCPXML file could not be created:\n\n{exc}",
            )
            return
        finally:
            QApplication.restoreOverrideCursor()

        QMessageBox.information(
            self,
            "DaVinci Timeline Created",
            f"Created an FCPXML timeline containing {file_count} file"
            f"{'s' if file_count != 1 else ''}.\n\n"
            "In DaVinci Resolve choose:\n"
            "File → Import → Timeline\n\n"
            f"Then select:\n{export_path}\n\n"
            "PremieDrop sections are included as timeline markers."
        )
        if os.name == "nt":
            try:
                subprocess.Popen(
                    ["explorer.exe", f"/select,{export_path}"],
                    creationflags=getattr(
                        subprocess, "CREATE_NO_WINDOW", 0
                    ),
                )
            except OSError:
                pass

    def import_to_davinci_studio(self):
        section_files = []
        missing = 0
        for section in self.sections:
            valid_paths = []
            for path in section["files"]:
                if os.path.isfile(path):
                    valid_paths.append(os.path.abspath(path))
                else:
                    missing += 1
            if valid_paths:
                section_files.append((section["name"], valid_paths))

        if not section_files:
            QMessageBox.information(
                self,
                "Nothing to Import",
                "No valid PremieDrop files are available to import."
            )
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            resolve = connect_to_davinci_resolve()
            if resolve is None:
                raise RuntimeError(
                    "PremieDrop could not connect to DaVinci Resolve. "
                    "Open Resolve, load a project, and enable external "
                    "scripting for local applications in Resolve's "
                    "preferences."
                )
            project_manager = resolve.GetProjectManager()
            project = (
                project_manager.GetCurrentProject()
                if project_manager is not None else None
            )
            if project is None:
                raise RuntimeError(
                    "No DaVinci Resolve project is currently open."
                )
            media_pool = project.GetMediaPool()
            if media_pool is None:
                raise RuntimeError(
                    "The current Resolve project's Media Pool is unavailable."
                )

            root_folder = media_pool.GetRootFolder()
            original_folder = media_pool.GetCurrentFolder()
            imported_count = 0
            failed_sections = []
            try:
                for section_name, paths in section_files:
                    target_folder = self.find_or_create_davinci_bin(
                        media_pool, root_folder, section_name
                    )
                    if target_folder is None:
                        failed_sections.append(section_name)
                        continue
                    if not media_pool.SetCurrentFolder(target_folder):
                        failed_sections.append(section_name)
                        continue
                    imported = media_pool.ImportMedia(paths) or []
                    imported_count += len(imported)
            finally:
                if original_folder is not None:
                    media_pool.SetCurrentFolder(original_folder)

            details = [
                f"{imported_count} media item"
                f"{'s' if imported_count != 1 else ''} imported",
                f"{len(section_files)} PremieDrop bin"
                f"{'s' if len(section_files) != 1 else ''} processed",
            ]
            if missing:
                details.append(f"{missing} missing file{'s' if missing != 1 else ''}")
            if failed_sections:
                details.append(
                    f"{len(failed_sections)} bin"
                    f"{'s' if len(failed_sections) != 1 else ''} failed"
                )
            QMessageBox.information(
                self,
                "DaVinci Import Complete",
                f"{', '.join(details)}.\n\n"
                f"Project: {project.GetName()}"
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "DaVinci Import Failed",
                f"{exc}\n\n"
                "Make sure DaVinci Resolve is running with a project open."
            )
        finally:
            QApplication.restoreOverrideCursor()

    def open_media_browser(self, tab_name):
        default_tab = tab_name.removesuffix("_search")
        if default_tab in ("youtube", "myinstants", "tenor"):
            self.embedded_last_default_browser_tab = default_tab
        if (
            self.youtube_browser_process is not None
            and self.youtube_browser_process.poll() is None
        ):
            self.set_youtube_panel_attached(True)
            self.send_browser_command(tab_name)
            return

        frozen_app = getattr(sys, "frozen", False)
        helper_path = os.path.join(os.path.dirname(__file__), "youtube_browser.py")
        if frozen_app:
            browser_command = [sys.executable, "--premiedrop-browser"]
            browser_cwd = os.path.dirname(sys.executable)
        else:
            if not os.path.isfile(helper_path):
                QMessageBox.warning(
                    self,
                    "Media Browser Missing",
                    f"The browser helper was not found:\n{helper_path}"
                )
                return
            browser_command = [sys.executable, helper_path]
            browser_cwd = os.path.dirname(__file__)

        launch_options = {
            "cwd": browser_cwd,
        }
        if os.name == "nt":
            launch_options["creationflags"] = getattr(
                subprocess, "CREATE_NO_WINDOW", 0
            )

        try:
            if os.path.isfile(YOUTUBE_DOWNLOAD_REQUEST_FILE):
                os.remove(YOUTUBE_DOWNLOAD_REQUEST_FILE)
            if os.path.isfile(YOUTUBE_BROWSER_STATUS_FILE):
                os.remove(YOUTUBE_BROWSER_STATUS_FILE)
            if os.path.isfile(YOUTUBE_BROWSER_COMMAND_FILE):
                os.remove(YOUTUBE_BROWSER_COMMAND_FILE)
            self.set_youtube_panel_attached(True)
            self.publish_youtube_dock_state()
            self.youtube_browser_launch_time = time.time()
            self.youtube_browser_process = subprocess.Popen(
                browser_command + [
                    YOUTUBE_DOWNLOAD_REQUEST_FILE,
                    YOUTUBE_DOCK_STATE_FILE,
                    YOUTUBE_BROWSER_STATUS_FILE,
                    YOUTUBE_BROWSER_LOG_FILE,
                    YOUTUBE_BROWSER_COMMAND_FILE,
                    tab_name,
                    YOUTUBE_HOME_URL,
                    MYINSTANTS_HOME_URL,
                    TENOR_HOME_URL,
                ],
                **launch_options,
            )
        except OSError as exc:
            QMessageBox.warning(
                self,
                "Could Not Open Media Browser",
                f"The isolated browser could not start:\n\n{exc}"
            )

    def send_browser_command(self, tab_name):
        os.makedirs(APP_DATA_DIR, exist_ok=True)
        temporary_path = f"{YOUTUBE_BROWSER_COMMAND_FILE}.tmp"
        command = {
            "tab": tab_name,
            "site_search": (
                tab_name.removesuffix("_search")
                if tab_name.endswith("_search")
                else ""
            ),
            "search_images": tab_name == "images",
            "search_website": tab_name == "search",
            "created_at": datetime.now(timezone.utc).timestamp(),
        }
        try:
            with open(temporary_path, "w", encoding="utf-8") as command_file:
                json.dump(command, command_file)
            os.replace(temporary_path, YOUTUBE_BROWSER_COMMAND_FILE)
        except OSError:
            pass

    def set_youtube_panel_attached(self, attached):
        if (
            self.youtube_panel_attached == attached
            and (
                not attached
                or self.youtube_host.width() >= YOUTUBE_PANEL_MIN_WIDTH
            )
        ):
            self.publish_youtube_dock_state()
            return

        available = QApplication.desktop().availableGeometry(self)
        self.youtube_panel_attached = attached

        if attached:
            self.youtube_panel_width = max(
                YOUTUBE_PANEL_MIN_WIDTH,
                ATTACHED_BROWSER_WINDOW_WIDTH - self.youtube_base_width,
            )
            self.youtube_host.setFixedWidth(self.youtube_panel_width)
            target_width = self.youtube_base_width + self.youtube_panel_width
        else:
            self.youtube_host.setMinimumWidth(0)
            self.youtube_host.setMaximumWidth(0)
            self.youtube_host.setFixedWidth(0)
            self.youtube_panel_width = 0
            target_width = self.youtube_base_width

        self.setMinimumWidth(target_width)
        self.setMaximumWidth(
            target_width if attached else 16777215
        )
        self.resize(target_width, self.height())
        QApplication.processEvents()

        frame = self.frameGeometry()
        target_x = available.x() + max(
            0, (available.width() - frame.width()) // 2
        )
        target_y = min(
            max(frame.y(), available.y()),
            available.y() + available.height() - frame.height()
        )
        self.move(target_x, target_y)
        self.publish_youtube_dock_state()

    def check_youtube_browser(self):
        if (
            self.youtube_browser_process is not None
            and self.youtube_browser_process.poll() is not None
        ):
            self.youtube_browser_process = None
            self.set_youtube_panel_attached(False)

        if self.youtube_browser_process is not None:
            self.check_youtube_browser_status()
            self.publish_youtube_dock_state()

        if not os.path.isfile(YOUTUBE_DOWNLOAD_REQUEST_FILE):
            return

        try:
            with open(
                YOUTUBE_DOWNLOAD_REQUEST_FILE, "r", encoding="utf-8"
            ) as request_file:
                request = json.load(request_file)
            os.remove(YOUTUBE_DOWNLOAD_REQUEST_FILE)
        except (OSError, ValueError):
            return

        url = request.get("url", "")
        if isinstance(url, str) and url:
            cursor_position = None
            try:
                cursor_position = QPoint(
                    int(request["cursor_x"]),
                    int(request["cursor_y"]),
                )
            except (KeyError, TypeError, ValueError):
                pass
            self.open_download_dialog(
                url,
                cursor_position,
                request_type=request.get("request_type", ""),
                suggested_filename=request.get("suggested_filename", ""),
                mime_type=request.get("mime_type", ""),
                referer=request.get("referer", ""),
            )

    def check_youtube_browser_status(self):
        if not os.path.isfile(YOUTUBE_BROWSER_STATUS_FILE):
            return
        try:
            with open(
                YOUTUBE_BROWSER_STATUS_FILE, "r", encoding="utf-8"
            ) as status_file:
                status = json.load(status_file)
            os.remove(YOUTUBE_BROWSER_STATUS_FILE)
        except (OSError, ValueError):
            return
        attached = status.get("attached")
        if isinstance(attached, bool):
            if (
                not attached
                and self.youtube_browser_process is not None
                and time.time() - self.youtube_browser_launch_time < 3
            ):
                self.publish_youtube_dock_state()
                return
            self.set_youtube_panel_attached(attached)

    def publish_youtube_dock_state(self):
        os.makedirs(APP_DATA_DIR, exist_ok=True)
        host_position = self.youtube_host.mapToGlobal(QPoint(0, 0))
        if self.youtube_panel_attached:
            self.youtube_panel_width = max(
                self.youtube_host.width(),
                self.youtube_panel_width,
                YOUTUBE_PANEL_MIN_WIDTH,
            )
        state_width = (
            self.youtube_panel_width
            if self.youtube_panel_attached
            else self.youtube_host.width()
        )
        state = {
            "parent_hwnd": int(self.youtube_host.winId()),
            "x": host_position.x(),
            "y": host_position.y(),
            "width": state_width,
            "height": self.youtube_host.height(),
            "attached": self.youtube_panel_attached,
            "visible": self.isVisible(),
            "minimized": self.isMinimized(),
        }
        temporary_path = f"{YOUTUBE_DOCK_STATE_FILE}.tmp"
        try:
            with open(temporary_path, "w", encoding="utf-8") as state_file:
                json.dump(state, state_file)
            os.replace(temporary_path, YOUTUBE_DOCK_STATE_FILE)
        except OSError:
            pass

    def open_download_dialog(
        self, initial_url="", cursor_position=None, request_type="",
        suggested_filename="", mime_type="", referer=""
    ):
        if not isinstance(initial_url, str):
            initial_url = ""
        if self.download_worker is not None and self.download_worker.isRunning():
            QMessageBox.information(
                self,
                "Download in Progress",
                "Wait for the current download to finish."
            )
            return
        direct_file = (
            request_type == "direct"
            or looks_like_direct_download(
                initial_url, suggested_filename, mime_type
            )
        )
        if not direct_file and yt_dlp is None:
            QMessageBox.information(
                self,
                "yt-dlp Required",
                'Install the downloader first:\n\npython -m pip install "yt-dlp[default]"'
            )
            return

        default_folder = self.last_download_folder
        if not default_folder or not os.path.isdir(default_folder):
            default_folder = self.project_folder
        if not default_folder or not os.path.isdir(default_folder):
            default_folder = os.path.join(
                os.path.expanduser("~"),
                "Downloads",
                "PremieDrop"
            )

        dialog = DownloadDialog(
            self.sections,
            default_folder,
            self,
            initial_url=initial_url,
            direct_file=direct_file,
            suggested_filename=suggested_filename,
            mime_type=mime_type,
            referer=referer,
        )
        dialog.adjustSize()
        if not isinstance(cursor_position, QPoint):
            cursor_position = QCursor.pos()
        available = QApplication.desktop().availableGeometry(cursor_position)
        dialog_x = min(
            max(cursor_position.x(), available.x()),
            available.x() + available.width() - dialog.width()
        )
        dialog_y = min(
            max(cursor_position.y(), available.y()),
            available.y() + available.height() - dialog.height()
        )
        dialog.move(dialog_x, dialog_y)
        dialog.url_input.setFocus()
        dialog.url_input.setCursorPosition(len(initial_url))
        if dialog.exec_() != QDialog.Accepted:
            return
        settings = dialog.settings()
        self.last_download_folder = settings["folder"]
        self.save_library()

        self.download_progress.setValue(0)
        self.download_status.setText("Starting download...")
        self.download_progress_row.show()

        worker_class = (
            DirectFileDownloadWorker
            if settings["download_type"] == "direct"
            else DownloadWorker
        )
        self.download_worker = worker_class(settings, self)
        self.download_worker.progress.connect(self.update_download_progress)
        self.download_worker.completed.connect(self.download_completed)
        self.download_worker.failed.connect(self.download_failed)
        self.download_worker.finished.connect(self.download_thread_finished)
        self.download_worker.start()

    def update_download_progress(self, percent, detail):
        self.download_progress.setValue(percent)
        self.download_status.setText(detail)

    def download_completed(self, path, section_name):
        self.add_files([path], section_name)
        self.download_progress.setValue(100)
        self.download_status.setText(f"Added {os.path.basename(path)}")
        QTimer.singleShot(4000, self.download_progress_row.hide)

    def download_failed(self, message):
        self.download_progress_row.hide()
        QMessageBox.warning(self, "Download Failed", message)

    def download_thread_finished(self):
        worker = self.download_worker
        self.download_worker = None
        if worker is not None:
            worker.deleteLater()

    def install_update(self):
        if (
            not self.closing_for_update_installer
            and self.update_worker is not None
            and self.update_worker.isRunning()
        ):
            QMessageBox.information(
                self,
                "Update in Progress",
                "PremieDrop is already downloading the latest installer.",
            )
            return
        if self.download_worker is not None and self.download_worker.isRunning():
            QMessageBox.information(
                self,
                "Download in Progress",
                "Wait for the current media download to finish first.",
            )
            return
        start = QMessageBox.question(
            self,
            "Install Update",
            "Download and run the latest PremieDrop installer now?\n\n"
            "PremieDrop will close after the installer opens.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if start != QMessageBox.Yes:
            return

        self.update_btn.setEnabled(False)
        self.download_progress.setValue(0)
        self.download_status.setText("Checking latest release...")
        self.download_progress_row.show()

        self.update_worker = UpdateInstallerWorker(self)
        self.update_worker.progress.connect(self.update_install_progress)
        self.update_worker.completed.connect(self.update_installer_ready)
        self.update_worker.failed.connect(self.update_install_failed)
        self.update_worker.finished.connect(self.update_install_finished)
        self.update_worker.start()

    def update_install_progress(self, percent, detail):
        self.download_progress.setValue(percent)
        self.download_status.setText(detail)

    def update_installer_ready(self, installer_path, release_tag):
        self.download_progress.setValue(100)
        self.download_status.setText(f"Opening {release_tag} installer...")
        try:
            subprocess.Popen(
                [installer_path],
                cwd=os.path.dirname(installer_path),
            )
        except OSError as exc:
            self.update_install_failed(str(exc))
            return
        self.closing_for_update_installer = True
        QTimer.singleShot(500, self.close)

    def update_install_failed(self, message):
        self.update_btn.setEnabled(True)
        self.download_status.setText("Update failed.")
        QTimer.singleShot(4000, self.download_progress_row.hide)
        QMessageBox.warning(self, "Update Failed", message)

    def update_install_finished(self):
        worker = self.update_worker
        self.update_worker = None
        self.update_btn.setEnabled(True)
        if worker is not None:
            worker.deleteLater()

    def preview_item(self, item):
        path = item.data(Qt.UserRole)
        file_type = get_file_type(path) if path else None
        if file_type not in ("video", "audio", "image"):
            return
        if file_type == "video":
            requested_path = os.path.normcase(os.path.abspath(path))
            for video_window in list(self.video_windows):
                current_path = getattr(video_window, "current_path", "")
                if (
                    current_path
                    and os.path.normcase(os.path.abspath(current_path))
                    == requested_path
                ):
                    if video_window.isMinimized():
                        video_window.showNormal()
                    else:
                        video_window.show()
                    video_window.raise_()
                    video_window.activateWindow()
                    return

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
            video_preview = self.ensure_video_preview()
            loaded = video_preview.load_audio(path)
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
            minimum_width = self.required_window_width()
            self.setMinimumWidth(minimum_width)
            self.setMaximumHeight(16777215)
            self.setMinimumHeight(BASE_WINDOW_HEIGHT)
            base_size = self.embedded_previous_size or self.size()
            target_width = max(minimum_width, base_size.width())
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
        minimum_width = self.required_window_width()
        self.setMinimumSize(minimum_width, BASE_WINDOW_HEIGHT)
        if previous_size is not None:
            self.resize(
                max(minimum_width, previous_size.width()),
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
        minimum_width = self.required_window_width()
        self.setMinimumSize(minimum_width, BASE_WINDOW_HEIGHT)
        if previous_size is not None:
            restored_width = max(minimum_width, previous_size.width())
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
        self.setMinimumWidth(self.required_window_width())
        self.setMinimumHeight(BASE_WINDOW_HEIGHT)
        self.resize(max(self.required_window_width(), width), height)
        if self.video_preview is not None and not self.video_preview.isHidden():
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

    def next_preset_name(self, presets):
        number = 1
        existing = {name.casefold() for name in presets}
        while f"preset {number}" in existing:
            number += 1
        return f"Preset {number}"

    def save_library_preset(self):
        presets = load_presets()
        default_name = self.next_preset_name(presets)
        name, accepted = QInputDialog.getText(
            self,
            "Save Preset",
            "Preset name:",
            text=default_name,
        )
        name = name.strip()
        if not accepted or not name:
            return

        existing_name = next(
            (
                preset_name for preset_name in presets
                if preset_name.casefold() == name.casefold()
            ),
            None,
        )
        if existing_name is not None:
            replace = QMessageBox.question(
                self,
                "Replace Preset",
                f'A preset named "{existing_name}" already exists. Replace it?',
                QMessageBox.Yes | QMessageBox.No,
            )
            if replace != QMessageBox.Yes:
                return
            if existing_name != name:
                presets.pop(existing_name, None)

        presets[name] = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sections": [
                {
                    "name": section["name"],
                    "files": list(section["files"]),
                }
                for section in self.sections
            ],
        }
        try:
            save_presets(presets)
        except OSError as exc:
            QMessageBox.warning(self, "Preset Not Saved", str(exc))
            return
        QMessageBox.information(
            self,
            "Preset Saved",
            f'"{name}" saved with {len(self.all_files())} files.',
        )

    def load_library_preset(self):
        presets = load_presets()
        if not presets:
            QMessageBox.information(
                self,
                "No Presets",
                "No saved presets are available yet.",
            )
            return

        names = list(presets)
        name, accepted = QInputDialog.getItem(
            self,
            "Load Preset",
            "Choose a preset:",
            names,
            0,
            False,
        )
        if not accepted or not name:
            return

        preset_sections = presets.get(name, {}).get("sections", [])
        if not isinstance(preset_sections, list):
            QMessageBox.warning(
                self, "Preset Invalid", "This preset could not be loaded."
            )
            return

        missing = 0
        restored_sections = []
        for section in preset_sections:
            if not isinstance(section, dict):
                continue
            files = []
            for path in section.get("files", []):
                normalized = os.path.normpath(path)
                if os.path.exists(normalized):
                    files.append(normalized)
                else:
                    missing += 1
            restored_sections.append({
                "name": str(section.get("name", "")).strip(),
                "files": files,
            })

        self.image_preview.hide_for_switch()
        if self.video_preview is not None:
            self.video_preview.close_preview()
        for window in list(self.video_windows):
            window.close_preview()

        self.sections = normalize_sections(restored_sections)
        self.update_window_minimum_size(expand=True)
        self.save_library()
        self.populate_list()

    def write_extension_diagnostics(self):
        errors = (
            self.import_registry.load_errors
            + self.ui_extension_registry.load_errors
        )
        diagnostics_path = os.path.join(
            APP_DATA_DIR, "extension_errors.log"
        )
        if not errors:
            try:
                os.remove(diagnostics_path)
            except OSError:
                pass
            return
        try:
            os.makedirs(APP_DATA_DIR, exist_ok=True)
            with open(
                diagnostics_path, "w", encoding="utf-8"
            ) as diagnostics_file:
                for path, details in errors:
                    diagnostics_file.write(f"Extension: {path}\n")
                    diagnostics_file.write(details)
                    diagnostics_file.write("\n\n")
        except OSError:
            pass
        message = f'"{name}" loaded with {len(self.all_files())} files.'
        if missing:
            message += (
                f"\n\n{missing} missing file"
                f"{'s were' if missing != 1 else ' was'} skipped."
            )
        QMessageBox.information(self, "Preset Loaded", message)

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
        folder_active = bool(
            self.project_folder and os.path.exists(self.project_folder)
        )
        if folder_active:
            name = os.path.basename(self.project_folder)
            self.folder_label.setText(f"→  {name}")
            self.folder_label.setToolTip(self.project_folder)
            self.copy_btn.setEnabled(True)
        else:
            self.folder_label.setText("No project folder set")
            self.folder_label.setToolTip("")
            self.copy_btn.setEnabled(True)
        self.folder_label.set_active(folder_active)
        self.update_import_button_tooltip()
        self.auto_organize_btn.setEnabled(folder_active)
        self.reload_assets_btn.setEnabled(folder_active)

    def show_project_folder_contents(self):
        if not self.project_folder or not os.path.isdir(self.project_folder):
            return
        dialog = FolderContentsDialog(self.project_folder, self)
        dialog.exec_()

    def preset_section_folders(self):
        return {
            name: os.path.join(self.project_folder, safe_folder_name(name))
            for name in DEFAULT_SECTIONS
        }

    def unique_destination(self, folder, filename):
        base, extension = os.path.splitext(filename)
        destination = os.path.join(folder, filename)
        number = 2
        while os.path.exists(destination):
            destination = os.path.join(
                folder, f"{base} ({number}){extension}"
            )
            number += 1
        return destination

    def auto_organize_assets(self):
        if not self.project_folder or not os.path.isdir(self.project_folder):
            QMessageBox.warning(
                self, "No Folder Set", "Please set a project folder first."
            )
            return

        preset_folders = self.preset_section_folders()
        for folder in preset_folders.values():
            os.makedirs(folder, exist_ok=True)

        moved = 0
        failed = 0
        replacements = {}
        try:
            root_entries = list(os.scandir(self.project_folder))
        except OSError as exc:
            QMessageBox.warning(self, "Auto Organize Failed", str(exc))
            return

        for entry in root_entries:
            if not entry.is_file():
                continue
            source = os.path.normpath(entry.path)
            if os.path.splitext(source)[1].lower() not in ALL_EXTENSIONS:
                continue
            section_name = section_for_file(source)
            destination_folder = preset_folders.get(section_name)
            if destination_folder is None:
                continue
            destination = self.unique_destination(
                destination_folder, entry.name
            )
            try:
                shutil.move(source, destination)
                replacements[
                    os.path.normcase(os.path.abspath(source))
                ] = os.path.normpath(destination)
                moved += 1
            except OSError:
                failed += 1

        if replacements:
            for section in self.sections:
                section["files"] = [
                    replacements.get(
                        os.path.normcase(os.path.abspath(path)), path
                    )
                    for path in section["files"]
                ]

        added = self.reload_assets(show_message=False)
        QMessageBox.information(
            self,
            "Auto Organize Complete",
            f"{moved} file{'s' if moved != 1 else ''} organized, "
            f"{added} asset{'s' if added != 1 else ''} reloaded"
            + (f", {failed} failed." if failed else ".")
        )

    def reload_assets(self, show_message=True):
        if not self.project_folder or not os.path.isdir(self.project_folder):
            if show_message:
                QMessageBox.warning(
                    self, "No Folder Set", "Please set a project folder first."
                )
            return 0

        preset_folders = self.preset_section_folders()
        managed_roots = {
            os.path.normcase(os.path.abspath(folder))
            for folder in preset_folders.values()
        }
        discovered_by_section = {}
        for section_name, folder in preset_folders.items():
            os.makedirs(folder, exist_ok=True)
            discovered = []
            for root, _directories, filenames in os.walk(folder):
                for filename in filenames:
                    path = os.path.normpath(os.path.join(root, filename))
                    if os.path.splitext(path)[1].lower() in ALL_EXTENSIONS:
                        discovered.append(path)
            discovered_by_section[section_name] = discovered

        before = {
            os.path.normcase(os.path.abspath(path))
            for path in self.all_files()
        }
        for section in self.sections:
            discovered = discovered_by_section.get(section["name"])
            if discovered is None:
                continue
            external_files = []
            for path in section["files"]:
                absolute = os.path.normcase(os.path.abspath(path))
                inside_managed = any(
                    absolute == root or absolute.startswith(root + os.sep)
                    for root in managed_roots
                )
                if not inside_managed and os.path.exists(path):
                    external_files.append(path)
            section["files"] = external_files + [
                path for path in discovered if path not in external_files
            ]

        after = {
            os.path.normcase(os.path.abspath(path))
            for path in self.all_files()
        }
        added = len(after - before)
        self.save_library()
        self.populate_list()
        if show_message:
            QMessageBox.information(
                self,
                "Assets Reloaded",
                f"{added} new asset{'s' if added != 1 else ''} loaded from "
                "the preset folders."
            )
        return added

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
        visible_total = 0
        changed = False
        search_text = ""
        if hasattr(self, "search_input"):
            search_text = self.search_input.text().strip().casefold()
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
            visible_files = valid_files
            if search_text:
                section_name = section["name"].casefold()
                visible_files = [
                    path for path in valid_files
                    if search_text in section_name
                    or search_text in os.path.basename(path).casefold()
                    or search_text in os.path.basename(os.path.dirname(path)).casefold()
                    or search_text in path.casefold()
                ]

            if index:
                separator = QListWidgetItem()
                separator.setFlags(Qt.NoItemFlags)
                separator.setBackground(QColor("#2a2a4a"))
                separator.setSizeHint(QSize(0, separator_height))
                self.file_list.addItem(separator)

            total += len(valid_files)
            visible_total += len(visible_files)
            section_item = QListWidgetItem()
            section_item.setData(Qt.UserRole, None)
            section_item.setData(Qt.UserRole + 1, section["name"])
            section_item.setFlags(Qt.NoItemFlags)
            section_item.setSizeHint(QSize(0, section_height))
            self.file_list.addItem(section_item)
            section_box = SectionDropBox(
                self,
                section["name"],
                visible_files,
                section_height,
                total_count=len(valid_files)
            )
            self.file_list.setItemWidget(section_item, section_box)

        self.saved_files = self.all_files()
        if changed:
            self.save_library()

        if search_text:
            self.count_label.setText(
                f"{visible_total} of {total} file{'s' if total != 1 else ''}"
            )
        else:
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

    def clear_section(self, section_name):
        section = self.find_section(section_name)
        if section is None or not section["files"]:
            return

        files = list(section["files"])
        reply = QMessageBox.question(
            self,
            "Clear Section",
            f'Remove all {len(files)} file{"s" if len(files) != 1 else ""} '
            f'from "{section_name}"?\n\n'
            "Your actual files will not be deleted.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        paths = set(files)
        if (
            self.video_preview is not None
            and self.video_preview.current_path in paths
        ):
            self.video_preview.close_preview()
        if self.image_preview.current_path in paths:
            self.image_preview.close_preview()
        for window in list(self.video_windows):
            if window.current_path in paths:
                window.close_preview()

        section["files"] = []
        self.save_library()
        self.populate_list()

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
        if (
            self.video_preview is not None
            and self.video_preview.current_path == path
        ):
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
        if self.download_worker is not None and self.download_worker.isRunning():
            QMessageBox.information(
                self,
                "Download in Progress",
                "Wait for the current download to finish before closing PremieDrop."
            )
            event.ignore()
            return
        if self.update_worker is not None and self.update_worker.isRunning():
            QMessageBox.information(
                self,
                "Update in Progress",
                "Wait for the update installer to finish downloading before closing PremieDrop."
            )
            event.ignore()
            return
        if (
            self.youtube_browser_process is not None
            and self.youtube_browser_process.poll() is None
        ):
            self.youtube_browser_process.terminate()
        self.set_youtube_panel_attached(False)
        for window in list(self.video_windows):
            window.close_preview()
        self.image_preview.hide_for_switch()
        if self.video_preview is not None:
            self.video_preview.release()
        super().closeEvent(event)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--premiedrop-browser":
        import youtube_browser
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        return youtube_browser.main()

    clear_browser_storage_on_startup()
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setApplicationName("PremieDrop")
    if os.path.exists(APP_ICON_FILE):
        app.setWindowIcon(QIcon(APP_ICON_FILE))
    app.setStyle("Fusion")
    window = MainWindow()
    if os.path.exists(APP_ICON_FILE):
        window.setWindowIcon(QIcon(APP_ICON_FILE))
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

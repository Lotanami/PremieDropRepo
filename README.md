# PremieDrop

PremieDrop is a desktop media library and workflow companion for video
editors. It keeps reusable videos, sound effects, images, and GIFs organized
in one persistent window, provides built-in previews and web tools, and helps
move complete asset collections into editing software.

PremieDrop is currently developed and tested primarily on Windows, with
Premiere Pro CEP as its working automatic editor integration.

## Features

### Media library

- Persistent library that remembers files, sections, and project folders.
- Add files through the file picker or by dragging them into PremieDrop.
- Drag selected assets back out into compatible editing applications.
- Search files by filename, source folder, or section.
- Live file count and window-size display.
- Support for custom sections that can be added, renamed, reordered, or
  removed.
- Move individual assets between sections through the context menu.
- Reveal source files in File Explorer.
- Clear individual sections or the complete library.

### Automatic organization

- Default sections for:
  - Large video files over 1 GB.
  - Short video files under 1 GB.
  - Sound effects and audio.
  - Images and GIFs.
- Automatically classify loose media into the appropriate folders.
- Reload assets already present in managed project folders.
- Keep external files in the library without unnecessarily moving them.
- Select a project folder and create section-specific media directories.

### Presets

- Save the current section and file arrangement as a named library preset.
- Load saved library presets later.
- Automatically generate names such as `Preset 1` when no custom name is
  entered.
- Save and load website presets from the browser search menu.
- Preserve the last selected editor import target between sessions.

### Media previews

- Cached FFmpeg thumbnails for video files.
- VLC-powered video and audio playback.
- Play, pause, seek, volume, fullscreen, and close controls.
- Video preview sizing based on the source dimensions without forcing 4K
  media to occupy the entire screen.
- Scaled image previews.
- Fully animated GIF previews instead of a static first frame.
- Compact embedded audio preview inside the main window.

### Web workspace

- Persistent web panel attached directly to the PremieDrop window.
- Pop the browser out into a separate window and attach it again.
- Hide and reopen the web panel without reloading persistent pages.
- Built-in destinations for:
  - YouTube.
  - MyInstants.
  - Image search.
  - General website search.
- Back, forward, reload, and home controls.
- Saved website and image-search entries.
- Right-click saved website or image-search entries to delete them.
- Save the current website as a preset.
- Load or delete saved website presets.
- Image-search pages remain at 80% zoom.
- Visible hover highlighting across browser buttons and dropdown menus.

### Downloads

- Download supported media from a URL.
- Send the current YouTube URL directly to PremieDrop's downloader.
- Right-click supported browser media and choose **Copy URL to PremieDrop**.
- Right-click images and choose **Save Image**.
- Choose the destination section before downloading.
- Direct-file downloads with progress reporting.
- YouTube video and audio downloading through `yt-dlp`.
- FFmpeg-powered format conversion and audio extraction.

Only download media that you own or have permission to use.

### Editor integration

- Automatic Premiere Pro import through the included CEP bridge.
- Copy assets into matching project folders and Premiere bins.
- Persistent editor selector with grouped import targets.
- Provider-based integration architecture for adding new editors or replacing
  unfinished integrations without rewriting the main menu.
- Stable import-provider IDs so user selections continue working across
  updates.
- Extension diagnostics written to
  `%APPDATA%\PremieDrop\extension_errors.log`.

### Customization and development

- Central configuration for common UI labels, dimensions, spacing, and theme
  colors.
- Discoverable import-provider modules.
- UI plugin insertion points for:
  - Library tools.
  - The Web dropdown.
  - Primary action buttons.
- External providers can replace built-in placeholders by registering the
  same provider ID.

## Compatibility roadmap

- [ ] Premiere Pro UXP integration
- [ ] Final Cut Pro compatibility
- [ ] DaVinci Resolve 21 (Free) compatibility
- [ ] macOS compatibility

## Requirements

- Windows 10 or Windows 11.
- Python 3.10 or newer.
- VLC Media Player for video and audio previews.
- FFmpeg, supplied automatically through `imageio-ffmpeg` when available.
- Adobe Premiere Pro for CEP integration.

Install the Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run PremieDrop:

```powershell
python main.py
```

## Premiere Pro CEP integration

Install the included CEP bridge:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\cep-extension\install.ps1
```

Restart Premiere Pro, then open the **PremieDrop Bridge** extension. Select
**Premiere Pro (CEP)** from PremieDrop's import dropdown to send the current
library into matching Premiere bins.

Dragging selected files into Premiere's Project panel remains available as a
manual alternative.

## Supported media

| Type | Extensions |
|---|---|
| Video | `.mp4` `.mov` `.avi` `.mkv` `.wmv` `.flv` `.webm` `.m4v` |
| Audio | `.mp3` `.wav` `.aac` `.flac` `.ogg` `.m4a` `.aiff` |
| Image | `.png` `.jpg` `.jpeg` `.gif` `.bmp` `.tiff` `.webp` |

## Project structure

| Path | Purpose |
|---|---|
| `main.py` | Main PremieDrop desktop application |
| `youtube_browser.py` | Isolated persistent web workspace |
| `cep-extension/` | Premiere Pro CEP bridge |
| `import_providers/` | Discoverable editor integration providers |
| `premiedrop_ext/` | Public import and UI extension APIs |
| `ui_plugins/` | Optional UI additions |
| `EXTENDING_PREMIEDROP.md` | Contributor extension guide |

## License

PremieDrop is released under the MIT License.

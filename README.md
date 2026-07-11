# PremieDrop

PremieDrop is a Windows desktop media library and editor workflow companion for video creators. It helps collect clips, sounds, images, and web-downloaded media into organized sections, preview them quickly, and send them into editing software with less folder-hunting.

## Install

Download the latest stable installer from GitHub Releases:

https://github.com/Lotanami/PremieDropRepo/releases/latest

The bundled installer includes the PremieDrop desktop app, Python runtime, app packages, ffmpeg support through imageio-ffmpeg, and the Premiere Pro CEP extension payload. VLC Media Player is still required separately for video preview playback.

## Main Capabilities

- Organize local media into named sections such as large video files, small video files, photos, sound effects, and audio.
- Add files manually or rescan a selected project folder into section folders.
- Save and load library presets for repeat project structures.
- Auto-organize loose media in a project folder into preset section folders.
- Search across files, folders, and sections.
- Drag selected files directly from PremieDrop into supported editors.
- Reveal files in File Explorer, remove individual items, clear sections, and rename or remove custom sections.
- Remember the selected project folder between sessions.
- Check for and run the latest installer from inside the app with the Install Update button.

## Preview Tools

- Image preview with aspect-ratio-preserving display.
- Audio preview in a compact embedded player.
- Standalone video preview windows powered by VLC.
- Play, pause, restart, fullscreen, volume, +/-5 second skip, direct timeline click seeking, and drag seeking.
- Center play/pause/restart overlays similar to a regular video player.
- Live timestamp feedback while dragging the video timeline.
- Duplicate prevention so opening the same video twice brings the existing preview forward instead of creating another copy.

## Web And Downloads

- Embedded/persistent media browser with quick entries for YouTube, MyInstants, website search, and image search.
- Browser URL dropdown for opening presets and switching search targets.
- Save and remove browser presets.
- Download media from direct URLs and browser-selected URLs.
- Remember the last accepted download folder.
- Clear browser cache on startup while preserving saved browser presets.

## Editor Integrations

### Premiere Pro

- Bundled CEP extension: PremieDrop Bridge V0.
- Installer option for installing the Premiere Pro CEP extension.
- CEP bridge imports queued PremieDrop files into Premiere bins that match PremieDrop section names.
- Files already present in the Premiere project are skipped during automatic imports.
- CEP debug mode is enabled by the extension installer for supported CSXS versions.

### DaVinci Resolve

- DaVinci Resolve Studio import path is wired through Resolve's scripting API.
- Free Resolve automatic importing is marked unavailable because scripting support is limited.

### Future Providers

- Premiere Pro UXP is shown as a disabled installer/app option until the UXP package exists.
- Final Cut Pro is represented as an extension point but is not implemented yet.
- New import providers can be added under the release-source import provider system.

## Repository Layout

| Path | Purpose |
|---|---|
| main.py | Main PremieDrop desktop app in the legacy/default source layout. |
| youtube_browser.py | Isolated browser helper used by the app. |
| cep-extension/ | Premiere Pro CEP bridge package. |
| requirements.txt | Python runtime dependencies for source runs. |
| installer-branch | Current bundled installer/source layout used for packaged releases. |

## Build From Source

Install Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run PremieDrop from source:

```powershell
python main.py
```

For bundled Windows installer builds, use the current release packaging on installer-branch.

## Notes For Contributors

- Keep large generated executables out of normal source commits; publish them as GitHub Release assets.
- Import integrations should use the import provider system instead of hardcoding editor-specific behavior into the main window.
- Optional UI additions should use the UI extension registry where possible.
- Only download media you have permission to use.
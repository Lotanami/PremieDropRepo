# PremieDrop

PremieDrop is a lightweight PyQt5 media asset manager for Adobe Premiere Pro.
Store frequently used video, audio, and image files, preview them, organize them
into sections, drag them into an NLE, or import the whole library into Premiere
Pro 2022 through the included CEP extension.

## Features

- Persistent media library with drag-and-drop input and output
- Automatic video, audio, image, and file-size sections
- Custom sections with rename, move, and remove controls
- Cached FFmpeg video thumbnails
- VLC video and audio previews
- Scaled image previews
- Project media-folder organization
- One-click import into matching Premiere bins
- Duplicate-safe automatic CEP imports
- Windows CEP installer for Premiere Pro 2022

## Requirements

- Windows 10/11
- Python 3.8+
- Adobe Premiere Pro 2022 for CEP integration
- VLC Media Player for media previews

Install Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run PremieDrop:

```powershell
python main.py
```

## Premiere Pro 2022 Integration

Install the CEP bridge:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\cep-extension\install.ps1
```

Then:

1. Restart Premiere Pro.
2. Open `Window > Extensions > PremieDrop Bridge` or `Extensions (Legacy)`.
3. Keep the bridge panel open.
4. In PremieDrop, choose a media folder with `Set Folder`.
5. Click `Import All to Premiere`.

PremieDrop copies only missing files into reusable section folders. The bridge
creates matching Premiere bins and imports the queued files automatically.

The handoff uses the current user's application-data directory:

```text
%APPDATA%\PremieDrop\premiedrop_import_queue.json
```

No personal or hard-coded user paths are required.

## Supported Media

| Type | Extensions |
|---|---|
| Video | `.mp4` `.mov` `.avi` `.mkv` `.wmv` `.flv` `.webm` `.m4v` |
| Audio | `.mp3` `.wav` `.aac` `.flac` `.ogg` `.m4a` `.aiff` |
| Image | `.png` `.jpg` `.jpeg` `.gif` `.bmp` `.tiff` |

## Notes

- Dragging into Premiere's Project panel remains supported.
- Direct external drops onto the Premiere timeline are unreliable.
- The bundled CEP manifest targets Premiere Pro 2022 (`22.x`).
- Newer Premiere releases should eventually use a UXP companion.

## Contributing

Issues and pull requests are welcome.

## License

MIT

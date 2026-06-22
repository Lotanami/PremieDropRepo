# PremieDrop

PremieDrop is a lightweight PyQt5 media asset manager for Adobe Premiere Pro.
Store frequently used video, audio, and image files, preview them, organize them
into sections, drag them into an NLE, or import the whole library into Premiere
Pro through the included CEP extension.

## Features

- Persistent media library with drag-and-drop input and output
- Automatic video, audio, image, and file-size sections
- Custom sections with rename, move, and remove controls
- Cached FFmpeg video thumbnails
- VLC video and audio previews
- Animated GIF and scaled image previews
- Persistent embedded web workspace
- URL and direct-file downloads
- Project-folder organization and asset reloading
- Named library presets
- One-click import into matching Premiere bins

## Requirements

- Windows 10/11
- Python 3.10+
- Adobe Premiere Pro for CEP integration
- VLC Media Player for media previews

Install Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run PremieDrop:

```powershell
python main.py
```

Only download media you have permission to use.

## Premiere Pro Integration

Install the CEP bridge:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\cep-extension\install.ps1
```

Then restart Premiere Pro and open the PremieDrop Bridge extension.

## Supported Media

| Type | Extensions |
|---|---|
| Video | `.mp4` `.mov` `.avi` `.mkv` `.wmv` `.flv` `.webm` `.m4v` |
| Audio | `.mp3` `.wav` `.aac` `.flac` `.ogg` `.m4a` `.aiff` |
| Image | `.png` `.jpg` `.jpeg` `.gif` `.bmp` `.tiff` `.webp` |

## Notes

- Dragging into Premiere's Project panel remains supported.
- Direct external drops onto the Premiere timeline are unreliable.

## License

MIT

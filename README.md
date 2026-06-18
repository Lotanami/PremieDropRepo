# 🎬 PremieDrop

A lightweight media asset manager that lets you save your favourite clips and audio files, then drag them straight into Adobe Premiere Pro (or any other NLE).

Built for lazy people, by a lazy person.

---

## What it does

- Save MP4s, MP3s, and other media files to a persistent list
- See file name, folder, and size at a glance
- **Drag files directly from the app into Premiere Pro's project panel**
- Drop files onto the app window to add them to your list
- Right-click to reveal a file in Explorer / Finder, or remove it from the list
- Your list saves automatically between sessions

---

## Supported file types

| Type | Extensions |
|---|---|
| Video | `.mp4` `.mov` `.avi` `.mkv` `.wmv` `.flv` `.webm` `.m4v` |
| Audio | `.mp3` `.wav` `.aac` `.flac` `.ogg` `.m4a` `.aiff` |
| Image | `.png` `.jpg` `.jpeg` `.gif` `.bmp` `.tiff` |

---

## Installation

### Requirements
- Python 3.8+
- PyQt5

### Install dependencies

```bash
pip install PyQt5
```

### Run

```bash
python main.py
```

---

## How to use

1. **Add files** — click `+ Add Files` or drag and drop files onto the window
2. **Select a file** in the list
3. **Drag it** into Premiere Pro's Project panel

> ⚠️ Dropping directly onto the **timeline** is a known limitation — Premiere doesn't always accept external drops onto the timeline itself. Dragging to the **Project panel** works reliably.

---

## Roadmap / Ideas for contributors

This is intentionally kept simple. Here's what could be added:

- [ ] Thumbnail previews for video files (using `ffmpeg`)
- [ ] Search / filter bar
- [✅ ] Tags or categories for organising files
- [ ] CEP panel companion for direct timeline placement in Premiere
- [ ] Support for folder watching
- [ ] System tray mode (run minimised in the background)
- [ ] After Effects / DaVinci Resolve / Final Cut support
- [✅ ] Collections / multiple lists

---

## Contributing

Pull requests welcome. This project exists because I wanted something simple and didn't find it. If you improve it, share it back.

1. Fork the repo
2. Make your changes
3. Open a PR with a description of what you changed and why

---

## License

MIT — do whatever you want with it.

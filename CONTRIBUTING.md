# Contributing to PremieDrop

Thanks for wanting to help with PremieDrop. The app is in beta, and help is
welcome with UI/UX cleanup, PyQt polish, bug fixing, refactoring, packaging,
and editor integrations.

## Good Places To Start

- Look through issues labeled `good first issue` for smaller starter tasks.
- Look through issues labeled `help wanted` for areas where outside help is
  especially useful.
- If you want to work on editor support, check labels like `area: integration`,
  `editor: premiere`, `editor: davinci`, and `editor: final-cut-pro`.
- If you want to work on UI, check labels like `area: ui`, `area: ux`,
  `area: pyqt`, and `area: browser`.

## Project Layout

- `systems/main.py` is the main desktop app. It currently holds a lot of logic
  and is one of the main areas that needs refactoring.
- `systems/youtube_browser.py` is the separate media browser helper used for
  YouTube, MyInstants, Tenor, Giphy search, website search, image search, and
  browser downloads.
- `systems/PremieDropInstaller.py` is the Windows installer UI and install
  logic.
- `cep-extension/` contains the Premiere Pro CEP bridge.
- `systems/import_providers/` contains built-in editor import provider
  definitions and placeholders.
- `systems/premiedrop_ext/` contains extension points for imports, UI hooks,
  shared UI text, sizing, and theme values.

## Running Locally

PremieDrop is currently developed on Windows.

```powershell
cd systems
python -m pip install -r requirements.txt
python main.py
```

If your system uses the Python launcher, this may work instead:

```powershell
cd systems
py -3 -m pip install -r requirements.txt
py -3 main.py
```

Video preview uses VLC, so install VLC Media Player separately if video preview
does not work.

## Building

Build the app executable:

```powershell
cd systems
.\build-windows.ps1
```

Build the bundled installer:

```powershell
cd systems
.\build-installer.ps1
```

Run `build-windows.ps1` before `build-installer.ps1` so the installer bundles
the current `premiedrop.exe`.

## Pull Requests

- Open an issue first for larger changes so the direction is clear.
- Keep PRs focused on one feature, bug, or cleanup area.
- Do not commit generated `.exe` files or build output.
- Mention which issue your PR addresses, if there is one.
- Include screenshots or short screen recordings for UI changes when possible.
- For bug fixes, include the steps you used to reproduce and test the fix.

## Style Notes

- Prefer small, readable changes over big rewrites.
- Keep user-facing behavior stable unless the issue is specifically about
  changing the workflow.
- Use existing extension points where possible instead of adding more logic to
  `systems/main.py`.
- New editor integrations should use the import provider structure under
  `systems/import_providers/`.

## Current Rough Areas

- `systems/main.py` is large and needs to be split into clearer modules.
- The Web feature works, but the interface is cluttered and needs a cleaner
  design.
- macOS support has not been built yet.
- Premiere UXP, Final Cut Pro, and DaVinci Resolve free-version support need
  research before full implementation.

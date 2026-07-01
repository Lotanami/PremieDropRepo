# PremieDrop

PremieDrop is a Windows desktop media library and workflow companion for video
editors.

## Quick Files

| Path | Purpose |
|---|---|
| `PremieDropInstaller-v0.11.exe` | Windows installer executable. |
| `cep-extension/` | Premiere Pro CEP bridge package. |
| `systems/` | PremieDrop application source, build scripts, and developer docs. |

## Build

Build the app executable from `systems`:

```powershell
cd systems
.\build-windows.ps1
```

Build the installer executable from `systems`:

```powershell
cd systems
.\build-installer.ps1
```

The installer displays the available editor package options. The Premiere Pro
CEP extension can be selected; the UXP option is shown disabled until it exists.

# PremieDrop Installer

The installer is a small Windows executable that downloads the latest
`premiedrop.exe`, installs it into `%LOCALAPPDATA%\PremieDrop`, and offers
optional editor packages.

## Build the app executable

```powershell
.\build-windows.ps1
```

The output is:

```text
dist\premiedrop\premiedrop.exe
```

Upload that file to the release URL used by the installer.

## Build the installer executable

```powershell
.\build-installer.ps1
```

The output is:

```text
dist\PremieDropInstaller.exe
```

By default, the installer downloads:

```text
https://github.com/Lotanami/PremieDropRepo/releases/latest/download/premiedrop.exe
```

Set `PREMIEDROP_DOWNLOAD_URL` before launching the installer to test another
download location.

## Editor package options

- Premiere Pro CEP extension: available and bundled into the installer.
- Premiere Pro UXP extension: displayed as a disabled option until the package
  exists.

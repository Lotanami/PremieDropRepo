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
dist\PremieDropInstaller-v0.14.4-beta.exe
```

The build script also copies the installer to:

```text
..\PremieDropInstaller-v0.14.4-beta.exe
```

For each installer iteration, bump `$installerVersion` in
`build-installer.ps1` by `0.01`.

Run `build-windows.ps1` before `build-installer.ps1` to bundle the current
`premiedrop.exe` into the installer. If no app payload exists, the installer
falls back to downloading `premiedrop.exe` from the configured URL.

The browser-capable `premiedrop.exe` is larger than GitHub's normal per-file
commit limit, so publish `systems\payload\premiedrop.exe` as a GitHub Release
asset named `premiedrop.exe` when using the download fallback.

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

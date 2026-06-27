# PremieDrop CEP Bridge

Companion panel for Premiere Pro 2022.

## Install

1. Close Premiere Pro.
2. Run `install.ps1` in PowerShell.
3. Restart Premiere Pro.
4. Open `Window > Extensions > PremieDrop Bridge V0`.

## Test

1. In PremieDrop, select a project media folder.
2. Keep the PremieDrop Bridge V0 panel open in Premiere.
3. Click `Import All to Premiere` in PremieDrop.

The panel reads:

`%APPDATA%\PremieDrop\premiedrop_import_queue.json`

It creates or reuses top-level Premiere bins matching PremieDrop section names,
then automatically imports queued files into those bins. Files already present in
the Premiere project are skipped during automatic imports. Pressing `Import Now`
manually imports the current queue again.

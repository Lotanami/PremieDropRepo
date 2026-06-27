$ErrorActionPreference = "Stop"

$source = $PSScriptRoot
$extensionsRoot = Join-Path $env:APPDATA "Adobe\CEP\extensions"
$destination = Join-Path $extensionsRoot "PremieDrop Bridge V0"

New-Item -ItemType Directory -Force -Path $extensionsRoot | Out-Null
New-Item -ItemType Directory -Force -Path $destination | Out-Null
Copy-Item -Path (Join-Path $source "*") -Destination $destination -Recurse -Force

New-Item -Path "HKCU:\Software\Adobe\CSXS.11" -Force | Out-Null
New-ItemProperty `
    -Path "HKCU:\Software\Adobe\CSXS.11" `
    -Name "PlayerDebugMode" `
    -Value "1" `
    -PropertyType String `
    -Force | Out-Null

Write-Host "PremieDrop CEP installed to:"
Write-Host $destination
Write-Host ""
Write-Host "Restart Premiere Pro, then open Window > Extensions > PremieDrop Bridge V0."

$ErrorActionPreference = "Stop"

$source = $PSScriptRoot
$extensionsRoot = Join-Path $env:APPDATA "Adobe\CEP\extensions"
$destination = Join-Path $extensionsRoot "PremieDrop Bridge V0"
$oldDestinations = @(
    (Join-Path $extensionsRoot "cep-extension"),
    (Join-Path $extensionsRoot "PremieDrop Bridge"),
    (Join-Path $extensionsRoot "PremieDrop")
)

New-Item -ItemType Directory -Force -Path $extensionsRoot | Out-Null
foreach ($oldDestination in $oldDestinations) {
    if (Test-Path $oldDestination) {
        Remove-Item -Path $oldDestination -Recurse -Force
    }
}
New-Item -ItemType Directory -Force -Path $destination | Out-Null
Copy-Item -Path (Join-Path $source "*") -Destination $destination -Recurse -Force

foreach ($version in 11..14) {
    $registryPath = "HKCU:\Software\Adobe\CSXS.$version"
    New-Item -Path $registryPath -Force | Out-Null
    New-ItemProperty `
        -Path $registryPath `
        -Name "PlayerDebugMode" `
        -Value "1" `
        -PropertyType String `
        -Force | Out-Null
}

Write-Host "PremieDrop CEP installed to:"
Write-Host $destination
Write-Host ""
Write-Host "Restart Premiere Pro, then open Window > Extensions > PremieDrop Bridge V0."

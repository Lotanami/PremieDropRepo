$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $projectRoot
$localIcon = Join-Path $projectRoot "premiedrop.ico"

if ($env:PYTHON) {
    $pythonCommand = @($env:PYTHON)
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCommand = @("python")
}
elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCommand = @("py", "-3")
}
else {
    throw "Python 3.10 or newer is required to build PremieDrop."
}

function Invoke-PremieDropPython {
    $command = $pythonCommand[0]
    $baseArgs = @()
    if ($pythonCommand.Count -gt 1) {
        $baseArgs = $pythonCommand[1..($pythonCommand.Count - 1)]
    }
    & $command @baseArgs @args
}

Push-Location $projectRoot
try {
    Invoke-PremieDropPython -m pip install -r requirements.txt
    Invoke-PremieDropPython -m pip install -r build-requirements.txt

    $pyInstallerArgs = @(
        "--noconfirm",
        "--windowed",
        "--noupx",
        "--onefile",
        "--name", "premiedrop",
        "--hidden-import", "youtube_browser",
        "--collect-all", "PyQt5.QtWebEngineWidgets",
        "--collect-all", "PyQt5.QtWebEngineCore",
        "--collect-all", "PyQtWebEngine",
        "--add-data", "premiedrop_ext;premiedrop_ext",
        "--add-data", "import_providers;import_providers",
        "--add-data", "ui_plugins;ui_plugins"
    )
    if (Test-Path -LiteralPath $localIcon) {
        $pyInstallerArgs += @("--icon", $localIcon)
        $pyInstallerArgs += @("--add-data", "$localIcon;.")
    }
    $pyInstallerArgs += "main.py"

    Invoke-PremieDropPython -m PyInstaller @pyInstallerArgs

    Write-Host ""
    Write-Host "Built PremieDrop executable:"
    Write-Host (Join-Path $projectRoot "dist\premiedrop.exe")

    New-Item -ItemType Directory -Force -Path (Join-Path $projectRoot "payload") | Out-Null
    Copy-Item `
        -LiteralPath (Join-Path $projectRoot "dist\premiedrop.exe") `
        -Destination (Join-Path $projectRoot "payload\premiedrop.exe") `
        -Force
    Write-Host "Copied app payload to:"
    Write-Host (Join-Path $projectRoot "payload\premiedrop.exe")
}
finally {
    Pop-Location
}

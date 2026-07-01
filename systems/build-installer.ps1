$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $projectRoot
$installerSource = Join-Path $projectRoot "PremieDropInstaller.py"
$cepPayload = Join-Path $repoRoot "cep-extension"
$appPayload = Join-Path $projectRoot "payload\premiedrop.exe"
$installerVersion = "0.10"
$installerName = "PremieDropInstaller-v$installerVersion"

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
    throw "Python 3.10 or newer is required to build the PremieDrop installer."
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
    Invoke-PremieDropPython -m pip install -r build-requirements.txt

    $pyInstallerArgs = @(
        "--noconfirm",
        "--windowed",
        "--onefile",
        "--name", $installerName,
        "--add-data", "$cepPayload;cep-extension"
    )
    if (Test-Path -LiteralPath $appPayload) {
        $pyInstallerArgs += @("--add-binary", "$appPayload;.")
    }
    else {
        Write-Warning "No app payload found at $appPayload. Installer will use the download fallback."
    }
    $pyInstallerArgs += $installerSource

    Invoke-PremieDropPython -m PyInstaller @pyInstallerArgs

    Write-Host ""
    Write-Host "Built PremieDrop installer:"
    Write-Host (Join-Path $projectRoot "dist\$installerName.exe")

    Copy-Item `
        -LiteralPath (Join-Path $projectRoot "dist\$installerName.exe") `
        -Destination (Join-Path $repoRoot "$installerName.exe") `
        -Force
    Write-Host "Copied installer to:"
    Write-Host (Join-Path $repoRoot "$installerName.exe")
}
finally {
    Pop-Location
}

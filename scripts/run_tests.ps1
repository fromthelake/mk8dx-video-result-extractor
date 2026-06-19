param(
    [switch]$SkipCompile
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$script:PythonExe = $null
$script:PythonArgs = @()

function Set-ProjectPython {
    $venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        $script:PythonExe = $venvPython
        $script:PythonArgs = @()
        return
    }
    if (-not [string]::IsNullOrWhiteSpace($env:PYTHON_BIN)) {
        $script:PythonExe = $env:PYTHON_BIN
        $script:PythonArgs = @()
        return
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.12 --version *> $null
        if ($LASTEXITCODE -eq 0) {
            $script:PythonExe = "py"
            $script:PythonArgs = @("-3.12")
            return
        }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $script:PythonExe = "python"
        $script:PythonArgs = @()
        return
    }
    throw "No Python interpreter found. Run scripts\setup_windows.ps1 first or install Python 3.12."
}

function Invoke-ProjectPython {
    $allArgs = @()
    $allArgs += $script:PythonArgs
    $allArgs += $args
    & $script:PythonExe @allArgs
}

Set-ProjectPython
Set-Location $projectRoot

$versionText = Invoke-ProjectPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($versionText -ne "3.12") {
    throw "This project requires Python 3.12. Current interpreter is $versionText via $script:PythonExe"
}

Write-Host "Using Python interpreter: $script:PythonExe $($script:PythonArgs -join ' ')"
if (-not $SkipCompile) {
    Invoke-ProjectPython -m compileall mk8dx_video_result_extractor
}
Invoke-ProjectPython -m unittest discover

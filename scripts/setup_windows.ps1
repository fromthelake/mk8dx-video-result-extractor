param(
    [switch]$CreateVenv,
    [ValidateSet("Auto", "Cuda", "Cpu", "RocmExperimental")]
    [string]$TorchMode = "Auto"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

function Resolve-PythonBootstrap {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        try {
            & py -3.12 --version *> $null
            if ($LASTEXITCODE -eq 0) {
                return @("py", "-3.12")
            }
        } catch {
        }
        throw "Python 3.12 was not found. Install Python 3.12 first."
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $versionText = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
        if ($versionText -eq "3.12") {
            return @("python")
        }
        throw "Python 3.12 was not found. Install Python 3.12 first."
    }
    throw "No Python launcher was found. Install Python 3.12 first."
}

function Assert-Python312($pythonExe) {
    $versionText = & $pythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ($versionText -ne "3.12") {
        throw "This project requires Python 3.12. Current interpreter is $versionText at $pythonExe"
    }
}

function Assert-FFmpeg {
    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
        throw "FFmpeg was not found on PATH. Install FFmpeg, open a new PowerShell window, and rerun setup."
    }
}

function Remove-ProjectEggInfo($rootPath) {
    Get-ChildItem -Path $rootPath -Directory -Filter "*.egg-info" -ErrorAction SilentlyContinue | ForEach-Object {
        Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Select-TorchPackage($pythonExe, $mode) {
    $decisionJson = & $pythonExe -m mk8dx_video_result_extractor.setup_torch --mode $mode --format json
    if ($LASTEXITCODE -ne 0) {
        throw "Hardware-aware PyTorch selection failed."
    }
    return ($decisionJson | Out-String | ConvertFrom-Json)
}

function Write-TorchDecision($decision) {
    $gpuNames = @($decision.gpu_names)
    $gpuText = "none reported"
    if ($gpuNames.Count -gt 0 -and -not [string]::IsNullOrWhiteSpace([string]$gpuNames[0])) {
        $gpuText = ($gpuNames -join ", ")
    }
    Write-Host "Hardware scan:"
    Write-Host "  OS: $($decision.system) ($($decision.machine))"
    Write-Host "  GPUs: $gpuText"
    Write-Host "  nvidia-smi available: $($decision.nvidia_smi_available)"
    Write-Host "  requested torch mode: $($decision.requested_mode)"
    Write-Host "  selected torch mode: $($decision.selected_mode)"
    Write-Host "  expected GPU OCR: $($decision.expected_gpu_ocr)"
    Write-Host "  reason: $($decision.reason)"
    foreach ($warning in @($decision.warnings)) {
        if (-not [string]::IsNullOrWhiteSpace($warning)) {
            Write-Warning $warning
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($decision.post_install_note)) {
        Write-Host "  note: $($decision.post_install_note)"
    }
}

function Install-SelectedTorch($pythonExe, $decision) {
    if ($decision.requires_manual_setup) {
        throw $decision.reason
    }
    $pipArgs = @($decision.pip_args)
    if ($pipArgs.Count -eq 0) {
        throw "PyTorch selection did not produce install arguments."
    }
    Write-Host "Installing PyTorch package set for mode '$($decision.selected_mode)'..."
    & $pythonExe -m pip install @pipArgs
}

if ($CreateVenv -or -not (Test-Path ".venv\Scripts\python.exe")) {
    $bootstrap = Resolve-PythonBootstrap
    if ($bootstrap.Length -gt 1) {
        & $bootstrap[0] $bootstrap[1] -m venv .venv
    } else {
        & $bootstrap[0] -m venv .venv
    }
}

$python = ".\.venv\Scripts\python.exe"
$playExe = ".\.venv\Scripts\mk8-local-play.exe"
Assert-Python312 $python
Assert-FFmpeg
Write-Host "Using Python interpreter: $python"
$torchDecision = Select-TorchPackage $python $TorchMode
Write-TorchDecision $torchDecision
& $python -m pip install --upgrade pip setuptools wheel
Install-SelectedTorch $python $torchDecision
& $python -m pip install -e ".[gui]"
Remove-ProjectEggInfo $projectRoot

if (-not (Test-Path $playExe)) {
    Write-Host "Console launchers missing after editable install, retrying with forced reinstall..."
    & $python -m pip install --force-reinstall -e ".[gui]"
    Install-SelectedTorch $python $torchDecision
    Remove-ProjectEggInfo $projectRoot
}

if (-not (Test-Path $playExe)) {
    throw "Setup completed dependency install, but mk8-local-play.exe was not created in .venv\Scripts."
}

$configPath = "config\app_config.json"
$exampleConfigPath = "config\app_config.example.json"
if (-not (Test-Path $configPath)) {
    if (-not (Test-Path $exampleConfigPath)) {
        throw "Missing $exampleConfigPath. Restore it from git before running setup."
    }
    Copy-Item $exampleConfigPath $configPath
    Write-Host "Created local $configPath from $exampleConfigPath."
}

& $playExe --check

Write-Host ""
Write-Host "Setup finished."
Write-Host "This app runs from the local .venv in this project folder."
Write-Host "No global Python package install or PATH change is required for mk8-local-play."
Write-Host "PyTorch mode selected by setup: $($torchDecision.selected_mode). Use --check to confirm the active OCR backend."
Write-Host "Next steps:"
Write-Host "1. Put videos into Input_Videos."
Write-Host "2. Run .\.venv\Scripts\mk8-local-play.exe to open the GUI."
Write-Host "3. Or run .\.venv\Scripts\mk8-local-play.exe --all from PowerShell."
Write-Host "   or run .\.venv\Scripts\python.exe -m mk8dx_video_result_extractor.main --all"

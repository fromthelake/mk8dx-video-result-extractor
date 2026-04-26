param(
    [string]$VideoName = "Test_3_Races.mkv",
    [string]$BaselineDir = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

$holdDir = Join-Path $projectRoot "Input_Videos_Hold"

if ([string]::IsNullOrWhiteSpace($BaselineDir)) {
    throw "BaselineDir is required. Provide an explicit baseline path via -BaselineDir."
}
if (-not (Test-Path $BaselineDir)) {
    throw "BaselineDir does not exist: $BaselineDir"
}

try {
    if (Test-Path $holdDir) {
        Get-ChildItem $holdDir -File | Move-Item -Destination "Input_Videos" -Force
        Remove-Item $holdDir -Force
    }

    New-Item -ItemType Directory -Force -Path $holdDir | Out-Null
    Get-ChildItem "Input_Videos" -File | Where-Object { $_.Name -ne $VideoName } | Move-Item -Destination $holdDir -Force

    Get-ChildItem "Output_Results\Frames" -File -ErrorAction SilentlyContinue | Remove-Item -Force
    Get-ChildItem "Output_Results\Debug\Score_Frames" -File -ErrorAction SilentlyContinue | Remove-Item -Force
    Remove-Item "Output_Results\Debug\debug_max_val.csv" -Force -ErrorAction SilentlyContinue
    Get-ChildItem "Output_Results" -File -Filter "*_Tournament_Results.xlsx" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    Remove-Item "Output_Results\Tournament_Results.xlsx" -Force -ErrorAction SilentlyContinue
    Remove-Item "Output_Results\~`$Tournament_Results.xlsx" -Force -ErrorAction SilentlyContinue

    & $python -m mk8dx_video_result_extractor.main --check

    $extract = Measure-Command { & $python -m mk8dx_video_result_extractor.main --extract --video $VideoName }
    $ocr = Measure-Command { & $python -m mk8dx_video_result_extractor.main --ocr --video $VideoName }

    & $python tools\validate_outputs.py --baseline-dir $BaselineDir

    Write-Host ("extract_seconds={0:N2}" -f $extract.TotalSeconds)
    Write-Host ("ocr_seconds={0:N2}" -f $ocr.TotalSeconds)
}
finally {
    if (Test-Path $holdDir) {
        Get-ChildItem $holdDir -File | Move-Item -Destination "Input_Videos" -Force
        Remove-Item $holdDir -Force
    }
}

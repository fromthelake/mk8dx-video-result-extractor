param(
    [switch]$KeepCodexTmp,
    [switch]$KeepAbRuns
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Assert-InProjectRoot($Path) {
    $resolved = (Resolve-Path -LiteralPath $Path).Path
    if (-not $resolved.StartsWith($projectRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to delete outside project root: $resolved"
    }
    return $resolved
}

function Remove-GeneratedTarget($Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }
    $resolved = Assert-InProjectRoot $Path
    Remove-Item -LiteralPath $resolved -Recurse -Force
    Write-Host "Removed $resolved"
}

$cacheRoots = @(
    "mk8dx_video_result_extractor",
    "mk8dx_video_result_extractor_data",
    "tests",
    "tools"
)

foreach ($root in $cacheRoots) {
    $rootPath = Join-Path $projectRoot $root
    if (-not (Test-Path -LiteralPath $rootPath)) {
        continue
    }
    Get-ChildItem -LiteralPath $rootPath -Recurse -Directory -Force -Filter "__pycache__" |
        ForEach-Object { Remove-GeneratedTarget $_.FullName }
}

foreach ($cacheName in @(".pytest_cache", ".mypy_cache", ".ruff_cache")) {
    Remove-GeneratedTarget (Join-Path $projectRoot $cacheName)
}

if (-not $KeepCodexTmp) {
    Remove-GeneratedTarget (Join-Path $projectRoot ".codex_tmp")
}

if (-not $KeepAbRuns) {
    Remove-GeneratedTarget (Join-Path $projectRoot ".ab_runs")
}

Write-Host "Generated-artifact cleanup complete."

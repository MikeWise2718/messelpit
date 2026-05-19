<#
.SYNOPSIS
    Build all three USD variants of messel.usd at different mesh resolutions.

.DESCRIPTION
    Runs src/messelpit/build_usd.py three times to produce:

      out/messel.usd       full-res (decimate=1)  ~54M verts, ~1 GB     reference / offline renders
      out/messel_med.usd   decimate=4             ~3.4M verts, ~250 MB  default for desktop Kit
      out/messel_lo.usd    decimate=8             ~840K verts, ~50 MB   Quest streaming target

    The texture (out/ortho.png) is the same for all three; only the mesh
    density differs. Each variant gets a sibling .usdz packed alongside.

    Requires data/prep/dem.tif and data/prep/ortho.png to already exist
    (produced by tools/prep_rasters.py). The .venv must be set up.

.PARAMETER Force
    Rebuild variants even if the .usd already exists. Without this flag,
    existing variants are skipped (fast incremental re-runs).

.PARAMETER SkipFullRes
    Don't build the full-res variant. Useful on machines where the full-res
    build is too slow or unnecessary -- the med + lo variants are usually
    what you actually want.

.PARAMETER NoUsdz
    Don't pack .usdz alongside each .usd. Faster, but you lose portability.

.EXAMPLE
    .\tools\build_variants.ps1
    Build any variants that don't exist yet.

.EXAMPLE
    .\tools\build_variants.ps1 -Force
    Rebuild all three from scratch.

.EXAMPLE
    .\tools\build_variants.ps1 -SkipFullRes -NoUsdz
    Quick build: just med + lo as .usd only.
#>
[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$SkipFullRes,
    [switch]$NoUsdz
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$outDir = Join-Path $repoRoot "out"
$prepDir = Join-Path $repoRoot "data\prep"

if (-not (Test-Path $python)) {
    Write-Error "Python interpreter not found at $python -- run 'uv venv' + 'uv pip install -e .' first."
}
foreach ($f in @("dem.tif", "ortho.png", "origin.json")) {
    $p = Join-Path $prepDir $f
    if (-not (Test-Path $p)) {
        Write-Error "Missing $p -- run 'python tools/prep_rasters.py' first."
    }
}

$variants = @(
    @{ Name = "full"; Decimate = 1; Out = "out\messel.usd" }
    @{ Name = "med";  Decimate = 4; Out = "out\messel_med.usd" }
    @{ Name = "lo";   Decimate = 8; Out = "out\messel_lo.usd" }
)

if ($SkipFullRes) {
    $variants = $variants | Where-Object { $_.Name -ne "full" }
}

foreach ($v in $variants) {
    $outPath = Join-Path $repoRoot $v.Out
    $skip = (Test-Path $outPath) -and -not $Force
    Write-Host ""
    Write-Host "=== $($v.Name) variant (decimate=$($v.Decimate)) -> $($v.Out) ===" -ForegroundColor Cyan
    if ($skip) {
        Write-Host "exists -- skipping (use -Force to rebuild)" -ForegroundColor Yellow
        continue
    }
    $pyArgs = @("-m", "messelpit.build_usd", "--decimate", $v.Decimate, "--out", $v.Out)
    if (-not $NoUsdz) { $pyArgs += "--usdz" }
    Push-Location $repoRoot
    try {
        & $python @pyArgs
        if ($LASTEXITCODE -ne 0) {
            Write-Error "build_usd failed for $($v.Name) (exit $LASTEXITCODE)"
        }
    } finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "Variants in $outDir :" -ForegroundColor Green
Get-ChildItem $outDir -Filter "messel*.usd*" | Sort-Object Name | ForEach-Object {
    $sizeMB = [string]::Format('{0,7:N1} MB', ($_.Length / 1MB))
    Write-Host "  $sizeMB  $($_.Name)"
}

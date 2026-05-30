<#
.SYNOPSIS
    Build the USD variants of messel.usd at different mesh and texture sizes.

.DESCRIPTION
    Runs src/messelpit/build_usd.py to produce:

      out/messel.usd          full-res (decimate=1)  ~54M verts, ~1 GB     reference / offline renders
      out/messel_med.usd      decimate=4             ~3.4M verts, ~65 MB   default for desktop Kit
      out/messel_lo.usd       decimate=8             ~840K verts, ~16 MB   loose-file low-poly variant
      out/messel_lo.usdz      decimate=8 + 16384 q90 ~44 MB                packaged low-poly, JPEG-textured
      out/messel_lo_quest.usdz decimate=8 + 8192 q90 ~24 MB                Quest streaming target

    The texture (out/ortho.png) is the same for the loose .usd variants;
    only the .usdz variants downsize/JPEG-compress the bundled texture.

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
    Rebuild all variants from scratch.

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

# Each variant authors a .usd + (optionally) a .usdz. Variants ending in
# _quest reuse the lo mesh but bundle a downsized 8192-wide JPEG texture
# suited to Quest 3 streaming. The texture-prep step only runs for usdz.
$variants = @(
    @{ Name = "full";     Decimate = 1; Out = "out\messel.usd";          TexMaxDim = 16384 }
    @{ Name = "med";      Decimate = 4; Out = "out\messel_med.usd";      TexMaxDim = 16384 }
    @{ Name = "lo";       Decimate = 8; Out = "out\messel_lo.usd";       TexMaxDim = 16384 }
    @{ Name = "lo_quest"; Decimate = 8; Out = "out\messel_lo_quest.usd"; TexMaxDim = 8192 }
)

if ($SkipFullRes) {
    $variants = $variants | Where-Object { $_.Name -ne "full" }
}

# lo_quest only makes sense as a .usdz -- if -NoUsdz is set, skip it.
if ($NoUsdz) {
    $variants = $variants | Where-Object { $_.Name -ne "lo_quest" }
}

foreach ($v in $variants) {
    $outPath = Join-Path $repoRoot $v.Out
    $usdzPath = [System.IO.Path]::ChangeExtension($outPath, ".usdz")
    # Skip rule: lo_quest only ships as .usdz, so check the .usdz for existence.
    $checkPath = if ($v.Name -eq "lo_quest") { $usdzPath } else { $outPath }
    $skip = (Test-Path $checkPath) -and -not $Force
    Write-Host ""
    Write-Host "=== $($v.Name) variant (decimate=$($v.Decimate), tex=$($v.TexMaxDim)) -> $($v.Out) ===" -ForegroundColor Cyan
    if ($skip) {
        Write-Host "exists -- skipping (use -Force to rebuild)" -ForegroundColor Yellow
        continue
    }
    $pyArgs = @("-m", "messelpit.build_usd", "--decimate", $v.Decimate, "--out", $v.Out)
    if (-not $NoUsdz) {
        # JPEG q90 inside the .usdz keeps the bundle small without visible
        # quality loss on orthophoto content. The on-disk .usd still
        # references the original lossless PNG via ./ortho.png.
        $pyArgs += @("--usdz", "--texture-format", "jpeg", "--texture-quality", "90",
                     "--texture-max-dim", $v.TexMaxDim)
    }
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

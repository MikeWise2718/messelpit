<#
.SYNOPSIS
    Build the OSM buildings+roads overlay and compose it onto the terrain.

.DESCRIPTION
    Two steps:

      1. Run the sibling `osm2usd` builder on data/messel_osm.json (OSM
         geometry exported by overpy in raw WGS84), draping it onto the
         Messel DEM and grouping it by class. Produces out/messel_osm.usd
         with /World/OSM/{Roads,Buildings}/<class> subtrees.

      2. Author a wrapper stage out/messel_lo_with_osm.usd that references
         BOTH the untouched terrain (out/messel_lo.usd) and the overlay.
         The base messel_lo.usd is never modified.

    Inputs required:
      data/messel_osm.json     OSM geometry (overpy `export-json` output)
      data/prep/origin.json    EPSG + SW-corner origin (from prep_rasters.py)
      data/prep/dem.tif        local-frame DEM for draping
      out/messel_lo.usd        base terrain (from build_variants.ps1)

    Dependencies:
      The `osm2usd` package must be importable. It lives as a sibling repo at
      ..\osm2usd. Either `uv pip install -e ..\osm2usd` into messelpit's
      .venv, or point -Osm2UsdPython at its interpreter.

.PARAMETER Osm2UsdPython
    Python interpreter that can import osm2usd. Default: messelpit's own
    .venv python (assumes osm2usd was installed editable into it).

.PARAMETER Terrain
    Base terrain USD to compose onto. Default out/messel_lo.usd.

.PARAMETER Force
    Rebuild out/messel_osm.usd even if it already exists.

.EXAMPLE
    .\tools\build_osm_overlay.ps1
    Build the overlay and the wrapper using cached messel_osm.usd if present.

.EXAMPLE
    .\tools\build_osm_overlay.ps1 -Force
    Re-run osm2usd from the JSON even if out/messel_osm.usd exists.
#>
[CmdletBinding()]
param(
    [string]$Osm2UsdPython = ".venv\Scripts\python.exe",
    [string]$Terrain = "out\messel_lo.usd",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$osmJson  = "data\messel_osm.json"
$origin   = "data\prep\origin.json"
$dem      = "data\prep\dem.tif"
$osmUsd   = "out\messel_osm.usd"
$wrapper  = "out\messel_lo_with_osm.usd"

foreach ($p in @($osmJson, $origin, $dem, $Terrain)) {
    if (-not (Test-Path $p)) {
        Write-Error "Missing required input: $p"
    }
}

if ($Force -or -not (Test-Path $osmUsd)) {
    Write-Host "Step 1/2: osm2usd -> $osmUsd" -ForegroundColor Cyan
    & $Osm2UsdPython -m osm2usd.cli build `
        -j $osmJson `
        -o $osmUsd `
        --origin $origin `
        --dem $dem
    if ($LASTEXITCODE -ne 0) { Write-Error "osm2usd build failed (exit $LASTEXITCODE)" }
} else {
    Write-Host "Step 1/2: $osmUsd exists, skipping (use -Force to rebuild)" -ForegroundColor Yellow
}

Write-Host "Step 2/2: wrapper stage -> $wrapper" -ForegroundColor Cyan
& ".venv\Scripts\python.exe" -m messelpit.build_overlay_stage `
    --terrain $Terrain `
    --overlay $osmUsd `
    --out $wrapper
if ($LASTEXITCODE -ne 0) { Write-Error "wrapper authoring failed (exit $LASTEXITCODE)" }

Write-Host "Done. Open $wrapper in the viewer." -ForegroundColor Green

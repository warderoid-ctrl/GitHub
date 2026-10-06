<#
.SYNOPSIS
    Download and install the bundled Meshroom / AliceVision binaries into tools\.

.DESCRIPTION
    Downloads Meshroom 2025.1.0 (Windows, CUDA 12) from Zenodo, verifies its MD5,
    extracts it to tools\Meshroom-2025.1.0, and runs the install check.

    The download is ~9.5 GiB and resumes if interrupted, so re-running after a
    dropped connection is safe and cheap.

.PARAMETER KeepArchive
    Keep the downloaded .zip in tools\_downloads instead of deleting it after a
    successful extraction.

.PARAMETER Force
    Re-extract even if tools\Meshroom-2025.1.0 already exists.
#>
[CmdletBinding()]
param(
    [switch]$KeepArchive,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

$Version   = '2025.1.0'
$Url       = 'https://zenodo.org/records/16887472/files/Meshroom-2025.1.0-Windows.zip?download=1'
$Md5       = '6af3282e0b6e739a36a2607d8e86fa82'

$Root      = Split-Path -Parent $PSScriptRoot
$ToolsDir  = Join-Path $Root 'tools'
$DlDir     = Join-Path $ToolsDir '_downloads'
$Archive   = Join-Path $DlDir "Meshroom-$Version-Windows.zip"
$Target    = Join-Path $ToolsDir "Meshroom-$Version"

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "!!  $msg" -ForegroundColor Yellow }

if ((Test-Path $Target) -and -not $Force) {
    Write-Step "Already installed at $Target (use -Force to reinstall)."
} else {
    New-Item -ItemType Directory -Force -Path $DlDir | Out-Null

    # --- Download (resumable) -------------------------------------------------
    if (Test-Path $Archive) {
        $haveGb = [math]::Round((Get-Item $Archive).Length / 1GB, 2)
        Write-Step "Resuming download (have $haveGb GiB)..."
    } else {
        Write-Step 'Downloading Meshroom (~9.5 GiB); this takes a while...'
    }
    & curl.exe -L -C - --retry 5 --retry-delay 10 --retry-all-errors -o $Archive $Url
    if ($LASTEXITCODE -ne 0) { throw "Download failed (curl exit $LASTEXITCODE). Re-run to resume." }

    # --- Verify ---------------------------------------------------------------
    Write-Step 'Verifying checksum...'
    $actual = (Get-FileHash -Path $Archive -Algorithm MD5).Hash.ToLower()
    if ($actual -ne $Md5) {
        throw "Checksum mismatch: expected $Md5, got $actual. Delete $Archive and re-run."
    }
    Write-Host "    MD5 OK"

    # --- Extract --------------------------------------------------------------
    $staging = Join-Path $ToolsDir "_staging-$Version"
    if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $staging | Out-Null

    Write-Step 'Extracting (several minutes)...'
    # tar.exe ships with Windows 10+ and is far faster than Expand-Archive here.
    & tar.exe -xf $Archive -C $staging
    if ($LASTEXITCODE -ne 0) {
        Write-Warn 'tar failed; falling back to Expand-Archive.'
        Expand-Archive -Path $Archive -DestinationPath $staging -Force
    }

    # The archive may or may not carry its own top-level folder; normalise both.
    $entries = @(Get-ChildItem $staging)
    $source  = if ($entries.Count -eq 1 -and $entries[0].PSIsContainer) { $entries[0].FullName } else { $staging }

    if (Test-Path $Target) { Remove-Item $Target -Recurse -Force }
    Move-Item -Path $source -Destination $Target
    if (Test-Path $staging) { Remove-Item $staging -Recurse -Force -ErrorAction SilentlyContinue }

    if (-not $KeepArchive) {
        Write-Step 'Removing archive to reclaim disk space (-KeepArchive to retain).'
        Remove-Item $Archive -Force
    }
    Write-Step "Installed to $Target"
}

Write-Step 'Checking the install...'
& python (Join-Path $PSScriptRoot 'scan.py') --doctor
exit $LASTEXITCODE

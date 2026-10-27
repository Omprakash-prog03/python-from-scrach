<#
.SYNOPSIS
  PlateSense one-click installer for Windows.

.DESCRIPTION
  Downloads the latest PlateSense Windows release from GitHub, extracts it
  to %LOCALAPPDATA%\PlateSense, creates Start Menu + Desktop shortcuts, and
  optionally launches the app.

  One-line install (PowerShell):
      irm https://raw.githubusercontent.com/Omprakash-prog03/python-from-scrach/main/platesense/scripts/install.ps1 | iex

  With options (set env vars before piping):
      $env:PLATESENSE_VERSION="v1.0.0"; $env:PLATESENSE_LAUNCH="1"; irm <url> | iex

  Or run the file directly with params:
      .\install.ps1 -Version v1.0.0 -InstallDir "C:\Apps\PlateSense" -Launch
#>

[CmdletBinding()]
param(
    [string]$Version    = "",
    [string]$InstallDir = "",
    [switch]$NoShortcuts,
    [switch]$Launch
)

$ErrorActionPreference = "Stop"
$RepoOwner = "Omprakash-prog03"
$RepoName  = "python-from-scrach"

function Install-PlateSense {
    [CmdletBinding()]
    param(
        [string]$Version,
        [string]$InstallDir,
        [switch]$NoShortcuts,
        [switch]$Launch
    )

    function Write-Step($msg) { Write-Host "[platesense] $msg" -ForegroundColor Cyan }
    function Write-Ok($msg)   { Write-Host "           $msg" -ForegroundColor Green }
    function Write-Warn($msg) { Write-Host "           $msg" -ForegroundColor Yellow }
    function Write-Fail($msg) { Write-Host "           $msg" -ForegroundColor Red }

    if (-not $Version)    { $Version    = if ($env:PLATESENSE_VERSION) { $env:PLATESENSE_VERSION } else { "latest" } }
    if ($env:PLATESENSE_LAUNCH -eq "1") { $Launch = $true }

    if (-not $InstallDir) {
        $InstallDir = if ($env:PLATESENSE_DIR) { $env:PLATESENSE_DIR } else { Join-Path $env:LOCALAPPDATA "PlateSense" }
    }

    # --- Resolve latest version if needed -----------------------------------
    if ($Version -eq "latest") {
        Write-Step "Looking up latest release on GitHub..."
        try {
            $rel = Invoke-RestMethod -Uri "https://api.github.com/repos/$RepoOwner/$RepoName/releases/latest" -UseBasicParsing
            $Version = $rel.tag_name
        } catch {
            Write-Fail "Could not reach GitHub API to find latest release."
            Write-Fail "Check your internet connection, or set `$env:PLATESENSE_VERSION='vX.Y.Z' and retry."
            return 1
        }
    }
    Write-Ok "Version: $Version"

    $VersionClean = $Version -replace '^v',''
    $zipName = "PlateSense-$VersionClean-win-x64.zip"
    $downloadUrl = "https://github.com/$RepoOwner/$RepoName/releases/download/$Version/$zipName"

    # --- Prepare temp dir ---------------------------------------------------
    $tmpDir = Join-Path $env:TEMP "platesense-install-$(Get-Random)"
    New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
    $zipPath = Join-Path $tmpDir $zipName

    # --- Download -----------------------------------------------------------
    Write-Step "Downloading $downloadUrl"
    try {
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath -UseBasicParsing
    } catch {
        Write-Fail "Download failed: $($_.Exception.Message)"
        Write-Fail ""
        Write-Fail "Common causes:"
        Write-Fail "  * The release is still building (CI takes 3-5 minutes after the tag is pushed)."
        Write-Fail "  * You're offline or GitHub is unreachable."
        Write-Fail ""
        Write-Fail "Manual fallback: grab the zip from"
        Write-Fail "  https://github.com/$RepoOwner/$RepoName/releases"
        return 1
    }
    $zipSize = (Get-Item $zipPath).Length
    Write-Ok "Downloaded $([math]::Round($zipSize/1MB,1)) MB"

    # --- Extract ------------------------------------------------------------
    Write-Step "Installing to $InstallDir"
    if (Test-Path $InstallDir) {
        Write-Warn "Existing installation found — replacing it."
        $proc = Get-Process -Name "PlateSense" -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Warn "PlateSense is running — closing it..."
            Stop-Process -Name "PlateSense" -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
        }
        Remove-Item -Recurse -Force $InstallDir
    }
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    Expand-Archive -Path $zipPath -DestinationPath $InstallDir -Force
    $exePath = Join-Path $InstallDir "PlateSense.exe"
    if (-not (Test-Path $exePath)) {
        Write-Fail "Install failed: PlateSense.exe not found after extraction."
        Write-Fail "The downloaded zip may be corrupt or from an incompatible build."
        return 1
    }
    Write-Ok "Extracted to $InstallDir"

    # --- Unblock ------------------------------------------------------------
    Get-ChildItem -Path $InstallDir -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
        try { Unblock-File $_.FullName -ErrorAction SilentlyContinue } catch {}
    }

    # --- Shortcuts ----------------------------------------------------------
    if (-not $NoShortcuts) {
        Write-Step "Creating shortcuts..."
        try {
            $WshShell = New-Object -ComObject WScript.Shell

            $desktopPath = [Environment]::GetFolderPath("Desktop")
            $shortcutPath = Join-Path $desktopPath "PlateSense.lnk"
            $sc = $WshShell.CreateShortcut($shortcutPath)
            $sc.TargetPath = $exePath
            $sc.WorkingDirectory = $InstallDir
            $sc.IconLocation = $exePath
            $sc.Description = "PlateSense — Indian Number Plate Detection"
            $sc.Save()
            Write-Ok "Desktop shortcut: $shortcutPath"

            $startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\PlateSense"
            New-Item -ItemType Directory -Path $startMenu -Force | Out-Null
            $smShortcut = Join-Path $startMenu "PlateSense.lnk"
            $sc = $WshShell.CreateShortcut($smShortcut)
            $sc.TargetPath = $exePath
            $sc.WorkingDirectory = $InstallDir
            $sc.IconLocation = $exePath
            $sc.Description = "PlateSense"
            $sc.Save()

            $uninstallVbs = Join-Path $InstallDir "uninstall.ps1"
            @'
$install = Split-Path -Parent $MyInvocation.MyCommand.Path
$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\PlateSense"
$desktop = Join-Path ([Environment]::GetFolderPath("Desktop")) "PlateSense.lnk"
Get-Process -Name PlateSense -ErrorAction SilentlyContinue | Stop-Process -Force
Remove-Item -Recurse -Force $install -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force $startMenu -ErrorAction SilentlyContinue
Remove-Item -Force $desktop -ErrorAction SilentlyContinue
Write-Host "PlateSense removed." -ForegroundColor Green
Start-Sleep -Seconds 2
'@ | Set-Content -Path $uninstallVbs
            $uninstallShortcut = Join-Path $startMenu "Uninstall PlateSense.lnk"
            $sc = $WshShell.CreateShortcut($uninstallShortcut)
            $sc.TargetPath = "powershell.exe"
            $sc.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$uninstallVbs`""
            $sc.Description = "Uninstall PlateSense"
            $sc.Save()
            Write-Ok "Start Menu folder: $startMenu"
        } catch {
            Write-Warn "Could not create shortcuts ($($_.Exception.Message)) — you can still run PlateSense.exe directly."
        }
    }

    # --- Cleanup ------------------------------------------------------------
    Remove-Item -Recurse -Force $tmpDir -ErrorAction SilentlyContinue

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host " PlateSense $Version installed successfully." -ForegroundColor Green
    Write-Host " Location: $InstallDir" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green

    if ($Launch) {
        Write-Step "Launching PlateSense..."
        Start-Process -FilePath $exePath -WorkingDirectory $InstallDir
    } else {
        Write-Host " Double-click PlateSense.exe or the Desktop shortcut to start." -ForegroundColor Cyan
    }
    return 0
}

# When piped via `irm <url> | iex`, param() bound nothing; use defaults.
# When dot-sourced or invoked directly, params were already bound.
if (-not $Version)    { $Version    = "" }
if (-not $InstallDir) { $InstallDir = "" }

$null = Install-PlateSense -Version $Version -InstallDir $InstallDir -NoShortcuts:$NoShortcuts -Launch:$Launch
exit $LASTEXITCODE

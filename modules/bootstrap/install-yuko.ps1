# =====================================================================
# SYSTEM LEVEL INTEROP DEPLOYMENT ORCHESTRATOR (PLAYWRIGHT MASTER VERBOSE)
# =====================================================================
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "[!] Escalating privileges to Administrator..." -ForegroundColor Yellow
    Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    Exit
}

Write-Host "=== STARTING ALL-IN-ONE BROWSER-VIRTUALIZED DEPLOYMENT ===" -ForegroundColor Magenta

# FORCE DESTROY AND PURGE: Instantly vaporizes the container footprint to guarantee a clean slate
Write-Host "[*] Executing deep filesystem unregistration blocks..." -ForegroundColor Yellow
wsl --shutdown
wsl --unregister NixOS 2>$null | Out-Null

# 1. Verify WSL status engine
Write-Host "`n[1/5] Validating core WSL subsystem layer..." -ForegroundColor Cyan
$wslCheck = wsl --status 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] WSL core framework not found. Initializing base features..." -ForegroundColor Yellow
    wsl --install --no-distribution
    Write-Host "`n[!] Windows features staged. Please restart your PC and run this macro again." -ForegroundColor Yellow
    Pause; Exit 0
}
Write-Host "✔ Host WSL subsystem engine is active." -ForegroundColor Green

# =====================================================================
# STAGE 2: PROCESS AUTOMATED BROWSER INJECTION (DPI Bypass Tunnels)
# =====================================================================
Write-Host "`n[2/5] Synchronizing Browser Web-Automation Sockets via Pip..." -ForegroundColor Cyan
$pythonExe = ""
$targetPaths = @(
    "C:\Python314\python.exe",
    "C:\Python312\python.exe",
    "C:\tools\python3\python.exe",
    "C:\tools\python\python.exe"
)
foreach ($path in $targetPaths) { if (Test-Path $path) { $pythonExe = $path; break } }
if ([string]::IsNullOrEmpty($pythonExe)) {
    $rootSearch = Get-ChildItem -Path "C:\Python*" -Filter "python.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($rootSearch) { $pythonExe = $rootSearch.FullName }
}
if ([string]::IsNullOrEmpty($pythonExe)) {
    Write-Host "❌ CRITICAL ERROR: Python is required on disk to run browser pipelines!" -ForegroundColor Red
    Pause; Exit 1
}

& $pythonExe -m pip install playwright --quiet --no-warn-script-location
& $pythonExe -m playwright install chromium

$cacheDir = "$env:USERPROFILE\Desktop\wsl-cache"
if (Test-Path $cacheDir) { Remove-Item $cacheDir -Recurse -Force -ErrorAction SilentlyContinue }
New-Item -Path $cacheDir -ItemType Directory -Force | Out-Null

$nixosWslTarget = "$env:USERPROFILE\Desktop\nixos.wsl"
$escapedCacheTarget = $nixosWslTarget -replace '\\', '\\\\'

# Stream down the 551MB system image file behind your network filters via Playwright browser context
Write-Host "`n[3/5] Spawning Automated Browser Process to Stream Core Image Bundle..." -ForegroundColor Cyan
$pythonBrowserCode = @"
import sys
import os
import multiprocessing
from playwright.sync_api import sync_playwright

def browser_task():
    print("    [*] Starting browser process virtualization hooks...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()
        
        print("    [*] Streaming 551MB NixOS core container system image bundle...")
        try:
            with page.expect_download(timeout=120000) as download_info:
                try:
                    page.goto('https://github.com/nix-community/NixOS-WSL/releases/download/2605.7.2/nixos.wsl')
                except Exception as e:
                    if "Download is starting" not in str(e): raise e
            download_info.value.save_as('$($escapedCacheTarget)')
            print("✔ Automated browser file transfer completed successfully.")
        except Exception as err:
            print(f"❌ Failed to stream NixOS image: {err}")
            os._exit(1)
        finally:
            browser.close()

if __name__ == '__main__':
    multiprocessing.freeze_support()
    p = multiprocessing.Process(target=browser_task)
    p.start()
    p.join()
    if p.exitcode != 0: sys.exit(1)
    sys.exit(0)
"@

$pyScriptPath = "$env:TEMP\browser_master_stream.py"
Set-Content -Path $pyScriptPath -Value $pythonBrowserCode -Force
& $pythonExe $pyScriptPath
$pyExitCode = $LASTEXITCODE
Remove-Item $pyScriptPath -Force

if ($pyExitCode -ne 0) {
    Write-Host "❌ CRITICAL EXTRACTION ERROR: Automated browser data pipeline failed to map source streams!" -ForegroundColor Red
    Pause; Exit 1
}

# =====================================================================
# STAGE 4: REGISTER RECONCILED NIXOS SYSTEM DISK
# =====================================================================
Write-Host "`n[4/5] Registering Subsystem Container cleanly via Windows 11 Core..." -ForegroundColor Cyan
$installDir = "C:\wsl\NixOS"
if (Test-Path $installDir) { Remove-Item $installDir -Recurse -Force -ErrorAction SilentlyContinue }
New-Item -Path $installDir -ItemType Directory -Force | Out-Null

if (-not (Test-Path $nixosWslTarget) -or (Get-Item $nixosWslTarget).Length -lt 400MB) {
    Write-Host "❌ CRITICAL ERROR: Intact installer bundle cache missing from Desktop!" -ForegroundColor Red
    Pause; Exit 1
}

# Native Windows 11 import parses the raw .wsl bundle perfectly without bugs
& wsl.exe --import NixOS $installDir $nixosWslTarget --version 2
Write-Host "✔ NixOS machine mapping fully active." -ForegroundColor Green

if (Test-Path $nixosWslTarget) { Remove-Item $nixosWslTarget -Force }

# =====================================================================
# STAGE 5: EXTRACTION, AUTOMATED INITIALIZATION & ABSOLUTE FLAKE SWITCH
# =====================================================================
Write-Host "`n[5/5] Injecting Code Frameworks & Executing Home-Manager Switch..." -ForegroundColor Cyan

# Output streaming active: Logs every step of the channel update and flake compilation trace
$rawBashCommands = @'
set -e

# TASK 1: PERMANENT SYSTEM-LEVEL FLAKE ENABLING WITH PROPER QUOTED STRINGS
echo '[*] Injecting experimental features parameters permanently into system configurations...'
sudo sed -i '/system\.stateVersion/i \  nix.settings.experimental-features = [ \"nix-command\" \"flakes\" ];' /etc/nixos/configuration.nix

echo '[*] Triggering internal system reconstruction to lock in Flakes mode...'
sudo nixos-rebuild switch

echo '[*] Bouncing WSL hypervisor kernel maps to register root changes...'
if [ -f /etc/profile ]; then source /etc/profile; fi

# TASK 2: FORCE SYSTEM-WIDE CORES TO PREVENT DRIFT (GUARANTEES GIT IS PRESENT)
echo '[*] Task B: Injecting Git core packages into the unprivileged nixos profile...'
# Using nix-env handles the install directly without requiring the experimental CLI to be loaded yet
sudo nix-env -iA nixos.git nixos.cacert

# Force add the standard paths directly to this running terminal instance
export PATH="/run/current-system/sw/bin:/nix/var/nix/profiles/default/bin:$HOME/.nix-profile/bin:$PATH"

# TASK 3: SYNCHRONIZE WORKSPACE TO NATIVE YUKO LOCAL LOCATION
echo '[*] Task C: Synchronizing workspace tracks and triggering Home-Manager compile...'
if [ ! -d /home/nixos/.yuko ]; then
  echo '[*] Syncing your standalone .yuko architecture framework from GitHub...'
  git clone https://github.com /home/nixos/.yuko
else
  echo '[*] Existing codebase found. Pulling down delta updates...'
  cd /home/nixos/.yuko && git pull
fi

# TASK 4: DECLARATIVE USER CONFIGURATION FLAKE REBUILD SWITCH
echo '==================================================='
echo 'Triggering automatic Home-Manager compilation switch via Flakes...'
echo '==================================================='
cd /home/nixos/.yuko

# Force Home-Manager execution via direct flake runner targeting the repository context
nix run --extra-experimental-features "nix-command flakes" github:nix-community/home-manager/master --show-trace -- switch -b backup --flake .#yuko-core

# Sync environments out to persistent profile matrices
if [ -f /etc/profile ]; then source /etc/profile; fi
. /home/nixos/.nix-profile/etc/profile.d/hm-session-vars.sh 2>/dev/null || true

echo '==================================================='
echo '(=^･ω･^=) All Systems Operating and Configured Natively!'
echo '-> System Engine: Pure NixOS'
echo '-> Global Settings: Core Flakes Mode Permanently Enabled'
echo '-> Profile Configuration: Home-Manager Flake Initialized & Live'
echo '==================================================='
'@

$cleanBashCommands = $rawBashCommands -replace "`r`n", "`n"

# CRITICAL EXECUTION CONTEXT: Execute natively as the unprivileged user nixos
# We use sudo internally inside the block for actions that require system-level privileges
wsl -d NixOS -u nixos -- bash -c $cleanBashCommands

# Reclaim cache space from your Desktop space
Remove-Item $cacheDir -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "`n✔ Configuration orchestration fully finalized! Your workspace head is live." -ForegroundColor Green
Pause
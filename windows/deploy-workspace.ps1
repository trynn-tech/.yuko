# =====================================================================
# MASTER WORKSPACE DEPLOYMENT ORCHESTRATOR
# =====================================================================

$ScriptDir = $PSScriptRoot
if (-not $ScriptDir -and $MyInvocation.MyCommand.Path) {
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}
if (-not $ScriptDir) {
    $ScriptDir = Get-Location
}

$CurrentScript = $MyInvocation.MyCommand.Path
if (-not $CurrentScript) { $CurrentScript = $PSCommandPath }

# Elevate privilege with ExecutionPolicy Bypass set globally for the session
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "[!] Escalating privileges to Administrator..." -ForegroundColor Yellow
    if ($CurrentScript) {
        Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$CurrentScript`"" -Verb RunAs
    } else {
        Write-Error "Unable to determine script file path for elevation."
    }
    Exit
}

Set-Location -Path $ScriptDir

Write-Host "=== STARTING WORKSPACE PROVISIONING ===" -ForegroundColor Magenta

# Step 1: Provision Windows Desktop Environment
$HostDesktopScript = Join-Path $ScriptDir "setup-host-desktop.ps1"
if (Test-Path $HostDesktopScript) {
    Write-Host "`n[1/2] Executing Windows Host Desktop Setup..." -ForegroundColor Cyan
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File $HostDesktopScript
    
    # Verification check
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✔ Host Desktop Setup finished." -ForegroundColor Green
    } else {
        Write-Host "⚠ Host Desktop Setup exited with code $LASTEXITCODE." -ForegroundColor Yellow
    }
} else {
    Write-Host "`n[1/2] Skipping Host Desktop Setup (Script missing)" -ForegroundColor Yellow
}

# Step 2: Provision Virtualized NixOS WSL Environment
$InstallYukoScript = Join-Path $ScriptDir "install-yuko.ps1"
if (Test-Path $InstallYukoScript) {
    Write-Host "`n[2/2] Executing NixOS WSL Container Setup..." -ForegroundColor Cyan
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File $InstallYukoScript
    
    # Verification check
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✔ WSL Container Setup finished." -ForegroundColor Green
    } else {
        Write-Host "⚠ WSL Container Setup exited with code $LASTEXITCODE." -ForegroundColor Yellow
    }
} else {
    Write-Host "`n[2/2] Skipping WSL Container Setup (Script missing)" -ForegroundColor Yellow
}

Write-Host "`n✔ All deployment tasks completed." -ForegroundColor Green
Pause
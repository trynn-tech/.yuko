# =====================================================================
# MASTER WORKSPACE DEPLOYMENT ORCHESTRATOR
# =====================================================================
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "[!] Escalating privileges to Administrator..." -ForegroundColor Yellow
    Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    Exit
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

Write-Host "=== STARTING WORKSPACE PROVISIONING ===" -ForegroundColor Magenta

# Step 1: Provision Windows Desktop Environment
Write-Host "`n[1/2] Executing Windows Host Desktop Setup..." -ForegroundColor Cyan
& "$ScriptDir\setup-host-desktop.ps1"

# Step 2: Provision Virtualized NixOS WSL Environment
Write-Host "`n[2/2] Executing NixOS WSL Container Setup..." -ForegroundColor Cyan
& "$ScriptDir\install-yuko.ps1"

Write-Host "`n✔ All deployment steps executed successfully!" -ForegroundColor Green
Pause
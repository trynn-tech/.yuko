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
# STAGE 2: PROCESS AUTOMATED BROWSER INJECTION
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
$escapedCacheTarget = $nixosWslTarget.Replace('\', '/')

$nixosWslTarget = "$env:USERPROFILE\Desktop\nixos.wsl"
$escapedCacheTarget = $nixosWslTarget.Replace('\', '/')

# Pass the destination path safely via environment variables to bypass PowerShell here-string limits
$env:TARGET_WSL_DEST = $escapedCacheTarget

# =====================================================================
# STAGE 3: STREAM CORE IMAGE VIA PLAYWRIGHT
# =====================================================================
Write-Host "`n[3/5] Spawning Automated Browser Process to Stream Core Image Bundle..." -ForegroundColor Cyan

# Use literal single-quoted here-string; os.environ fetches the path in Python
$pythonBrowserCode = @'
import sys
import os
import multiprocessing
from playwright.sync_api import sync_playwright

def browser_task():
    print("    [*] Starting browser process virtualization hooks...")
    target_dest = os.environ.get("TARGET_WSL_DEST")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()
        
        print("    [*] Streaming NixOS core container system image bundle...")
        try:
            target_url = 'https://github.com/nix-community/NixOS-WSL/releases/download/2411.6.0/nixos.wsl'
            with page.expect_download(timeout=180000) as download_info:
                try:
                    page.goto(target_url)
                except Exception as e:
                    if "net::ERR_ABORTED" not in str(e) and "Download is starting" not in str(e):
                        raise e
            download = download_info.value
            download.save_as(target_dest)
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
'@

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
# STAGE 4: REGISTER NIXOS SYSTEM DISK
# =====================================================================
Write-Host "`n[4/5] Registering Subsystem Container cleanly via Windows 11 Core..." -ForegroundColor Cyan
$installDir = "C:\wsl\NixOS"
if (Test-Path $installDir) { Remove-Item $installDir -Recurse -Force -ErrorAction SilentlyContinue }
New-Item -Path $installDir -ItemType Directory -Force | Out-Null

if (-not (Test-Path $nixosWslTarget) -or (Get-Item $nixosWslTarget).Length -lt 100MB) {
    Write-Host "❌ CRITICAL ERROR: Intact installer bundle cache missing from Desktop!" -ForegroundColor Red
    Pause; Exit 1
}

& wsl.exe --import NixOS $installDir $nixosWslTarget --version 2
Write-Host "✔ NixOS machine mapping fully active." -ForegroundColor Green

# =====================================================================
# STAGE 5A: SYSTEM PROVISIONING (ROOT)
# =====================================================================
Write-Host "[*] Provisioning system configuration as 'root'..." -ForegroundColor Yellow

# Pure literal here-string prevents early variable resolution
$rootScript = @'
#!/usr/bin/env bash
[ -f /etc/profile ] && . /etc/profile

echo '[*] Provisioning container lab layout config...'
cat << 'LABEOF' > /etc/nixos/lab.nix
{ config, pkgs, lib, ... }:

let
  userName = "nixos";
  modelDir = "/home/${userName}/models";
  labDir = "/home/${userName}/lab/Re-L";

  runPhiMode = false;

  activeConfig = if runPhiMode then {
    name = "gpt-5";
    backend = "llama-cpp";
    parameters = {
      model = "blobs/Phi-3.5-mini-instruct-Q4_K_M.gguf";
      context_size = 8192;
      gpu_layers = -1;
      temperature = 0.2;
      f16_kv = true;
      mmap = true;
    };
  } else {
    name = "gpt-5";
    backend = "llama-cpp";
    parameters = {
      # Point to the first shard; llama.cpp automatically binds 00002-of-00002
      model = "blobs/qwen2.5-coder-7b-instruct-q5_k_m-00001-of-00002.gguf";
      context_size = 8192;
      gpu_layers = -1;
      temperature = 0.1;
      f16_kv = true;
      mmap = true;
    };
  };

  activeYaml = pkgs.writers.writeYAML "gpt-5.yaml" activeConfig;
in {
  networking.firewall.allowedTCPPorts = [ 8081 8888 ];

  environment.systemPackages = with pkgs; [
    podman-compose skopeo git python313 pipenv curl wget
  ];

  systemd.tmpfiles.rules = [
    "d ${labDir} 0755 ${userName} users -"
    "d ${modelDir} 0755 ${userName} users -"
    "d ${modelDir}/blobs 0755 ${userName} users -"
    "d ${modelDir}/configs 0755 ${userName} users -"
  ];

  systemd.services."podman-network-re-l" = {
    path = [ pkgs.podman ];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      ExecStart = "${pkgs.bash}/bin/bash -c '${pkgs.podman}/bin/podman network exists re-l-net || ${pkgs.podman}/bin/podman network create re-l-net'";
      ExecStop = "${pkgs.bash}/bin/bash -c '${pkgs.podman}/bin/podman network rm -f re-l-net'";
    };
    wantedBy = [ "multi-user.target" ];
  };

  systemd.services.provision-re-l-models = {
    description = "Declarative Model Provisioning Guard";
    path = [ pkgs.curl pkgs.wget pkgs.coreutils ];
    wantedBy = [ "multi-user.target" ];
    serviceConfig.Type = "oneshot";
    script = ''
      mkdir -p ${modelDir}/blobs
      rm -f ${modelDir}/*.yaml

      TARGET_PHI="${modelDir}/blobs/Phi-3.5-mini-instruct-Q4_K_M.gguf"
      if [ ! -s "$TARGET_PHI" ]; then
        echo "Downloading Phi-3.5-mini-instruct GGUF..."
        rm -f "$TARGET_PHI"
        curl -sSL -A "Mozilla/5.0" -o "$TARGET_PHI" "https://huggingface.co/bartowski/Phi-3.5-mini-instruct-GGUF/resolve/main/Phi-3.5-mini-instruct-Q4_K_M.gguf" || true
      fi

      SHARD1="${modelDir}/blobs/qwen2.5-coder-7b-instruct-q5_k_m-00001-of-00002.gguf"
      SHARD2="${modelDir}/blobs/qwen2.5-coder-7b-instruct-q5_k_m-00002-of-00002.gguf"

      if [ ! -s "$SHARD1" ]; then
        echo "Downloading Qwen2.5-Coder shard 1 of 2..."
        curl -sSL -A "Mozilla/5.0" -o "$SHARD1" "https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q5_k_m-00001-of-00002.gguf?download=true" || true
      fi

      if [ ! -s "$SHARD2" ]; then
        echo "Downloading Qwen2.5-Coder shard 2 of 2..."
        curl -sSL -A "Mozilla/5.0" -o "$SHARD2" "https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q5_k_m-00002-of-00002.gguf?download=true" || true
      fi

      cp -f ${activeYaml} ${modelDir}/gpt-5.yaml
      chown -R ${userName}:users ${modelDir}
      chmod -R 755 ${modelDir}
      find ${modelDir} -type f -exec chmod 644 {} +
    '';
  };

  virtualisation.oci-containers = {
    backend = "podman";
    containers = {
      "searxng" = {
        image = "docker.io/searxng/searxng:latest";
        ports = [ "8888:8080" ];
        environment = {
          SEARXNG_SETTINGS_URL = "/etc/searxng/settings.yml";
          SEARXNG_SEARCH_FORMATS = "json";
        };
        extraOptions = [ "--network=re-l-net" "--log-opt=max-size=10m" "--log-opt=max-file=2" ];
      };

      "local-ai" = {
        image = "docker.io/localai/localai:v2.25.0-cublas-cuda12";
        ports = [ "8081:8080" ];
        environment = {
          MODELS_PATH = "/models";
          DEBUG = "true";
          AUTODETECT_MODEL_CAPABILITIES = "false";
          LD_LIBRARY_PATH = "/usr/lib/wsl/lib";
        };
        volumes = [
          "${modelDir}:/models"
          "/usr/lib/wsl/lib:/usr/lib/wsl/lib:ro"
        ];
        extraOptions = [
          "--network=re-l-net"
          "--log-opt=max-size=50m"
          "--log-opt=max-file=3"
          "--device=/dev/dxg:/dev/dxg"
          "--annotation=run.oci.keep_original_groups=1"
          "--security-opt=label=disable"
          "--user=0:0"
        ];
      };
    };
  };

  systemd.services."podman-searxng".after = [ "podman-network-re-l.service" ];

  systemd.services."podman-local-ai" = {
    after = [
      "provision-re-l-models.service"
      "podman-network-re-l.service"
      "podman-searxng.service"
    ];
    requires = [
      "provision-re-l-models.service"
      "podman-network-re-l.service"
    ];
    restartTriggers = [ activeYaml ];
  };
}
LABEOF

echo '[*] Writing system configuration...'
cat << 'NIXEOF' > /etc/nixos/configuration.nix
{ config, pkgs, lib, ... }:

let
  _enableWindowsInterop = true;
in
{
  imports = [
    <nixos-wsl/modules>
    ./lab.nix
  ];

  wsl = {
    enable = true;
    defaultUser = "nixos";
    interop.includePath = _enableWindowsInterop;
    wslConf.interop.appendWindowsPath = _enableWindowsInterop;
    wslConf.automount.enabled = true;
    wslConf.automount.root = "/mnt";
    useWindowsDriver = true;
  };

  nix.settings = {
    experimental-features = [ "nix-command" "flakes" ];
    trusted-users = [ "root" "nixos" ];
  };

  nix.registry.nixpkgs.to = {
    type = "path";
    path = <nixpkgs>;
  };
  nixpkgs.config.allowUnfree = true;

  users.users.nixos = {
    isNormalUser = true;
    description = "nixos";
    group = "users";
    shell = pkgs.zsh;
    extraGroups = [ "wheel" "networkmanager" "docker" ];
  };

  environment.systemPackages = with pkgs; [ git wget curl wsl-open shadow ];

  programs.zsh.enable = true;

  programs.nix-ld.enable = true;
  environment.variables = lib.mkForce {
    NIX_LD_LIBRARY_PATH = "/usr/lib/wsl/lib/";
    NIX_LD = "${pkgs.glibc}/lib/ld-linux-x86-64.so.2";
    NIX_CURL_FLAGS = "-A NixOS/24.11";
  };

  system.stateVersion = "24.11";
}
NIXEOF

echo '[*] Enabling bootstrapped experimental features...'
mkdir -p ~/.config/nix
echo 'experimental-features = nix-command flakes' > ~/.config/nix/nix.conf

echo '[*] Configuring channel environments...'

sudo nix-channel --add https://nixos.org/channels/nixos-24.11 nixos
sudo nix-channel --add https://nixos.org/channels/nixos-24.11 nixpkgs
sudo nix-channel --add https://github.com/nix-community/NixOS-WSL/archive/refs/heads/release-24.11.tar.gz nixos-wsl
sudo nix-channel --update

# Re-run system rebuild
sudo NIX_CURL_FLAGS="-A NixOS/24.11" nixos-rebuild switch

'@

# Pipe directly into WSL safely using stdin
$rootScript | wsl -d NixOS -u root -- bash -c "tr -d '\r' | bash"

# Reboot container layer to release state
Write-Host "[*] Cycling WSL engine to release mount state..." -ForegroundColor Yellow
wsl --terminate NixOS

Write-Host "[*] Executing system rebuild..." -ForegroundColor Yellow
wsl -d NixOS -u root -- bash -lc "nixos-rebuild switch"

# =====================================================================
# STAGE 5B: WORKSPACE & HOME-MANAGER SWITCH (NIXOS USER)
# =====================================================================
Write-Host "[*] Initializing workspace & Home-Manager flake as 'nixos'..." -ForegroundColor Yellow

$userScript = @'
#!/usr/bin/env bash
[ -f /etc/profile ] && . /etc/profile

echo '[*] Setting up workspace directory...'
cd ~
rm -rf ~/.yuko

mkdir -p ~/.config/nix
echo 'experimental-features = nix-command flakes' > ~/.config/nix/nix.conf

# Clone .yuko repo using nixpkgs git runner
nix --extra-experimental-features 'nix-command flakes' run github:NixOS/nixpkgs/nixos-24.11#git -- clone https://github.com/trynn-tech/.yuko ~/.yuko

cd ~/.yuko

cat << 'ENVEOF' > .yuko-env.example.nix
{
  userName = "nixos";
  homeDir  = "/home/nixos";
}
ENVEOF

rm -f flake.lock

echo '[*] Adding temporary Git bindings...'
nix --extra-experimental-features 'nix-command flakes' run github:NixOS/nixpkgs/nixos-24.11#git -- add -f -A

echo '[*] Generating fresh evaluation lock file...'
nix --extra-experimental-features 'nix-command flakes' shell \
  github:NixOS/nixpkgs/nixos-24.11#git -c \
  nix --extra-experimental-features 'nix-command flakes' flake lock

echo '[*] Staging assets to index context...'
nix --extra-experimental-features 'nix-command flakes' run \
  github:NixOS/nixpkgs/nixos-24.11#git -- add flake.lock

echo '[*] Executing transient Home-Manager runtime switch via Flakes engine...'
nix --extra-experimental-features 'nix-command flakes' run github:nix-community/home-manager/release-24.11 -- switch -b backup --flake .#yuko-windows

echo '==================================================='
echo '(=^･-･^=) All Systems Operating and Configured Natively!'
echo '==================================================='

'@

# Strip carriage returns on execution to prevent $'\r' syntax faults
$userScript | wsl -d NixOS -u nixos -- bash -c "tr -d '\r' | bash"

# =====================================================================
# STAGE 6: WINDOWS INTEGRATION & SHORTCUT PROVISIONING
# =====================================================================
Write-Host "`n[*] Injecting Start Menu shortcuts for WSL Tmux..." -ForegroundColor Yellow

try {
    $ShortcutPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\WSL Tmux.lnk"
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = "wt.exe"
    $Shortcut.Arguments = "wsl -d NixOS -u nixos tmux new-session -A -s main"
    $Shortcut.Description = "Launch NixOS WSL Tmux Session"
    $Shortcut.WorkingDirectory = "$env:USERPROFILE"
    $Shortcut.IconLocation = "wt.exe, 0"
    $Shortcut.Save()
    Write-Host "✔ Success! 'WSL Tmux' shortcut provisioned to Start Menu." -ForegroundColor Green
} catch {
    Write-Host "⚠️ Warning: Failed to create Start Menu shortcut: $_" -ForegroundColor Yellow
}

Write-Host "`n✔ Configuration orchestration fully finalized! Your workspace head is live." -ForegroundColor Green
Pause
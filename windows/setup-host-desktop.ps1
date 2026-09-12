# =====================================================================
# HOST WINDOWS DESKTOP & TOOLCHAIN PROVISIONER
# =====================================================================
Write-Host "=== STAGING HOST WINDOWS ENVIRONMENT ===" -ForegroundColor Magenta

# --- Stage 1: Native Package Installation ---
Write-Host "`n[*] Provisioning packages via winget & scoop..." -ForegroundColor Yellow
$packages = @(
    "glaze-wm.glazewm",
    "glaze-wm.zebar",
    "Tailscale.Tailscale",
    "WinDirStat.WinDirStat",
    "Mozilla.Firefox"
)

foreach ($pkg in $packages) {
    Write-Host " -> Installing $pkg..." -ForegroundColor Cyan
    winget install --id $pkg -e --accept-package-agreements --accept-source-agreements --silent
}

if (-not (Get-Command "microwin" -ErrorAction SilentlyContinue)) {
    Write-Host " -> Installing MicroWin via Scoop..." -ForegroundColor Cyan
    if (-not (Get-Command "scoop" -ErrorAction SilentlyContinue)) {
        Invoke-RestMethod -Uri https://get.scoop.sh | Invoke-Expression
    }
    scoop bucket add extras 2>$null
    scoop install microwin
}

# --- Stage 2: Firefox Enterprise Policies & Extensions ---
Write-Host "`n[*] Configuring Firefox Enterprise Policies..." -ForegroundColor Yellow
$firefoxInstallDir = "C:\Program Files\Mozilla Firefox"
if (-not (Test-Path $firefoxInstallDir)) { $firefoxInstallDir = "C:\Program Files (x86)\Mozilla Firefox" }
$policiesDir = Join-Path $firefoxInstallDir "distribution"

if (-not (Test-Path $policiesDir)) { New-Item -ItemType Directory -Path $policiesDir -Force | Out-Null }

$policiesJson = @"
{
  "policies": {
    "ExtensionSettings": {
      "uBlock0@raymondhill.net": {
        "installation_mode": "normal_installed",
        "install_url": "https://addons.mozilla.org/firefox/downloads/latest/ublock-origin/latest.xpi"
      },
      "sponsorBlocker@ajay.app": {
        "installation_mode": "normal_installed",
        "install_url": "https://addons.mozilla.org/firefox/downloads/latest/sponsorblock/latest.xpi"
      },
      "AutoTabDiscard@rills": {
        "installation_mode": "normal_installed",
        "install_url": "https://addons.mozilla.org/firefox/downloads/latest/auto-tab-discard/latest.xpi"
      },
      "addon@darkreader.org": {
        "installation_mode": "normal_installed",
        "install_url": "https://addons.mozilla.org/firefox/downloads/latest/darkreader/latest.xpi"
      },
      "{Auto-installed-Surfingkeys}": {
        "installation_mode": "normal_installed",
        "install_url": "https://addons.mozilla.org/firefox/downloads/latest/surfingkeys_ff/latest.xpi"
      }
    },
    "DisableTelemetry": true,
    "DisableFirefoxStudies": true
  }
}
"@
Set-Content -Path (Join-Path $policiesDir "policies.json") -Value $policiesJson -Encoding UTF8
Write-Host "✔ Firefox policies.json injected." -ForegroundColor Green

# --- Stage 3: Firefox user.js Preference Injection ---
Write-Host "`n[*] Injecting translated user.js into profile..." -ForegroundColor Yellow
$ffAppData = Join-Path $env:APPDATA "Mozilla\Firefox"
$profilesIni = Join-Path $ffAppData "profiles.ini"

if (-not (Test-Path $profilesIni)) {
    Start-Process "firefox.exe" -ArgumentList "-headless" -WindowStyle Hidden
    Start-Sleep -Seconds 3
    Stop-Process -Name "firefox" -ErrorAction SilentlyContinue
}

$profileDir = Get-ChildItem -Path (Join-Path $ffAppData "Profiles") -Directory | Select-Object -First 1
if ($profileDir) {
    $userJsPath = Join-Path $profileDir.FullName "user.js"
    $userJsContent = @"
// Extracted from modules/programs/firefox/default.nix
user_pref("extensions.autoDisableScopes", 0);
user_pref("extensions.enabledScopes", 15);
user_pref("browser.contentblocking.category", "strict");
user_pref("dom.event.clipboardevents.enabled", false);
user_pref("network.IDN_show_punycode", true);
user_pref("privacy.clearOnShutdown.cache", true);
user_pref("privacy.clearOnShutdown.offlineApps", true);
user_pref("privacy.clearOnShutdown.history", false);
user_pref("browser.sessionstore.resume_from_crash", true);
user_pref("browser.sessionstore.interval", 30000);
user_pref("network.cookie.cookieBehavior", 5);
user_pref("network.cookie.lifetimePolicy", 0);
user_pref("privacy.clearOnShutdown.cookies", false);
user_pref("privacy.clearOnShutdown.sessions", false);
user_pref("privacy.sanitize.sanitizeOnShutdown", false);
user_pref("network.trr.mode", 2);
user_pref("network.http.speculative-parallel-limit", 0);
user_pref("network.dns.disablePrefetch", true);
user_pref("network.predictor.enabled", false);
user_pref("network.prefetch-next", false);
user_pref("media.peerconnection.enabled", false);
user_pref("media.peerconnection.ice.no_host", true);
user_pref("media.peerconnection.ice.default_address_only", true);
user_pref("media.peerconnection.ice.proxy_only_if_behind_proxy", true);
user_pref("privacy.trackingprotection.enabled", true);
user_pref("privacy.trackingprotection.socialtracking.enabled", true);
user_pref("privacy.trackingprotection.fingerprinting.enabled", true);
user_pref("privacy.trackingprotection.cryptomining.enabled", true);
user_pref("dom.battery.enabled", false);
user_pref("security.mixed_content.block_active_content", true);
user_pref("privacy.fingerprintingProtection", false);
user_pref("privacy.fingerprintingProtection.pbmode", false);
user_pref("browser.aboutConfig.showWarning", false);
user_pref("browser.tabs.warnOnClose", true);
user_pref("browser.newtabpage.activity-stream.showSponsored", false);
user_pref("browser.urlbar.suggest.searches", false);
user_pref("browser.newtabpage.activity-stream.feeds.section.topstories", false);
user_pref("browser.urlbar.suggest.topsites", false);
user_pref("identity.fxaccounts.enabled", false);
user_pref("signon.rememberSignons", false);
user_pref("signon.autofillForms", false);
user_pref("browser.formfill.enable", false);
user_pref("network.http.referer.XOriginPolicy", 0);
user_pref("privacy.resistFingerprinting.autoDeclineNoUserInputCanvasPrompts", false);
user_pref("image.webp.enabled", true);
user_pref("privacy.firstparty.isolate", false);
user_pref("toolkit.telemetry.archive.enabled", false);
user_pref("toolkit.telemetry.server", "data:,");
user_pref("datareporting.policy.dataSubmissionEnabled", false);
user_pref("datareporting.healthreport.service.enabled", false);
user_pref("datareporting.healthreport.uploadEnabled", false);
user_pref("toolkit.telemetry.unified", false);
user_pref("toolkit.telemetry.enabled", false);
user_pref("app.shield.optoutstudies.enabled", false);
user_pref("app.normandy.enabled", false);
user_pref("app.normandy.api_url", "");
user_pref("browser.discovery.enabled", false);
user_pref("messaging-system.rfx.remove.experiments", true);
user_pref("toolkit.telemetry.bhrPing.enabled", false);
user_pref("toolkit.telemetry.firstShutdownPing.enabled", false);
user_pref("toolkit.telemetry.newProfilePing.enabled", false);
user_pref("toolkit.telemetry.shutdownPingSender.enabled", false);
user_pref("toolkit.telemetry.updatePing.enabled", false);
user_pref("telemetry.fog.init_on_shutdown", false);
user_pref("identity.fxaccounts.telemetry.clientAssociationPing.enabled", false);
user_pref("network.trr.confirmation_telemetry_enabled", false);
user_pref("browser.newtabpage.activity-stream.feeds.telemetry", false);
user_pref("browser.newtabpage.activity-stream.telemetry", false);
user_pref("browser.search.serpEventTelemetryCategorization.enabled", false);
user_pref("browser.search.serpEventTelemetryCategorization.regionEnabled", false);
user_pref("nimbus.telemetry.targetingContextEnabled", false);
user_pref("breakpad.reportURL", "");
user_pref("browser.tabs.crashReporting.sendReport", false);
"@
    Set-Content -Path $userJsPath -Value $userJsContent -Encoding UTF8
    Write-Host "✔ Firefox preferences mapped." -ForegroundColor Green
}

# --- Stage 4: Shell Integration Context Menu ---
Write-Host "`n[*] Registering 'Edit in NixVim' context menu..." -ForegroundColor Yellow
$regPath = "HKCU:\Software\Classes\*\shell\NixVim"
New-Item -Path $regPath -Force | Out-Null
Set-ItemProperty -Path $regPath -Name "(Default)" -Value "Edit in NixVim"
Set-ItemProperty -Path $regPath -Name "Icon" -Value "wt.exe"

$cmdPath = "$regPath\command"
New-Item -Path $cmdPath -Force | Out-Null
$nixvimCmd = 'wt.exe wsl -d NixOS -u nixos zsh -c "nvim `$(wslpath ''%1'')" '
Set-ItemProperty -Path $cmdPath -Name "(Default)" -Value $nixvimCmd
Write-Host "✔ Registered context menu handler." -ForegroundColor Green
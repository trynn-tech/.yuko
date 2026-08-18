{ config, pkgs, ... }:

let
  cyberpunk-theme = pkgs.fetchurl {
    url = "https://addons.mozilla.org/firefox/downloads/file/3547285/cyberpunk_neon_rain-1.0-fx.xpi";
    sha256 = "1d6kxlfvx39994m16k668469v8m35889y5i8z3i4j0k6v7i9p3k0";
  };
in
{
  home.file.".surfingkeys.js".source = ./surfingkeys.js;

  programs.firefox = {
    enable = true;
    configPath = ".mozilla/firefox"; 

    profiles.trynn = {
      id = 0;
      name = "trynn";
      isDefault = true;
      path = "xbx65bim.default"; # Connects Home Manager to your active profile folder

      settings = {
        # --- Required for Nix-managed extensions ---
        "extensions.autoDisableScopes" = 0;
        "extensions.enabledScopes" = 15;

        # --- Security & Privacy ---
        "browser.contentblocking.category" = "strict";
        "dom.event.clipboardevents.enabled" = false;
        "network.IDN_show_punycode" = true;

        # --- Session & Cookies ---
        "network.cookie.cookieBehavior" = 5;
        "network.cookie.lifetimePolicy" = 0;
        "privacy.clearOnShutdown.cache" = true;
        "privacy.clearOnShutdown.offlineApps" = true;
        "privacy.clearOnShutdown.history" = false;
        "privacy.sanitize.sanitizeOnShutdown" = true;
        "privacy.clearOnShutdown.sessions" = false;
        "browser.sessionstore.resume_from_crash" = true;
        "browser.sessionstore.interval" = 30000;

        # --- Network & DNS ---
        "network.trr.mode" = 2;
        "network.http.speculative-parallel-limit" = 0;
        "network.dns.disablePrefetch" = true;
        "network.predictor.enabled" = false;
        "network.prefetch-next" = false;

        # --- WebRTC ---
        "media.peerconnection.enabled" = false;
        "media.peerconnection.ice.no_host" = true;
        "media.peerconnection.ice.default_address_only" = true;
        "media.peerconnection.ice.proxy_only_if_behind_proxy" = true;

        # --- Tracking & Content ---
        "privacy.trackingprotection.enabled" = true;
        "privacy.trackingprotection.socialtracking.enabled" = true;
        "privacy.trackingprotection.fingerprinting.enabled" = true;
        "privacy.trackingprotection.cryptomining.enabled" = true;
        "dom.battery.enabled" = false;
        "security.mixed_content.block_active_content" = true;
        "privacy.fingerprintingProtection" = false;
        "privacy.fingerprintingProtection.pbmode" = false;

        # --- UI & Performance ---
        "browser.aboutConfig.showWarning" = false;
        "browser.tabs.warnOnClose" = true;
        "browser.newtabpage.activity-stream.showSponsored" = false;
        "browser.urlbar.suggest.searches" = false;
        "browser.newtabpage.activity-stream.feeds.section.topstories" = false;
        "browser.urlbar.suggest.topsites" = false;
        "identity.fxaccounts.enabled" = false;

        # --- Credentials ---
        "signon.rememberSignons" = false;
        "signon.autofillForms" = false;
        "browser.formfill.enable" = false;

        # --- Media / Site Fixes ---
        "network.http.referer.XOriginPolicy" = 0;
        "privacy.resistFingerprinting.autoDeclineNoUserInputCanvasPrompts" = false;
        "image.webp.enabled" = true;
        "privacy.firstparty.isolate" = false;

	# --- TELEMETRY, EXPERIMENTS & STUDIES (COMPLETE PURGE) ---
        # Disable core telemetry & health reporting
        "toolkit.telemetry.archive.enabled" = false;
        "toolkit.telemetry.server" = "data:,"; # Redirect telemetry endpoint to empty URI
        "datareporting.policy.dataSubmissionEnabled" = false;
        "datareporting.healthreport.service.enabled" = false;

        # --- Telemetry Purge ---
        "datareporting.healthreport.uploadEnabled" = false;
        "toolkit.telemetry.unified" = false;
        "toolkit.telemetry.enabled" = false;
        "app.shield.optoutstudies.enabled" = false;
        "app.normandy.enabled" = false;
        "app.normandy.api_url" = "";
        "browser.discovery.enabled" = false;
        "messaging-system.rfx.remove.experiments" = true;

        # Disable all ping types
        "toolkit.telemetry.bhrPing.enabled" = false;
        "toolkit.telemetry.firstShutdownPing.enabled" = false;
        "toolkit.telemetry.newProfilePing.enabled" = false;
        "toolkit.telemetry.shutdownPingSender.enabled" = false;
        "toolkit.telemetry.updatePing.enabled" = false;
        "telemetry.fog.init_on_shutdown" = false;
        "identity.fxaccounts.telemetry.clientAssociationPing.enabled" = false;
        "network.trr.confirmation_telemetry_enabled" = false;

        # Disable Activity Stream, Search & SERP telemetry
        "browser.newtabpage.activity-stream.feeds.telemetry" = false;
        "browser.newtabpage.activity-stream.telemetry" = false;
        "browser.search.serpEventTelemetryCategorization.enabled" = false;
        "browser.search.serpEventTelemetryCategorization.regionEnabled" = false;

        # Disable extra tracking / diagnostic pinging
        "nimbus.telemetry.targetingContextEnabled" = false;
        "breakpad.reportURL" = ""; # Disable crash report uploads
        "browser.tabs.crashReporting.sendReport" = false;
      };

      extensions.packages = with pkgs.nur.repos.rycee.firefox-addons; [
        ublock-origin # Note: Do not mix ublock-origin and adnauseam
        sponsorblock
        auto-tab-discard
        darkreader
        surfingkeys
      ];
    };
  };
}

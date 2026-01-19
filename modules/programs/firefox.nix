# modules/programs/firefox.nix
{ config, pkgs, ... }:
let
  # This makes the theme a proper Nix derivation
  cyberpunk-theme = pkgs.fetchurl {
    url = "https://addons.mozilla.org/firefox/downloads/file/3547285/cyberpunk_neon_rain-1.0-fx.xpi";
    sha256 = "1d6kxlfvx39994m16k668469v8m35889y5i8z3i4j0k6v7i9p3k0"; # Replace with actual hash from nix-prefetch-url
  };
in
{
  programs.firefox = {
    enable = true;
    
    profiles.trynn = {
      id = 0;
      name = "trynn";
      isDefault = true;

      settings = {

        # ---  THE SECURITY CORE  ---
        "browser.contentblocking.category" = "strict";
        "dom.event.clipboardevents.enabled" = false; # Sites can't see your copy/paste buffer
        "network.IDN_show_punycode" = true; # Prevents "lookalike" domain phishing


	# --- Session & Cookies (Preserving Logins) ---
        "network.cookie.cookieBehavior" = 5; # Total Cookie Protection
        "network.cookie.lifetimePolicy" = 0; # Keep cookies until they expire
        "privacy.clearOnShutdown.cookies" = false; # Critical for keeping Google logins
        "privacy.clearOnShutdown.cache" = true;
        "privacy.clearOnShutdown.offlineApps" = true;
        "privacy.clearOnShutdown.history" = false; # Keep history for address bar flow
        "privacy.sanitize.sanitizeOnShutdown" = true;
        "privacy.clearOnShutdown.sessions" = false;    # Don't delete open tabs
        "browser.sessionstore.resume_from_crash" = true;
        "browser.sessionstore.interval" = 30000; # Save session every 30 seconds

	# --- Telemetry & Experiments  ---
        "datareporting.healthreport.uploadEnabled" = false;
        "toolkit.telemetry.unified" = false;
        "toolkit.telemetry.enabled" = false;
        "app.shield.optoutstudies.enabled" = false;
        "app.normandy.enabled" = false;
        "app.normandy.api_url" = "";
        "browser.discovery.enabled" = false;


        # --- EXTENDED TELEMETRY PURGE (User Requested) ---
        "browser.newtabpage.activity-stream.feeds.telemetry" = false;
        "browser.search.serpEventTelemetryCategorization.enabled" = false;
        "browser.search.serpEventTelemetryCategorization.regionEnabled" = false;
        "identity.fxaccounts.telemetry.clientAssociationPing.enabled" = false;
        "network.trr.confirmation_telemetry_enabled" = false;
        "nimbus.telemetry.targetingContextEnabled" = false;
        "telemetry.fog.init_on_shutdown" = false;
        "toolkit.telemetry.archive.enabled" = false;
        "toolkit.telemetry.bhrPing.enabled" = false;
        "toolkit.telemetry.firstShutdownPing.enabled" = false;
        "toolkit.telemetry.newProfilePing.enabled" = false;
        "toolkit.telemetry.shutdownPingSender.enabled" = false;
        "toolkit.telemetry.updatePing.enabled" = false;

        # --- Network & DNS (VPN Optimized) ---
        "network.trr.mode" = 2; # TRR First (DoH)
        "network.http.speculative-parallel-limit" = 0;
        "network.dns.disablePrefetch" = true;
        "network.predictor.enabled" = false;
        "network.prefetch-next" = false;
 
        # --- WebRTC (Disabled per preference) ---
        "media.peerconnection.enabled" = false; # Set to true later for digital assistant
        "media.peerconnection.ice.no_host" = true;
        "media.peerconnection.ice.default_address_only" = true;

	 # --- WebRTC (Leak Prevention) ---
        "media.peerconnection.ice.proxy_only_if_behind_proxy" = true;


        # --- Tracking & Content ---
        "privacy.trackingprotection.enabled" = true;
        "privacy.trackingprotection.socialtracking.enabled" = true;
        "privacy.trackingprotection.fingerprinting.enabled" = true;
        "privacy.trackingprotection.cryptomining.enabled" = true;
        "dom.battery.enabled" = false;
        "security.mixed_content.block_active_content" = true;
        "privacy.fingerprintingProtection" = true; 
        "privacy.fingerprintingProtection.pbmode" = true;

        # --- UI & Performance ---
        "browser.aboutConfig.showWarning" = false; # We are power users now
        "browser.tabs.warnOnClose" = true;
        "browser.newtabpage.activity-stream.showSponsored" = false;
        "browser.urlbar.suggest.searches" = false;
        "browser.newtabpage.activity-stream.feeds.section.topstories" = false;
        "browser.urlbar.suggest.topsites" = false;
        "identity.fxaccounts.enabled" = false; # Disable Firefox Sync (Modular Choice)

        # --- Credentials ---
        "signon.rememberSignons" = false; # Use external manager
        "signon.autofillForms" = false;
        "browser.formfill.enable" = false;

        # Fix #1: Allow YouTube to see where thumbnail requests come from
        "network.http.referer.XOriginPolicy" = 0; 

        # Fix #2: Relax Canvas strictness for media-heavy sites
        "privacy.resistFingerprinting.autoDeclineNoUserInputCanvasPrompts" = false;

        # Fix #3: Ensure WebP (YouTube's thumbnail format) is enabled
        "image.webp.enabled" = true;
        
        # If using 'fullHardening', this is the big one that breaks thumbnails:
        "privacy.firstparty.isolate" = false; 
      };

      extensions.packages = with pkgs.nur.repos.rycee.firefox-addons; [
        ublock-origin
        adnauseam
        sponsorblock
        surfingkeys
        auto-tab-discard
        darkreader
      ];
    };
  };
}

# modules/core.nix
{
  config,
  lib,
  pkgs,
  ...
}:

let
  inherit (lib) mkOption types;
in
{

  ########################################
  ## OPTIONS
  ########################################
  options = {
    yuko.debug = {
      manualSteps = mkOption {
        type = types.bool;
        default = true;
        description = "Whether to write manual-step hints into a log file.";
      };

      manualLogPath = mkOption {
        type = types.str;
        default = ".yuko/logs/core-debug.log";
        description = "Path under $HOME where YukoNix writes manual-step hints.";
      };

      # Implemented in `config` below
      logStep = mkOption {
        type = types.functionTo types.str;
        readOnly = true;
        description = "Helper that logs a manual step when debug/manualSteps is enabled.";
      };
    };

    yuko.security.mailLockdown = mkOption {
      type = types.bool;
      default = false;
      description = ''
        When true, IMAP sync is restricted: no folder auto-creation and
        only a minimal set of mailboxes (usually INBOX) are synced.
      '';
    };

    yuko.mail = {
      activeAccount = mkOption {
        type = types.str;
        default = "trynn-primary";
        description = "Name of the currently active mail account.";
      };

      accounts = mkOption {
        type = types.attrsOf (
          types.submodule (
            { name, ... }:
            {
              options = {
                maildirBasePath = mkOption {
                  type = types.str;
                  description = "Base Maildir path for this account.";
                };

                imapPassEntry = mkOption {
                  type = types.str;
                  description = "pass entry used for IMAP auth.";
                };

                smtpPassEntry = mkOption {
                  type = types.str;
                  description = "pass entry used for SMTP auth.";
                };
              };
            }
          )
        );
        default = { };
        description = "All Yuko mail accounts (per-account metadata).";
      };

      activeHmAccount = mkOption {
        type = types.nullOr (types.attrsOf types.anything);
        readOnly = true;
        description = "Resolved Home Manager email account for the active account, if any.";
      };

      activeAccountMeta = mkOption {
        type = types.nullOr (types.attrsOf types.anything);
        readOnly = true;
        description = "Resolved Yuko mail metadata for the active account.";
      };
    };
  };

  ########################################
  ## CONFIG (derived values + basics)
  ########################################
  config =
    let
      cfg = config.yuko.debug;

      # Local helper for manual-step logging
      logStep =
        { component, message }:
        lib.optionalString cfg.manualSteps ''
          LOG_FILE="$HOME/${cfg.manualLogPath}"
          mkdir -p "$(dirname "$LOG_FILE")"
          echo "- [${component}] ${message}" >> "$LOG_FILE"
          echo "YukoNix/manual-step [${component}]: ${message}"
        '';

      inherit (lib) attrByPath;

      active = config.yuko.mail.activeAccount;
      hmAccounts = config.accounts.email.accounts or { };
      yukoAccounts = config.yuko.mail.accounts or { };

      hmActive = attrByPath [ active ] null hmAccounts;
      yukoActive = attrByPath [ active ] null yukoAccounts;

    in
    {
      ########################################
      ## Core Home Manager basics
      ########################################
      #home.username      = config.home.username;
      #home.homeDirectory = config.home.homeDirectory;
      #home.stateVersion  = config.home.stateVersion;

      programs.home-manager.enable = true;

      ########################################
      ## Wire debug helper + init
      ########################################
      yuko.debug.logStep = logStep;

      home.activation.yukoManualStepsInit = lib.mkIf cfg.manualSteps (
        lib.hm.dag.entryBefore [ "writeBoundary" ] ''
          LOG_FILE="$HOME/${cfg.manualLogPath}"
          mkdir -p "$(dirname "$LOG_FILE")"
          : > "$LOG_FILE"
          {
            echo "# YukoNix manual steps"
            echo "# Generated: $(date)"
            echo
          } >> "$LOG_FILE"
        ''
      );

      ########################################
      ## Derived mail meta
      ########################################
      yuko.mail.activeHmAccount = hmActive;
      yuko.mail.activeAccountMeta = yukoActive;

      assertions = [
        {
          assertion = yukoActive != null;
          message =
            "yuko.mail.activeAccount is set to "
            + active
            + " but yuko.mail.accounts does not contain that key.";
        }
      ];
    };
}

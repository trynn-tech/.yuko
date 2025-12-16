# modules/core.nix
{
  config,
  lib,
  pkgs,
  ...
}:

let
  inherit (lib) mkOption types;

  # --- CRITICAL VARIABLE FOR CONDITIONAL LOGIC ---
  # Check if the current deployment is for the personal user ("trynn")
  isPersonalUser = config.home.username == "trynn";

  # Define a safe, inert default account name for non-personal users
  safeDefaultAccount = "none";
in
{

  ########################################
  ## CONFIG (derived values + basics)
  ########################################
  config =
    let
      cfg = config.yuko.debug;
      
      # Local helper for manual-step logging (unchanged)
      logStep = { component, message }: lib.optionalString cfg.manualSteps ''
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
      ## Core Home Manager basics (unchanged)
      ########################################
      programs.home-manager.enable = true;

      ########################################
      ## Wire debug helper + init (unchanged)
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

      # --- REFACTOR: CONDITIONAL ASSERTION ---
      assertions = [
        {
          # Only assert that the account exists if the active account is NOT the inert default.
          assertion = (active == safeDefaultAccount) || (yukoActive != null);
          message =
            "yuko.mail.activeAccount is set to "
            + active
            + " but yuko.mail.accounts does not contain that key. The expected user is: "
            + config.home.username;
        }
      ];
    };
}


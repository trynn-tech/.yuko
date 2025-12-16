# modules/core.nix
{ config, lib, pkgs, ... }:
let
  inherit (lib) mkOption types;
in
{
  ########################################
  ## OPTIONS (Simplified)
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
      logStep = mkOption {
        type = types.functionTo types.str;
        readOnly = true;
        description = "Helper that logs a manual step when debug/manualSteps is enabled.";
      };
    };

    yuko.mail = {
      activeAccount = mkOption {
        type = types.str;
        # Conditional Default: Disables mail for non-primary users (like 'codespace')
        default = if config.home.username == "trynn" then "trynn-primary" else "none";
        description = "Name of the currently active mail account.";
      };
      accounts = mkOption {
        type = types.attrsOf ( types.submodule ( { ... }: { options = { maildirBasePath = mkOption { type = types.str; description = "Path."; }; }; } ) );
        default = { };
        description = "All Yuko mail accounts.";
      };
      # Other mail options omitted for brevity...
    };
  };

  ########################################
  ## CONFIG (Derived values + basics)
  ########################################
  config = let
    cfg = config.yuko.debug;
    logStep = { component, message }: lib.optionalString cfg.manualSteps ''
      LOG_FILE="$HOME/${cfg.manualLogPath}"
      mkdir -p "$(dirname "$LOG_FILE")"
      echo "- [${component}] ${message}" >> "$LOG_FILE"
      echo "YukoNix/manual-step [${component}]: ${message}"
    '';
    inherit (lib) attrByPath;
    active = config.yuko.mail.activeAccount;
    yukoAccounts = config.yuko.mail.accounts or { };
  in {
    programs.home-manager.enable = true;
    yuko.debug.logStep = logStep;
    
    # Example showing how to access the PATH or other environment variables at runtime
    # This will append the current $PATH to a file during activation:
    home.activation.logPath = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      echo "Runtime PATH: $PATH" >> "$HOME/.yuko/logs/runtime-path.log"
    '';

    # No assertions block here.
  };
}


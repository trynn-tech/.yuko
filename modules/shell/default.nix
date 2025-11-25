# modules/shell/default.nix
{ config, lib, pkgs, ... }:

let
  cfg     = config.yuko.shell;
  logStep = config.yuko.debug.logStep;
in {
  options.yuko.shell.default = lib.mkOption {
    type = lib.types.bool;
    default = false;
    description = ''
      If true, configure zsh and attempt to set /usr/bin/zsh as the login shell.
      Fails gracefully and never aborts activation.
    '';
  };

  config =
    {
      programs.zsh = {
        enable = true;
        enableCompletion = true;
        autosuggestions.enable = true;
        syntaxHighlighting.enable = true;

      # Make sure Nix environment is available in zsh
      initExtra = ''
        # If the multi-user Nix profile script exists, source it
        if [ -e "/nix/var/nix/profiles/per-user/$USER/profile/etc/profile.d/nix.sh" ]; then
          . "/nix/var/nix/profiles/per-user/$USER/profile/etc/profile.d/nix.sh"
        else
          # Fallback: make sure common Nix paths are on PATH
          export PATH="$HOME/.nix-profile/bin:/nix/var/nix/profiles/per-user/$USER/profile/bin:/nix/var/nix/profiles/default/bin:$PATH"
        fi
      '';
      };
    }// lib.mkIf cfg.default {
      home.activation.setDefaultShell =
        lib.hm.dag.entryAfter [ "writeBoundary" ] ''
          (
            set +e

            TARGET_SHELL="/usr/bin/zsh"
            CHSH="/usr/bin/chsh"

            if [ ! -x "$TARGET_SHELL" ]; then
              echo "Home Manager: $TARGET_SHELL not found; skipping login shell change."
              echo "  Install zsh via your system package manager (e.g. 'sudo apt install zsh')."
              ${logStep {
                component = "shell";
                message   = "Install zsh (e.g. 'sudo apt install zsh') so YukoNix can set it as login shell.";
              }}
              exit 0
            fi

            if [ ! -x "$CHSH" ]; then
              echo "Home Manager: $CHSH not found; cannot change login shell automatically."
              echo "  You can manually run:  chsh -s $TARGET_SHELL"
              ${logStep {
                component = "shell";
                message   = "Install 'chsh' or run 'chsh -s /usr/bin/zsh' manually to change login shell.";
              }}
              exit 0
            fi

            if [ "$SHELL" = "$TARGET_SHELL" ]; then
              echo "Home Manager: login shell already $TARGET_SHELL; nothing to do."
              exit 0
            fi

            echo "Home Manager: attempting to set login shell to $TARGET_SHELL"
            if "$CHSH" -s "$TARGET_SHELL"; then
              echo "Home Manager: login shell updated to $TARGET_SHELL"
              echo "  This will take effect for new terminals/logins; existing sessions remain unchanged."
              ${logStep {
                component = "shell";
                message   = "Login shell changed to /usr/bin/zsh. Open a new terminal/tmux session to use it.";
              }}
            else
              echo "Home Manager: could not change login shell (permissions or policy)."
              echo "  Your current shell ($SHELL) remains active."
              echo "  If you still want zsh as login shell, try manually:"
              echo "    chsh -s $TARGET_SHELL"
              ${logStep {
                component = "shell";
                message   = "Login shell change failed. Try 'chsh -s /usr/bin/zsh' manually if desired.";
              }}
            fi

            exit 0
          )
        '';
    };
}

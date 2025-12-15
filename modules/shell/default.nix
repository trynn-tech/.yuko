# modules/shell/default.nix
{
  config,
  lib,
  pkgs,
  ...
}:

let
  inherit (config.yuko.debug) logStep;

  # Option definition is now in the submodule, but the default shell setting remains here
  cfg = {
    inherit (config.yuko.shell) default;
  };

in
{

  # 1. Import the Zsh submodule
  imports = [
    ./zsh
    ./tmux
  ];

  # 2. Options for the overall shell setup (can be simplified if all options move to submodules)
  options.yuko.shell.default = lib.mkOption {
    type = lib.types.bool;
    default = false;
    description = "Optionally attempts to set the login shell to Zsh managed by Nix.";
  };

  # 3. Config block primarily handles the activation for setting the default shell
  config = {

    # Automatically enable the zsh configuration when the default shell option is requested.
    yuko.shell.zsh.enable = lib.mkDefault cfg.default;

    # 4. Activation for setting the default shell (Zsh)
    # The default shell setting remains here because it's an action performed
    # outside of the Zsh configuration itself.

    home.activation.setDefaultShell = lib.mkIf cfg.default (
      lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        (
          set +e
          # Use the shell installed by Home Manager/Nix (Zsh is now in home.packages)
          TARGET_SHELL="${pkgs.zsh}/bin/zsh"
          CHSH="$(command -v chsh || true)"

          if [ -z "$CHSH" ]; then
            echo "Home Manager: 'chsh' not available; cannot set login shell automatically."
            ${logStep {
              component = "shell";
              message = "'chsh' missing, login shell unchanged.";
            }}
            exit 0
          fi

          if [ "$SHELL" = "$TARGET_SHELL" ]; then
            echo "Home Manager: login shell already $TARGET_SHELL"
            exit 0
          fi

          echo "Home Manager: attempting to set login shell to $TARGET_SHELL"
          if $CHSH -s "$TARGET_SHELL"; then
            echo "Home Manager: login shell changed to $TARGET_SHELL."
            ${logStep {
              component = "shell";
              message = "Login shell updated to Nix zsh.";
            }}
          else
            echo "Home Manager: login shell change failed (permissions or policy)."
            ${logStep {
              component = "shell";
              message = "Login shell change failed.";
            }}
          fi
          exit 0
        )
      ''
    );
  };
}

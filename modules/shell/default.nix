# modules/shell/default.nix
{ config, lib, pkgs, ... }:

let
  cfg = config.yuko.shell;
in
{
  imports = [
    ./zsh
    ./tmux
    ./ledger.nix
  ];

  options.yuko.shell.default = lib.mkOption {
    type = lib.types.bool;
    default = false;
    description = "Enables the core Zsh environment and Ledger CLI.";
  };

  config = {
    # Distribute the 'default' toggle to submodules
    yuko.shell.zsh.enable = lib.mkDefault cfg.default;
    yuko.shell.ledger.enable = lib.mkDefault cfg.default;

    # Set Zsh as the login shell if 'default' is true
    home.activation.setDefaultShell = lib.mkIf cfg.default (
      lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        (
          set +e
          TARGET_SHELL="${pkgs.zsh}/bin/zsh"
          CHSH="$(command -v chsh || true)"
          
          if [ -z "$CHSH" ]; then
            echo "Home Manager: 'chsh' not available."
            exit 0
          fi

          if [ "$SHELL" != "$TARGET_SHELL" ]; then
            echo "Home Manager: updating login shell to $TARGET_SHELL"
            if $CHSH -s "$TARGET_SHELL"; then
              echo "Login shell updated to Nix zsh."
            else
              echo "Login shell update failed."
            fi
          fi
        )
      ''
    );

    # Essential system utility packages housed directly in core
    home.packages = with pkgs; [
      alacritty      
      curl
      tree
      vim
      ripgrep
      fd
      fzf
      pass
    ];

  };
}

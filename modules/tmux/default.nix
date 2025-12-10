{ config, lib, pkgs, ... }:

{
  programs.tmux = {
    enable = true;

    # Use Nix zsh as tmux's shell (note: string, not derivation)
    shell = "${pkgs.zsh}/bin/zsh";

    terminal = "screen-256color";
    mouse = true;
    keyMode = "vi";
    historyLimit = 100000;
    clock24 = true;

    extraConfig = ''
      # Start window & pane indexing at 1
      set-option -g base-index 1
      set-window-option -g pane-base-index 1

      # Split shortcuts
      bind | split-window -h
      bind - split-window -v

      # Reload config
      bind r source-file ~/.tmux.conf \; display-message "tmux config reloaded"

      # Vim-style copy mode
      setw -g mode-keys vi
    '';
  };

  xdg.configFile."tmux/tmux.conf".force = true;
}

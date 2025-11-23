{ config, lib, pkgs, ... }:

{
  programs.tmux = {
    enable = true;

    # Good defaults
    terminal = "screen-256color";
    mouse = true;
    keyMode = "vi";
    historyLimit = 100000;
    clock24 = true;

    # Make sure tmux uses zsh explicitly, even if something upstream is weird
    extraConfig = ''
      # Use zsh as the default shell inside tmux
      set-option -g default-shell /usr/bin/zsh

      # Start window & pane numbering at 1 (more human-friendly)
      set-option -g base-index 1
      set-window-option -g pane-base-index 1

      # Easier split shortcuts (Prefix + |, Prefix + -)
      bind | split-window -h
      bind - split-window -v

      # Reload tmux config: Prefix + r
      bind r source-file ~/.tmux.conf \; display-message "tmux config reloaded"

      # Make copy-mode feel more vimmy
      setw -g mode-keys vi
    '';
  };
}

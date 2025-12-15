# modules/tmux/default.nix
{ config, lib, pkgs, ... }:

{
  # --- TMUX CORE CONFIG -------------------------------------
  programs.tmux = {
    enable = true;

    shell = "${pkgs.zsh}/bin/zsh";
    terminal = "tmux-256color"; 
    mouse = true;
    keyMode = "vi";
    historyLimit = 100000;
    clock24 = true;

    # --- TMUX PLUGINS ----------------------------------------
    plugins = with pkgs.tmuxPlugins; [
      sensible
      yank
      resurrect
      {
        plugin = continuum;
        extraConfig = ''
          set -g @continuum-restore 'on'
          set -g @continuum-save-interval '5'
          
          # Remove C-s keybind from Continuum extraConfig to avoid conflict
        '';
      }
    ];

    # --- TMUX CONFIG -----------------------------------------
    extraConfig = ''
      # FIX: Ensure Tmux uses the correct terminfo
      set -g default-terminal "tmux-256color"
      
      # --- PREFIX -------------------------------------------
      set -g prefix C-b
      unbind C-b
      bind C-b send-prefix

      # --- INDEXING ------------------------------------------
      set -g base-index 1
      setw -g pane-base-index 1

      # --- SPLITS --------------------------------------------
      bind | split-window -h
      bind - split-window -v

      # --- COPY MODE -----------------------------------------
      setw -g mode-keys vi

      # --- RELOAD CONFIG -------------------------------------
      bind r source-file ~/.config/tmux/tmux.conf \; display-message "tmux reloaded"

      # --- RESURRECT / CONTINUUM ------------------------------
      set -g @resurrect-dir ~/.tmux/resurrect

      # CRITICAL FIX: Prevent nested shells (double prompt)
      set -g @resurrect-shells 'false'

      # Restore Neovim cleanly
      set -g @resurrect-processes 'nvim'
      set -g @resurrect-command-nvim 'nvim'
      
      # Manual save binding uses a custom shim to guarantee execution (Fixes 127 error)
      bind S run-shell "tmux-continuum-save"

      # --- SESSIONIZER ---------------------------------------
      bind f run-shell "tmux-sessionizer"
    '';
  };

  # --- ENSURE RESURRECT DIRECTORY EXISTS ---------------------
  home.activation.ensureTmuxResurrectDir =
    lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      mkdir -p "$HOME/.tmux/resurrect"
    '';

  # --- USER BINARIES ----------------------------------------
  home.packages = with pkgs; [
    tmux
    fzf
    coreutils

    # --- CONTINUUM SAVE SHIM (FIXES 127 ERROR) ---------------
    (pkgs.writeShellScriptBin "tmux-continuum-save" ''
      #!/usr/bin/env bash
      # Use absolute paths for all execution to overcome minimal Tmux environment PATH issues
      set -euo pipefail
      
      # Execute the Continuum save script via an absolute path
      ${pkgs.tmux}/bin/tmux run-shell \
        "${pkgs.tmuxPlugins.continuum}/scripts/save.sh"
    '')

    # --- TMUX SESSIONIZER (FZF FIXED) ------------------------
    (pkgs.writeShellScriptBin "tmux-sessionizer" ''
      #!/usr/bin/env bash
      set -u

      SEARCH_DIRS=("$HOME/dev" "$HOME")

      if ! selected=$(find "''${SEARCH_DIRS[@]}" \
        -mindepth 1 -maxdepth 2 -type d 2>/dev/null | fzf); then
        exit 0
      fi

      [ -z "$selected" ] && exit 0

      session=$(basename "$selected" | tr . _)

      tmux has-session -t "$session" 2>/dev/null || \
        tmux new-session -d -s "$session" -c "$selected"

      tmux switch-client -t "$session"
    '')
  ];

  # --- FORCE TMUX CONF OWNERSHIP -----------------------------
  xdg.configFile."tmux/tmux.conf".force = true;

  # --- ENSURE TMUX ALWAYS LOADS CONFIG -----------------------
  home.file.".tmux.conf".source =
    config.lib.file.mkOutOfStoreSymlink
      "${config.xdg.configHome}/tmux/tmux.conf";
}

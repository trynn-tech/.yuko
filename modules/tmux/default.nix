# modules/tmux/default.nix

{config, lib, pkgs, ...}: {
  programs.tmux = {
    enable = true;
    shell = "${pkgs.zsh}/bin/zsh";
    terminal = "screen-256color";
    mouse = true;
    keyMode = "vi";
    historyLimit = 100000;
    clock24 = true;
    
    extraConfig = ''
      # Force Tmux to use vi keys natively in copy mode
      setw -g mode-keys vi

      # Start window & pane indexing at 1
      set-option -g base-index 1
      set-window-option -g pane-base-index 1

      # Split shortcuts
      bind | split-window -h
      bind - split-window -v

      # Reload config
      bind r source-file ~/.tmux.conf \; display-message "tmux config reloaded"

      # Vim-style copy mode bindings
      # Unbind default keys first to prevent conflicts
      unbind-key -T copy-mode-vi v
      unbind-key -T copy-mode-vi y

      # Bind v to begin selection (highlighting)
      bind-key -T copy-mode-vi v send-keys -X begin-selection
      
      # Bind y to copy using your secure local system tools
      bind-key -T copy-mode-vi y send-keys -X copy-pipe-and-cancel "${pkgs.wl-clipboard}/bin/wl-copy || ${pkgs.xclip}/bin/xclip -selection clipboard -in"
    '';
  };
}


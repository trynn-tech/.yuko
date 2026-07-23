# modules/tmux/default.nix
{ config, lib, pkgs, ... }: {
  # Explicitly symlink ~/.tmux.conf to Home Manager's generated configuration path
  home.file.".tmux.conf".source = config.lib.file.mkOutOfStoreSymlink "${config.home.homeDirectory}/.config/tmux/tmux.conf";

  programs.tmux = {
    enable = true;
    shell = "${pkgs.zsh}/bin/zsh";
    # Upgrade terminal to xterm-256color to fully support advanced color definitions
    terminal = "xterm-256color";
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

      # Reload config with visual debug output
      bind r source-file ~/.tmux.conf \; display-message "🔥 YUKO TMUX CONFIG RELOADED SUCCESSFULLY! 🔥"

      # =====================================================================
      # THEME & STATUS BAR STYLING (Neon Violet, Mellow Teal, Emerald)
      # =====================================================================
      set-option -g status-style "bg=default,fg=white"

      # Window list styling
      set-window-option -g window-status-style "fg=cyan,bg=default"
      set-window-option -g window-status-current-style "fg=magenta,bg=default,bold"
      set-window-option -g window-status-format " #I:#W "
      set-window-option -g window-status-current-format " [#I:#W] "

      # Status right styling with explicit hex/color attributes
      # Neon Violet (#af87ff / colour141) for Active, Mellow Teal (#5fafaf / colour73) separators, and Emerald (#00af87 / colour36) for Inbox
      set-option -g status-right-length 120
      set-option -g status-right "#[fg=#af87ff,bold]Active: #(task +ACTIVE status:pending count 2>/dev/null || echo '0') #[fg=#5fafaf]|#[default] #[fg=#00af87,bold]Inbox: #(task +inbox status:pending count 2>/dev/null || echo '0') "

      # =====================================================================
      # ERGONOMIC BINDINGS FOR COPY MODE & PROMPT JUMPING
      # =====================================================================
      bind-key -n M-Space copy-mode

      # =====================================================================
      # MOUSE HOVER SELECTION & AUTOMATIC COPY
      # =====================================================================
      bind-key -T copy-mode-vi MouseDragEnd1Pane send-keys -X copy-pipe-and-cancel "sh -c '${pkgs.wl-clipboard}/bin/wl-copy 2>/dev/null || ${pkgs.xclip}/bin/xclip -selection clipboard -in'"

      # =====================================================================
      # VIM-STYLE KEYBOARD COPY MODE BINDINGS
      # =====================================================================
      unbind-key -T copy-mode-vi v
      unbind-key -T copy-mode-vi y

      # Bind v to begin selection (highlighting)
      bind-key -T copy-mode-vi v send-keys -X begin-selection

      # Bind y to copy using secure local system tools
      bind-key -T copy-mode-vi y send-keys -X copy-pipe-and-cancel "sh -c '${pkgs.wl-clipboard}/bin/wl-copy 2>/dev/null || ${pkgs.xclip}/bin/xclip -selection clipboard -in'"

      # Use Ctrl + j inside copy-mode to instantly jump backward to your prompt signature (❯ )
      bind-key -T copy-mode-vi C-j send-keys -X search-backward "❯ "
    '';
  };
}

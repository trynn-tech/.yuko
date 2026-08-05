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

      # Status left styling with explicit hex/color attributes
      set-option -g status-left "#[fg=#af87ff,bold] #S #[default]"

      # Styles the active window text (e.g., [1:nvim])
      set -g window-status-current-format "#[fg=#00af87,bold][#I]"
      
      # Styles the inactive windows (optional, sets them to a muted gray)
      set -g window-status-format "#[fg=#6e6a86][#I]"

      # Status right styling with explicit hex/color attributes
      # Active (Neon Violet #af87ff), Inbox (Emerald #00af87), Separators (Mellow Teal #5fafaf)
      # Unsorted: Calm Cobalt (#5f87d7) if 1-7, Calm Coral (#d78787) if >7, hidden if 0
      set-option -g status-right-length 150
      set-option -g status-right "#[fg=#af87ff,bold]Active: #(task +ACTIVE status:pending count 2>/dev/null || echo '0') #[fg=#5fafaf]|#[default] #[fg=#00af87,bold]Inbox: #(task +inbox status:pending count 2>/dev/null || echo '0')#(task +inbox priority: status:pending count 2>/dev/null | awk '\$1 > 7 {print \" #[fg=#5fafaf]|#[default] #[fg=#d78787,bold]Unsorted: \" \$1} \$1 > 0 && \$1 <= 7 {print \" #[fg=#5fafaf]|#[default] #[fg=#5f87d7,bold]Unsorted: \" \$1}') "

      # =====================================================================
      # ERGONOMIC BINDINGS FOR COPY MODE & PROMPT JUMPING
      # =====================================================================
      bind-key -n C-j copy-mode

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
      bind-key -T copy-mode-vi C-k send-keys -X search-backward "❯ "

      # Kill the session automatically when the client detaches
      set -g destroy-unattached on
    '';
  };
}

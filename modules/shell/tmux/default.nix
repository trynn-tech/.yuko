# modules/tmux/default.nix
{ config, lib, pkgs, ... }: {

  programs.tmux = {
    enable = true;
    shell = "${pkgs.zsh}/bin/zsh";
    prefix = "C-Space";
    terminal = "xterm-256color";
    mouse = true;
    keyMode = "vi";
    historyLimit = 100000;
    clock24 = true;
    plugins = with pkgs.tmuxPlugins; [
      vim-tmux-navigator
    ];
    extraConfig = ''
      # Force Tmux to use vi keys natively in copy mode
      setw -g mode-keys vi

      # Start window & pane indexing at 1
      set-option -g base-index 1
      set-window-option -g pane-base-index 1

      # Split shortcuts
      bind b split-window -h
      bind u split-window -v

      # Reload config with visual debug output
      bind r source-file ~/.config/tmux/tmux.conf \; display-message "🔥 YUKO TMUX CONFIG RELOADED SUCCESSFULLY! 🔥"

      # =====================================================================
      # VIM PANE RESIZING & CLEAR SCREEN OVERRIDE
      # =====================================================================
      bind -r H resize-pane -L 5
      bind -r J resize-pane -D 5
      bind -r K resize-pane -U 5
      bind -r L resize-pane -R 5

      # Clear screen override
      bind-key -n C-x send-keys C-l

      # =====================================================================
      # THEME & STATUS BAR STYLING (Neon Violet, Mellow Teal, Emerald)
      # =====================================================================
      set-option -g status-style "bg=default,fg=white"

      set-window-option -g window-status-style "fg=cyan,bg=default"
      set-window-option -g window-status-current-style "fg=magenta,bg=default,bold"
      set-window-option -g window-status-format " #I:#W "
      set-window-option -g window-status-current-format " [#I:#W] "

      set-option -g status-left "#[fg=#af87ff,bold] #S #[default]"
      set -g window-status-current-format "#[fg=#00af87,bold][#I]"
      set -g window-status-format "#[fg=#6e6a86][#I]"

      # Status right styling with Taskwarrior counts
      set-option -g status-right-length 150
      set-option -g status-right "#[fg=#af87ff,bold]Active: #(task +ACTIVE status:pending count 2>/dev/null || echo '0') #[fg=#5fafaf]|#[default] #[fg=#00af87,bold]Inbox: #(task +inbox status:pending count 2>/dev/null || echo '0')#(task +inbox priority: status:pending count 2>/dev/null | awk '\$1 > 7 {print \" #[fg=#5fafaf]|#[default] #[fg=#d78787,bold]Unsorted: \" \$1} \$1 > 0 && \$1 <= 7 {print \" #[fg=#5fafaf]|#[default] #[fg=#5f87d7,bold]Unsorted: \" \$1}') "

      # =====================================================================
      # ERGONOMIC BINDINGS FOR COPY MODE & PROMPT JUMPING
      # =====================================================================
      bind-key -n C-f copy-mode

      # Mouse hover selection & automatic copy
      bind-key -T copy-mode-vi MouseDragEnd1Pane send-keys -X copy-pipe-and-cancel "sh -c '${pkgs.wl-clipboard}/bin/wl-copy 2>/dev/null || ${pkgs.xclip}/bin/xclip -selection clipboard -in'"

      # Vim-style keyboard copy mode bindings
      unbind-key -T copy-mode-vi v
      unbind-key -T copy-mode-vi y
      bind-key -T copy-mode-vi v send-keys -X begin-selection
      bind-key -T copy-mode-vi y send-keys -X copy-pipe-and-cancel "sh -c '${pkgs.wl-clipboard}/bin/wl-copy 2>/dev/null || ${pkgs.xclip}/bin/xclip -selection clipboard -in'"

      # Jump backward to prompt signature
      bind-key -T copy-mode-vi C-k send-keys -X search-backward "❯ "
    '';
  };
}

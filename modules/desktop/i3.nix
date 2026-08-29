# modules/desktop/i3.nix
{ config, lib, pkgs, ... }:

with lib;

let
  cfg = config.myDesktop;
  arandrScript = ./assets/default.sh;
  vlcStartupDir = "~/Music";
  statusSongFile = "${config.home.homeDirectory}/.cache/mpv-current-song";
in {
  options.myDesktop.wallpaper = mkOption {
    type = types.path;
    default = ./assets/wallpaper.webp;
  };

  config = {
    home.packages = [
      pkgs.arandr
      pkgs.kdePackages.kdeconnect-kde
      pkgs.procps # provides killall for i3status refreshes
      pkgs.vicinae
      pkgs.i3lock
      pkgs.xdotool
    ];

    xsession.windowManager.i3 = {
      enable = true;
      config = {
        modifier = "Mod4";
        terminal = "alacritty";
        window = {
          border = 2;
          titlebar = false;
        };
        floating = {
          border = 2;
          titlebar = false;
        };
        # Neon Violet Accent Colors for Window Borders (Active orientation highlight)
        colors = {
          focused = {
            border = "#bd00ff";
            background = "#282a36";
            text = "#ffffff";
            indicator = "#bd00ff";
            childBorder = "#bd00ff";
          };
          unfocused = {
            border = "#444444";
            background = "#222222";
            text = "#888888";
            indicator = "#222222";
            childBorder = "#444444";
          };
          focusedInactive = {
            border = "#666666";
            background = "#222222";
            text = "#ffffff";
            indicator = "#666666";
            childBorder = "#666666";
          };
        };
        # Define the Resize Mode block
        modes = {
          resize = {
            # Vim-style directional resizing
            "h" = "resize shrink width 10 px or 10 ppt";
            "j" = "resize grow height 10 px or 10 ppt";
            "k" = "resize shrink height 10 px or 10 ppt";
            "l" = "resize grow width 10 px or 10 ppt";
            # Arrow keys alternative
            "Left"  = "resize shrink width 10 px or 10 ppt";
            "Down"  = "resize grow height 10 px or 10 ppt";
            "Up"    = "resize shrink height 10 px or 10 ppt";
            "Right" = "resize grow width 10 px or 10 ppt";
            # Exit resize mode back to default state
            "Return" = "mode \"default\"";
            "Escape" = "mode \"default\"";
            "Mod4+r" = "mode \"default\"";
          };
        };
        keybindings = lib.mkOptionDefault {
          "Mod4+1" = "workspace 1";
          "Mod4+2" = "workspace 2";
          "Mod4+3" = "workspace 3";
          "Mod4+4" = "workspace 4";
          "Mod4+5" = "workspace 5";
          "Mod4+6" = "workspace 6";
          "Mod4+7" = "workspace 7";
          "Mod4+8" = "workspace 8";
          "Mod4+9" = "workspace 9";
          "Mod4+0" = "workspace 10";
          "Mod4+Shift+1" = "move container to workspace 1";
          "Mod4+Shift+2" = "move container to workspace 2";
          "Mod4+Shift+3" = "move container to workspace 3";
          "Mod4+Shift+4" = "move container to workspace 4";
          "Mod4+Shift+5" = "move container to workspace 5";
          "Mod4+Shift+6" = "move container to workspace 6";
          "Mod4+Shift+7" = "move container to workspace 7";
          "Mod4+Shift+8" = "move container to workspace 8";
          "Mod4+Shift+9" = "move container to workspace 9";
          "Mod4+Shift+0" = "move container to workspace 10";
          "Mod4+Control+Left"  = "focus output left";
          "Mod4+Control+Right" = "focus output right";
          "Mod4+Control+Up"    = "focus output up";
          "Mod4+Control+Down"  = "focus output down";
          "Mod4+Shift+Left"    = "move output left";
          "Mod4+Shift+Right"   = "move output right";
          # Vim-style focus keybindings
          "Mod4+h" = "focus left";
          "Mod4+j" = "focus down";
          "Mod4+k" = "focus up";
          "Mod4+l" = "focus right";
          # Vim-style move keybindings
          "Mod4+Shift+h" = "move left";
          "Mod4+Shift+j" = "move down";
          "Mod4+Shift+k" = "move up";
          "Mod4+Shift+l" = "move right";
          # Custom Pane Movements for working with two screens and nested panes
          "Mod4+f" = "workspace 2"; # Terminal Work
          "Mod4+g" = "workspace 10"; # Internet Browser
          "Mod4+n" = "workspace 9"; # Aux often Music
          "Mod4+Tab" = "workspace next";
          "Mod4+Shift+Tab" = "workspace prev";
          # Split orientation bindings
          "Mod4+v" = "split v"; # Split vertically (top/bottom)
          "Mod4+c" = "split h"; # Split horizontally (left/right)
          # Enter Resize Mode
          "Mod4+r" = "mode \"resize\"";
          # Layout controls
          "Mod4+w" = "layout tabbed";
          "Mod4+e" = "layout toggle split";
          "Mod4+a" = "focus parent";
          # Gamer Mode Toggle - pane focus indicator toggle
          "Mod4+|" = "exec --no-startup-id i3-msg '[con_id=\"__focused__\"] border toggle'";
          "Mod4+d" = "exec --no-startup-id ${pkgs.vicinae}/bin/vicinae toggle";
          "Mod4+x" = "exec --no-startup-id \"i3-msg 'split h; exec alacritty -e yazi'\"";
          "Mod4+t" = "exec --no-startup-id \"i3-msg 'split h; exec alacritty --class split_term,split_term'\"";
          "Mod4+Return" = "exec alacritty";
          "Mod4+Shift+w" = "exec alacritty -e nvim +VimwikiIndex";
          "Mod4+Shift+q" = "kill";
          "Mod4+Shift+i" = "exec firefox";
          # Instantly reload arandr layout/tv setup hotkey
          "Mod4+F12" = "exec --no-startup-id ${arandrScript}";
          # Screen Lock Binding (Uses custom wallpaper color matching or standard fill)
          "Mod4+Control+l" = "exec --no-startup-id ${pkgs.i3lock}/bin/i3lock -c 0a0612";
          # Media Controls
          "Mod4+o" = "exec --no-startup-id pactl set-sink-mute @DEFAULT_SINK@ toggle";
          "Mod4+p" = "exec playerctl -a play-pause";
          "Mod4+space" = "exec --no-startup-id playerctl --player=mpv play-pause";
          "Mod4+BackSpace" = "exec --no-startup-id playerctl --player=firefox play-pause";
          "Mod4+grave" = "exec --no-startup-id playerctl previous";
          "Mod4+q" = "exec --no-startup-id playerctl next";
          "Mod4+minus" = "exec --no-startup-id pactl set-sink-volume @DEFAULT_SINK@ -5%";
          "Mod4+equal" = "exec --no-startup-id pactl set-sink-volume @DEFAULT_SINK@ +5%";

	  # Text Expanding Shortcuts via Clipboard Buffer
	   "Mod4+b" = "exec --no-startup-id bash -c 'sleep 0.15 && ${pkgs.xdotool}/bin/xdotool type --clearmodifiers -- \"\\`\\`\\`\"'";

	  "Mod4+z" = "exec --no-startup-id bash -c 'sleep 0.15 && ${pkgs.xdotool}/bin/xdotool type --clearmodifiers -- \"\\`\\`\\`bash\"'";
	  "Mod4+Shift+n" = "exec --no-startup-id bash -c 'sleep 0.15 && ${pkgs.xdotool}/bin/xdotool type --clearmodifiers -- \"\\`\\`\\`nix\"'";
	  "Mod4+Shift+m" = "exec --no-startup-id bash -c 'sleep 0.15 && ${pkgs.xdotool}/bin/xdotool type --clearmodifiers -- \"\\`\\`\\`python\"'";
          
          # Emit =^-.-^= instantly at cursor
          "Mod4+i" = "exec --no-startup-id bash -c 'sleep 0.15 && xdotool type --clearmodifiers -- \"=^-.-^=\"'";

        };
        workspaceOutputAssign = [
          { workspace = "1"; output = "HDMI-0"; }
          { workspace = "2"; output = "HDMI-0"; }
          { workspace = "3"; output = "HDMI-0"; }
          { workspace = "4"; output = "HDMI-0"; }
          { workspace = "5"; output = "HDMI-0"; }
          { workspace = "6"; output = "HDMI-1-2"; }
          { workspace = "7"; output = "HDMI-1-2"; }
          { workspace = "8"; output = "HDMI-1-2"; }
          { workspace = "9"; output = "HDMI-1-2"; }
          { workspace = "10"; output = "HDMI-1-2"; }
        ];
        assigns = {
          "1" = [ { class = "Firefox"; } ];
          "5" = [ { class = "KDE Connect Indicator"; } ];
        };
        startup = [
          # Import X11 display environment variables so background user systemd services (AutoKey) succeed
          { command = "systemctl --user import-environment DISPLAY XAUTHORITY"; notification = false; }
          { command = "${arandrScript}"; notification = false; }
          { command = "${pkgs.feh}/bin/feh --bg-max ${cfg.wallpaper}"; always = true; notification = false; }
          { command = "xsetroot -cursor_name left_ptr"; always = true; notification = false; }
          { command = "${pkgs.copyq}/bin/copyq"; notification = false; }
          {
            command = "while true; do nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits > /tmp/gpu_vram; sleep 5; done";
            always = true;
            notification = false;
          }
          # Start background track daemon alongside i3 startup
          { command = "${config.home.homeDirectory}/.local/bin/mpv-status-daemon"; notification = false; }
          # Desktop command pallete
          { command = "${pkgs.vicinae}/bin/vicinae server"; notification = false; }
          # 1. Start background terminal on workspace 2 first
          { command = "i3-msg 'workspace 2; exec alacritty'"; notification = false; }
          # 2. Start Firefox last and land focus cleanly on workspace 1
          { command = "i3-msg 'workspace 1; exec firefox'"; notification = false; }
          { command = "kdeconnect-indicator"; notification = false; }
        ];
        bars = [
          {
            position = "bottom";
            statusCommand = "${pkgs.i3status}/bin/i3status";
          }
        ];
      };
      extraConfig = ''
        default_border pixel 2
        default_floating_border pixel 2
        hide_edge_borders smart
        # Automatically make Firefox fullscreen on workspace 1
        for_window [workspace="1" class="Firefox"] fullscreen enable
        # Trigger resize automatically as soon as the window maps to X11
        for_window [class="split_term"] resize set width 20 ppt
      '';
    };
    home.file.".config/i3status/config".text = ''
      general {
          colors = true
          interval = 5
          color_good = "#9ece6a"
          color_degraded = "#e0af68"
          color_bad = "#f7768e"
      }
      order += "read_file current_song"
      order += "disk /"
      order += "load"
      order += "memory"
      order += "read_file gpu_vram"
      order += "ethernet _first_"
      order += "wireless _first_"
      order += "tztime local"
      read_file current_song {
          path = "${statusSongFile}"
          format = "🎧 %content"
      }
      read_file gpu_vram {
          path = "/tmp/gpu_vram"
          format = "GPU VRAM: %content MB"
      }
      memory {
          format = "RAM: %used / %total"
          threshold_degraded = "10%"
          format_degraded = "MEMORY LOW: %free"
      }
      ethernet _first_ {
          format_up = "ETH: %ip"
          format_down = ""
      }
      wireless _first_ {
          format_up = "WIFI: (%quality at %essid) %ip"
          format_down = ""
      }
      tztime local {
          format = "%Y-%m-%d %H:%M:%S"
      }
    '';
  };
}

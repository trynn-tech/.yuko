# modules/desktop/i3.nix
{ config, lib, pkgs, ... }:

with lib;

let
  cfg = config.myDesktop;
  arandrScript = ./assets/default.sh;
  vlcStartupDir = "~/yt";
in {
  options.myDesktop.wallpaper = mkOption {
    type = types.path;
    default = ./assets/default-bg.jpg;
  };

  config = {
    home.packages = [
      pkgs.feh
      pkgs.arandr
      pkgs.vlc
      pkgs.firefox
      pkgs.kdePackages.kdeconnect-kde
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

          # Gamer Mode Toggle - pane focus indicator toggle
          "Mod4+g" = "exec --no-startup-id i3-msg '[con_id=\"__focused__\"] border toggle'";
          "Mod4+d" = "exec --no-startup-id ${pkgs.rofi}/bin/rofi -show drun";
          "Mod4+x" = "exec --no-startup-id \"i3-msg 'split h; exec alacritty -e yazi'\"";
          
          "Mod4+Return" = "exec alacritty";
          "Mod4+space" = "exec alacritty";

          "Mod4+minus" = "scratchpad show";
          "Mod4+Shift+w" = "exec alacritty -e nvim +VimwikiIndex";
          "Mod4+Shift+q" = "kill";
          
          "Mod4+b" = "exec pavucontrol";
	  "Mod4+v" = "exec vlc --random ${vlcStartupDir}";
          "Mod4+f" = "exec firefox";
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
          { command = "${arandrScript}"; notification = false; }
          { command = "${pkgs.feh}/bin/feh --bg-max ${cfg.wallpaper}"; always = true; notification = false; }
          { command = "xsetroot -cursor_name left_ptr"; always = true; notification = false; }
          { command = "${pkgs.copyq}/bin/copyq"; notification = false; }
          {
            command = "while true; do nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits > /tmp/gpu_vram; sleep 5; done";
            always = true;
            notification = false;
          }
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
      order += "disk /"
      order += "load"
      order += "memory"
      order += "read_file gpu_vram"
      order += "ethernet _first_"
      order += "wireless _first_"
      order += "tztime local"
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

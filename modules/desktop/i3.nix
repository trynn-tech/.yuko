# modules/desktop/i3.nix

{ config, lib, pkgs, ... }:

with lib;
let
  cfg = config.myDesktop;
in {

  options.myDesktop.wallpaper = mkOption {
    type = types.path;
    default = ./assets/default-bg.jpg;
  };

  config = {
    # Ensure feh is available even if not in configuration.nix
    home.packages = [ pkgs.feh ];

    xsession.windowManager.i3 = {
      enable = true;
      config = {
        modifier = "Mod4";
        terminal = "alacritty";

        # Standard window behavior
        window = {
          border = 0;
          titlebar = false;
        };

        # Floating window behavior
        floating = {
          border = 0;
          titlebar = false;
        };

        # --------------
        # Use lib.mkOptionDefault to ensure we only override what we need
        keybindings = lib.mkOptionDefault {
          # Use hardcoded Mod4 strings for maximum reliability
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

          # Container Moving
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

          # Seamless physical screen shifting via keyboard shortcuts
          "Mod4+Control+Left"  = "focus output left";
          "Mod4+Control+Right" = "focus output right";
          "Mod4+Control+Up"    = "focus output up";
          "Mod4+Control+Down"  = "focus output down";

          # Instantly push focused windows to the other monitor
          "Mod4+Shift+Left"    = "move output left";
          "Mod4+Shift+Right"   = "move output right";

          # Your Utilities
          ## FIXED: Clean program launcher initialization to respect your targeted screen focus space
          "Mod4+d" = "exec --no-startup-id ${pkgs.rofi}/bin/rofi -show drun";
          ## Open Yazi (File Manager) with win+y 
          "Mod4+e" = "exec --no-startup-id \"i3-msg 'split h; exec alacritty -e yazi'\"";
          "Mod4+space" = "exec --no-startup-id i3-msg \"[class='scratchpad'] scratchpad show\" || exec alacritty --class scratchpad";
          "Mod4+minus" = "scratchpad show";
          "Mod4+Shift+w" = "exec alacritty -e nvim +VimwikiIndex";
          "Mod4+Shift+q" = "kill";
          "Mod4+v" = "exec pavucontrol";
        };

        # Explicitly map your workspace numbers to your verified physical port names
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

        startup = [
          { command = "${pkgs.feh}/bin/feh --bg-max ${cfg.wallpaper}"; always = true; notification = false; }
          { command = "xsetroot -cursor_name left_ptr"; always = true; notification = false; }
          { command = "${pkgs.copyq}/bin/copyq"; notification = false; }
          {
            command = "while true; do nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits > /tmp/gpu_vram; sleep 5; done";
            always = true;
            notification = false;
          }
        ];

        bars = [
          {
            position = "bottom";
            statusCommand = "${pkgs.i3status}/bin/i3status";
          }
        ];
      };

      # Ensures display extension configuration boots before the layout engine establishes mapping positions
      extraConfig = ''
        exec_always --no-startup-id ${pkgs.xorg.xrandr}/bin/xrandr --output HDMI-0 --auto --primary --output HDMI-1-2 --auto --left-of HDMI-0
        new_window none
        new_float none
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


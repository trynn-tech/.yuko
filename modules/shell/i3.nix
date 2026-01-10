# modules/shell/i3.nix
{ config, lib, pkgs, ... }:

{
  xsession.windowManager.i3 = {
    enable = true;
    config = {
      modifier = "Mod4";
      terminal = "alacritty";

      # --- 1. Startup Logic (The Precision Handshake) ---
      startup = [
        # Set the cursor immediately to avoid the 'X' pointer
        { command = "xsetroot -cursor_name left_ptr"; always = true; notification = false; }
        
        # Clipboard management
        { command = "${pkgs.copyq}/bin/copyq"; notification = false; }

        # GPU Background Monitor: Pipes Nvidia VRAM usage to a temp file for i3status
        { 
          command = "while true; do nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits > /tmp/gpu_vram; sleep 5; done"; 
          always = true; 
          notification = false; 
        }
      ];

      # --- 2. Window Rules (The Scratchpad Intelligence) ---
      window.commands = [
        {
          # If a window has the class 'scratchpad', make it float and hide it immediately
	  command = "floating enable, resize set 800 600, move position center";
          criteria = { class = "scratchpad"; };
        }
      ];

      keybindings = let
        mod = "Mod4";
      in lib.mkOptionDefault {
        # --- Workspace Navigation ---
        "${mod}+1" = "workspace number 1"; # Wiki / NixVim
        "${mod}+2" = "workspace number 2"; # MCP Server / Lab
        "${mod}+3" = "workspace number 3"; # GPU/Podman Monitoring

        # --- The Rofi Launcher (Fixed Keyboard Lag) ---
        # Replacing dmenu with Rofi for smoother input focus
        "${mod}+d" = "exec ${pkgs.rofi}/bin/rofi -show drun";

        # --- The Hyprland-style Scratchpad ---
        # Toggle existing scratchpad
        "${mod}+minus" = "scratchpad show";
        # In i3.nix keybindings:
        "${mod}+space" = "exec --no-startup-id i3-msg \"[class='scratchpad'] scratchpad show\" || exec alacritty --class scratchpad";
        # --- Lab Utilities ---
        "${mod}+Shift+w" = "exec alacritty -e nvim +VimwikiIndex";
        "${mod}+Shift+q" = "kill";
        "${mod}+v" = "exec pavucontrol";
      };

      # --- 3. Status Bar ---
      bars = [
        {
          position = "bottom";
          statusCommand = "${pkgs.i3status}/bin/i3status";
          fonts = {
            names = [ "DejaVu Sans Mono" ];
            size = 10.0;
          };
          colors = {
            background = "#1a1b26";
            statusline = "#c0caf5";
            separator  = "#414868";
          };
        }
      ];
    };
  };

  # --- 4. i3status Configuration ---
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
    order += "tztime local"

    # Reading the VRAM data generated in the startup block
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
        format_up = "NET: %ip"
        format_down = "NET: down"
    }

    tztime local {
        format = "%Y-%m-%d %H:%M:%S"
    }
  '';
}

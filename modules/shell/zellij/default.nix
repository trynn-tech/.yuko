# modules/shell/zellij/default.nix
{ config, pkgs, ... }:

let
  overviewLayout = ''
    layout {
        default_tab_template {
            children
            pane size=1 borderless=true {
                plugin location="zellij:compact-bar"
            }
        }

        // Tab 1: Just btop taking up 100% of the viewport
        tab name="System" focus=true {
            pane command="${pkgs.btop}/bin/btop" name="btop" borderless=true
        }

        // Tab 2: The hardware monitors sharing the screen 50/50 horizontally
        tab name="Monitors" split_direction="horizontal" {
            pane command="${pkgs.pipewire}/bin/pw-top" name="Audio (pw-top)" borderless=true
            pane command="${pkgs.nvtopPackages.full}/bin/nvtop" name="GPU (nvtop)" borderless=true
        }
    }
  '';

  synthOverviewScript = pkgs.writeShellScriptBin "synth-overview" ''
    SESSION="Yuko-Overview"

    # Destroy any background instances cleanly before loading the fresh configuration
    if ${pkgs.zellij}/bin/zellij list-sessions --no-formatting 2>/dev/null | ${pkgs.gnugrep}/bin/grep -q "^$SESSION"; then
        ${pkgs.zellij}/bin/zellij delete-session "$SESSION" 2>/dev/null || true
    fi

    # Launching inside alacritty handles standard input rendering perfectly
    exec ${pkgs.alacritty}/bin/alacritty --class "synth-overview" -e ${pkgs.zellij}/bin/zellij --layout overview attach --create "$SESSION"
  '';
in
{
  programs.zellij = {
    enable = true;
    enableZshIntegration = false;
  };

  # Write layout declaratively into ~/.config/zellij/layouts/overview.kdl
  xdg.configFile."zellij/layouts/overview.kdl".text = overviewLayout;

  # Declaratively generate a desktop entry so the vicinae server can instantly index it
  xdg.desktopEntries.synth-overview = {
    name = "Synth Overview";
    genericName = "System Monitor Dashboard";
    exec = "${synthOverviewScript}/bin/synth-overview";
    terminal = false; 
    categories = [ "System" "Utility" ];
    comment = "Launch declarative Zellij btop and hardware monitoring layout";
  };

  # Supervised background lifecycle daemon for the application launcher
  systemd.user.services.vicinae = {
    Unit = {
      Description = "Vicinae Application Launcher Server Cache Daemon";
      After = [ "graphical-session-pre.target" ];
      PartOf = [ "graphical-session.target" ];
    };
    Service = {
      ExecStart = "${pkgs.vicinae}/bin/vicinae server";
      Restart = "on-failure";
      RestartSec = 2;
    };
    Install = {
      WantedBy = [ "graphical-session.target" ];
    };
  };

  home.packages = [
    synthOverviewScript
  ];
}


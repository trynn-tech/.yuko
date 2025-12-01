# modules/local-bin.nix
{ config, lib, pkgs, ... }:

with lib;
let
  cfg = config.yuko.localBin;  # Note: using camelCase for subnamespace to avoid clashes
in
{
  options.yuko.localBin = {
    enable = mkEnableOption "Yuko local bin symlinks & mail scripts";
  };

  config = mkIf cfg.enable {
    # Ensure core mail tools are available (harmless if duplicated from home.packages)
    home.packages = with pkgs; [
      isync   # mbsync
      msmtp
      neomutt
    ];

    # Custom scripts in ~/.local/bin (HM auto-creates the dir and adds to PATH)
    home.file = {
      ".local/bin/mail-sync".text = ''
        #!/usr/bin/env bash
        set -euo pipefail
        ACCOUNT="${config.yuko.mail.activeAccount}"
        echo "Syncing mail for $ACCOUNT..."
        mbsync -a  # Or -c ~/.config/isyncrc if needed
        echo "Done. Run 'neomutt' to view updates."
      '';

      ".local/bin/mail-send".text = ''
        #!/usr/bin/env bash
        set -euo pipefail
        msmtp "$@"
      '';

      ".local/bin/mail-open".text = ''
        #!/usr/bin/env bash
        set -euo pipefail
        neomutt
      '';
    };

    # Make scripts executable (runs post-activation)
    home.activation.chmodLocalBin = hm.dag.entryAfter ["writeBoundary"] ''
      chmod +x $HOME/.local/bin/mail-*
    '';
  };
}

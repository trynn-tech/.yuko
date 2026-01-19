# modules/composer/local-bin.nix
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption mkIf types;
  homeDir = config.home.homeDirectory;
in {
  options.yuko.composer.localBin.enable = mkOption {
    type = types.bool;
    default = true;
    description = "Ensure ~/.local/bin exists and is added to PATH.";
  };

  config = mkIf config.yuko.composer.localBin.enable {
    # 1) Add ~/.local/bin to PATH
    home.sessionPath = [ "${homeDir}/.local/bin" ];

    # 2) Manifest the yuko-compose script
    home.file.".local/bin/yuko-compose" = {
      executable = true;
      text = ''
        #!/usr/bin/env bash
        # Launch Aider pointed at our local port 8081
        ${pkgs.aider-chat}/bin/aider --config ${homeDir}/.aider.conf.yml "$@"
      '';
    };
  };
}

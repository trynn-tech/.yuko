# modules/dev/nix/default.nix
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption types mkIf;
in {
  options.yuko.dev.nix = {
    enable = mkOption {
      type = types.bool;
      default = true;
      description = "Enable Nix dev tooling (statix, deadnix, etc.) for YukoNix.";
    };
  };

  config = mkIf config.yuko.dev.nix.enable {
    home.packages = with pkgs; [
      statix
      deadnix
    ];
  };
}

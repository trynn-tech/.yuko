# modules/core.nix
{
  config,
  lib,
  pkgs,
  ...
}:

let
  inherit (lib) mkOption types;
in
{
      programs.home-manager.enable = true;
}

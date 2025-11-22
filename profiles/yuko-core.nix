{ pkgs, nixCats, ... }:

{
  imports = [
    ../modules/core.nix
    ../modules/shell.nix
    ../modules/editors/nixcats.nix
  ];

  # Anything specific to yuko-core goes here:
  home.username = "trynn";
  home.homeDirectory = "/home/trynn";
  home.stateVersion = "23.11";

  programs.home-manager.enable = true;
}

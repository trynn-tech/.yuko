# modules/dev/default.nix
{ config, lib, pkgs, ... }:
{
  imports = [
    ./nix
  ];

  # Essential system utility packages housed directly in core
  home.packages = with pkgs; [
    copyq          
    feh            
    vlc
  ];
}

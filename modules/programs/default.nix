# modules/programs/default.nix
{ config, lib, pkgs, ... }:

{
  imports = [
    ./firefox
    ./file-managers.nix
    ./mpv.nix
  ];

  # Essential system utility packages housed directly in core
  home.packages = with pkgs; [
    copyq          
    feh            
    vlc
    wireshark
    btop
    ncdu
    caligula
    freetube
    zathura
    playerctl
    handy
  ];

}


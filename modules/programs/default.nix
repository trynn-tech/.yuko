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
    btop # process monitor
    ncdu # storage management
    caligula # Image flasher
    freetube 
    zathura # E-Book reader with vi controls
    playerctl # media controls
    handy # yuko stt
    scope-tui # audio visualizer
    qpwgraph # visualize audio/video streams 
    helvum # A GTK-based visual patchbay for PipeWire
    coppwr # A low-level PipeWire object and parameter explorer
    gnuplot 
  ];

}


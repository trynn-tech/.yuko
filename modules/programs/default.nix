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
    btop # process monitor
    nvtopPackages.full # GPU monitor
    wireshark # network monitor
    termshark # network monitor tui
    ncdu # storage management
    caligula # Image flasher
    freetube 
    zathura # E-Book reader with vi controls
    playerctl # media controls
    handy # yuko stt
    scope-tui # audio visualizer
    qpwgraph # visualize audio/video streams 
    coppwr # A low-level PipeWire object and parameter explorer
    gnuplot # cli graphing utility
    yt-dlp
  ];

}


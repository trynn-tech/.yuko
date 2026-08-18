# modules/desktop/default.nix
{ config, lib, pkgs, ... }:

{
  imports = [
    ./i3.nix
    # You can add more here later, e.g.:
    # ./fonts.nix
    # ./gtk.nix
    # ./screen-locker.nix
  ];

  # Essential system utility packages housed directly in core
  home.packages = with pkgs; [
    dmenu          
    vicinae
    rofi            
    arandr         
    adwaita-icon-theme 
    brightnessctl   
    pavucontrol     
  ];
}

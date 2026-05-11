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
}

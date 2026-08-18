# modules/programs/freetube.nix
{ pkgs, ... }:

{
  # Install the FreeTube package
  home.packages = [ pkgs.freetube ];
}

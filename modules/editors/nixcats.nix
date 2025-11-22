# modules/editors/nixcats.nix
{ pkgs, nixCats, ... }:
{
  home.packages = [
    nixCats.packages.${pkgs.system}.default
  ];

  home.sessionVariables.EDITOR = "nvim";
}

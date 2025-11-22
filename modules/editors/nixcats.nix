# modules/editors/nixcats.nix
{ pkgs, nixCats, ... }:

{
  home.packages = [
    nixCats.packages.${pkgs.system}.default
  ];

  # nixCats `nvim` will sit on PATH as `nvim`,
  # so core.nix's EDITOR = "nvim" will use this.
}

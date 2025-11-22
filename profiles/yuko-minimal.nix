{ pkgs, nixCats, ... }:

{
  imports = [
    ../modules/core.nix
    ../modules/shell.nix
    # maybe no nixCats, just a simple editor:
    # ../modules/editors/basic-nvim.nix
  ];

  home.username = "trynn";
  home.homeDirectory = "/home/trynn";
  home.stateVersion = "23.11";

  programs.home-manager.enable = true;

  # Maybe fewer packages here, or override things:
  home.packages = with pkgs; [
    # minimal tools only
    git
    neovim
  ];
}

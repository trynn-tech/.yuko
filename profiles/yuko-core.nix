# profiles/yuko-core.nix
{ config, pkgs, nixCats, ... }:

{
  imports = [
    ../modules/core.nix   # your core module (username, stateVersion, etc)
    nixCats.homeModule    # import nixCats' HM module
  ];

  # nixCats module configuration
  nixCats = {
    enable = true;

    # this is the name of the wrapped Neovim package it will create
    # it will give you a binary named "nvim" on your PATH
    packageNames = [ "nvim" ];

    # where your Lua config lives
    # you can change this later once you have your nixCats config directory sorted
    luaPath = ./.;
  };

  # point $EDITOR at the nixCats-provided nvim
  home.sessionVariables.EDITOR = "nvim";
}

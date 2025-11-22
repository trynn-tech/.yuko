{ config, pkgs, ... }:

{
  home.username      = "trynn";
  home.homeDirectory = "/home/trynn";

  # this is the important line:
  home.stateVersion  = "23.11";

  home.sessionVariables = {
    LANG = "en_US.UTF-8";
    EDITOR = "nvim";  # will point to nixCats in core profile
  };

  # common packages for all modes (you can tune this)
  home.packages = with pkgs; [
    hello
  ];

  programs.home-manager.enable = true;
}

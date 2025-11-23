# modules/core.nix 
{ config, pkgs, ... }:
{
  home.username      = "trynn";
  home.homeDirectory = "/home/trynn";

  # Must be a supported version for your pinned home-manager
  home.stateVersion  = "23.11";

  programs.home-manager.enable = true;

  # Some global packages you always want
  home.packages = with pkgs; [
    git
    ripgrep
    fd
    fzf
  ];

  # Editor env var – will point to nixvim's nvim
  home.sessionVariables.EDITOR = "nvim";
}

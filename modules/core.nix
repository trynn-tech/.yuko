# modules/core.nix
{ pkgs, ... }:

{
  home.sessionVariables = {
    LANG = "en_US.UTF-8";
    EDITOR = "nvim";  # will point to nixCats in core profile
  };

  # common packages for all modes (you can tune this)
  home.packages = with pkgs; [
    hello
  ];
}

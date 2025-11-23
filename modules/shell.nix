# modules/shell.nix
{ pkgs, ... }:

{
  programs.zsh = {
    enable = true;
    enableCompletion = true;

    autosuggestions.enable = true;
    syntaxHighlighting.enable = true;
  };

  # If you want zsh as your default
  home.shell = pkgs.zsh;
}

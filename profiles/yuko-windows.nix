# profiles/yuko-windows.nix
{ config, lib, pkgs, ... }:

{
  imports = [
    ../modules/core
  ];

  # -------------------------------
  # Global packages available to Yuko
  # -------------------------------
  home.packages = with pkgs; [
    gnuplot # cli graphing utility
    yt-dlp
    handy # yuko stt
    scope-tui
  ];

  # -------------------------------
  # Global env vars
  # -------------------------------
  home.sessionVariables = {
    EDITOR = "nvim";
    PATH = "$HOME/.local/bin:$PATH";
  };

  # -------------------------------
  # Toggle global FLAGs
  # -------------------------------
  yuko = {
    # Developer level scaffolding equipment
    dev.nix.enable = true;
    dev.nix.formatter = "nixfmt";

    # Terminal Interface
    shell.default = true;

    # -----------------------------------------------------------------
    # Central Local AI Controller Endpoint Matrix
    # -----------------------------------------------------------------
    synths = {
      enable = true;
      modelName = "architect";
      apiBase = "http://localhost:8081/v1";
      searxngBase = "http://localhost:8888";
    };

    # Zsh configuration
    shell.zsh.enable = true;
  };
}

# profiles/yuko-core.nix
{ config, lib, pkgs, ... }:

{
  imports = [
    ../modules/core
    ../modules/programs
    ../modules/desktop
  ];

  # -------------------------------
  # Global packages available to Yuko
  # -------------------------------
  home.packages = with pkgs; [
    sonobus
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

    # Terminal Interface & Zsh
    shell.default = true;
    shell.zsh.enable = true;

    # Frag TUI Editor
    frag = {
      enable = true;
      defaultWorkspace = "~/workspace";
    };

    # -----------------------------------------------------------------
    # Central Local AI Controller Endpoint Matrix
    # -----------------------------------------------------------------
    synths = {
      enable = true;
      modelName = "architect";
      apiBase = "http://localhost:8081/v1";
      searxngBase = "http://localhost:8888";
    };
  };
}

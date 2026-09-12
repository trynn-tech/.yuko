# profiles/yuko-fob.nix
{ config, lib, pkgs, ... }:

{
  imports = [
    ../modules/core
    ../modules/programs
    ../modules/desktop
    ../modules/networking
  ];

  # -------------------------------
  # Global Environment Defaults
  # -------------------------------
  home.sessionVariables = {
    EDITOR = "nvim";
    PATH = "$HOME/.local/bin:$PATH";
  };

  # -------------------------------
  # Global packages
  # -------------------------------
  home.packages = with pkgs; [
    sonobus
  ];

  # -------------------------------
  # Yuko Declarative Options
  # -------------------------------
  yuko = {
    dev.nix.enable = true;
    dev.nix.formatter = "nixfmt";
    shell.default = true;
    shell.zsh.enable = true;

    # -----------------------------------------------------------------
    # Network Construction Automation
    # -----------------------------------------------------------------
    networking.construct.enable = true;

    synths = {
      enable = true;
      modelName = "architect";
      apiBase = "http://localhost:8081/v1";
      searxngBase = "http://localhost:8888";
    };

    wan = {
      enable = true;
      wanInterface = "vm-fob-wan";
    };

    openwrt-provision = {
      enable = true;
      memory = 2048;
    };
  };
}

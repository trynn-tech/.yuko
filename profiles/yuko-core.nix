# profiles/yuko-core.nix
{
  config,
  lib,
  pkgs,
  ...
}:

{

  imports = [
    # Core
    ../modules/core.nix

    # Shell + editor
    ../modules/editors/nixvim.nix
    ../modules/shell
    ../modules/tmux

    # Display -- consider moving to Programs modules
    ../modules/desktop

    # Composer
    ../modules/composer
    ../modules/dev

    # Program modules
    ../modules/programs
  ];

  # Profile-specific extras live here if needed
  # e.g. extra home.packages, host-specific stuff, etc.

  # Enable HM managing itself
  programs.home-manager.enable = true;

  # -------------------------------
  # Global packages available to Yuko
  # -------------------------------
  home.packages = with pkgs; [
    git
    ripgrep
    fd
    fzf
    pass
    vlc
    strawberry
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
    # Central Infrastructure Providers Matrix
    composer.apiBase     = "http://localhost:8081/v1"; 
    composer.searxngBase = "http://127.0.0.1:8888";
    composer.modelName   = "architect";

    # Artificial Intelligence Pair Programmer
    composer.aider.enable = true;

    # Artificial Architect
    composer.deepResearch.enable = true;

    # This explicitly enables the Zsh configuration defined in the new submodule.
    shell.zsh.enable = true;

  };
}

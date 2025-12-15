# profiles/yuko-dev.nix
{
  config,
  lib,
  pkgs,
  ...
}:

{

  imports = [
    # --- CORE FRAMEWORK ---
    ../modules/core.nix

    # --- EDITORS & SHELL (Required for code editing/interaction) ---
    ../modules/editors/nixvim.nix
    ../modules/shell
    
    # ---  DEV TOOLS (Required for semantic/Nix tooling) ---
    ../modules/dev

    ../modules/syncthing/default.nix
  ];

  # Profile-specific extras live here if needed

  # Enable HM managing itself
  programs.home-manager.enable = true;

  # -------------------------------
  # Global packages available to Yuko
  # -------------------------------
  # We keep the essential packages for a development environment
  home.packages = with pkgs; [
    git
    ripgrep
    fd
    fzf
    
    # Keeping 'pass', 'isync', 'msmtp' is optional but since they are small,
    # let's keep only the absolute necessities for a developer terminal:
    pass # for secrets access
  ];

  # -------------------------------
  # Global env vars
  # -------------------------------
  home.sessionVariables.EDITOR = "nvim";

  # -------------------------------
  # Toggle global FLAGs (Mirroring the desired core settings)
  # -------------------------------
  yuko = {
    # Developer level scaffolding equipment
    dev.nix.enable = true;
    dev.nix.formatter = "nixfmt";

    # Terminal Interface
    shell.default = true;

    # debug helper
    debug.manualSteps = true;

    # No need to set mail flags here since mail modules aren't imported.

    # Composer Ctags
    #composer.ctags.enable = true;
  };

  # -------------------------------
  # Custom Semantic Compiler (Remains, as it's useful for editing Nix code)
  # -------------------------------
  #yuko.composer.ctags.extraConfig = ''
  #  # Treat *.nix as Nix (if needed)
  #  --langmap=Nix:.nix
  #'';

}

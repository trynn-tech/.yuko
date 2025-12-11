# profiles/yuko-core.nix
{ config, lib, pkgs, ... }:

{

  imports = [
    # Core
    ../modules/core.nix

    # Shell + editor
    ../modules/editors/nixvim.nix
    ../modules/shell
    ../modules/tmux

    # Composer
    ../modules/composer
    ../modules/dev

    # Mail modules 
    ../modules/mail/accounts/trynn-primary.nix
    ../modules/mail/neomutt.nix
    ../modules/mail/mbsync.nix
    ../modules/mail/msmtp.nix
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
    isync
    msmtp
  ];

  # -------------------------------
  # Global env vars
  # -------------------------------
  home.sessionVariables.EDITOR = "nvim";

  # -------------------------------
  # Toggle global FLAGs
  # -------------------------------

  yuko.composer.cli.enable = true;

  # debug helper
  yuko.debug.manualSteps = true;

  # Allow mail or mbsync/IMAP to create directories
  yuko.security.mailLockdown = false;

  yuko.composer.ctags.enable = true;

  # -------------------------------
  # Custom Semantic Compiler
  # -------------------------------
  yuko.composer.ctags.extraConfig = ''
    # Treat *.nix as Nix (if needed)
    --langmap=Nix:.nix

    # Later: USL / Forge / yuko.* patterns here
    # Adjunct definition of code here ...
  '';

}

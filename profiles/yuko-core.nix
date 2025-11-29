# profiles/yuko-core.nix
{ config, lib, pkgs, ... }:

{
  imports = [
    # Core
    ../modules/core.nix

    # Shell + editor
    ../modules/editors/nixvim.nix
    ../modules/shell/default.nix
    ../modules/tmux/default.nix

    # Composer
    ../modules/composer

    # Mail modules 
    ../modules/mail/accounts/trynn-primary.nix
    ../modules/mail/neomutt.nix
    ../modules/mail/mbsync.nix
    ../modules/mail/msmtp.nix
  ];

  # -------------------------------
  # Home Manager identity
  # -------------------------------
  home.username      = "trynn";
  home.homeDirectory = "/home/trynn";

  # Must match the version your pinned Home Manager supports
  home.stateVersion  = "23.11";

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

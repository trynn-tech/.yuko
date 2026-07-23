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
    vlc
    flashfocus
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

    # -----------------------------------------------------------------
    # Toggle Consumer Interface Agents (They inherit the values above automatically)
    # -----------------------------------------------------------------
    # Artificial Intelligence Orchestrator and Interface
    composer.hermes.enable = true;
    # Artificial Intelligence Pair Programmer
    composer.aider.enable = true;
    # Artificial Intelligence Researcher
    composer.deepResearch.enable = true;

    # This explicitly enables the Zsh configuration defined in the new submodule.
    # Note: I added a line in modules/shell/default.nix to set this based on shell.default,
    # but you can also set it explicitly here:
    shell.zsh.enable = true;

    # debug helper
    debug.manualSteps = true;

    # Allow mail or mbsync/IMAP to create directories
    security.mailLockdown = false;

    # A Bit archaic and not very useful for Nix,
    #first thought for semantics and may remove
    composer.ctags.enable = true;

  };

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

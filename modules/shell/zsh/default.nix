# modules/shell/zsh/default.nix
{
  config,
  lib,
  pkgs,
  ...
}:

let
  yukoRoot = config.home.homeDirectory;

  # Define Zsh plugin paths manually
  p10kPath = "${pkgs.zsh-powerlevel10k}/share/zsh-powerlevel10k";
  syntaxHighlighterPath = "${pkgs.zsh-syntax-highlighting}/share/zsh/site-functions";
  autosuggestionsPath = "${pkgs.zsh-autosuggestions}/share/zsh/site-functions";
  
  # YUKO_PACKAGE_PATH: Path for zsh-navigation-tools
  zshNavigationToolsPath = "${pkgs.zsh-navigation-tools}/share/zsh-navigation-tools";
  
  yukoZshFunctionContent = ''
    # --- YUKO CUSTOM SHELL CODE START ---
    
    # --- Nix Profile Sourcing ---
    if [ -e "/nix/var/nix/profiles/per-user/$USER/profile/etc/profile.d/nix.sh" ]; then
      . "/nix/var/nix/profiles/per-user/$USER/profile/etc/profile.d/nix.sh"
    else
      export PATH="$HOME/.nix-profile/bin:/nix/var/nix/profiles/default/bin:$PATH"
    fi

    # --- Yuko snowball command (Function Definitions) ---
    # YUKO_FUNCTION_DOC: Runs formatting, fixing (statix), and linting (deadnix) on the Yuko config.
    yuko_snowball() {
      # Use $HOME/.yuko for robustness
      cd "$HOME/.yuko" || return 1
      local yuko_status=0
      
      # YUKO_HELP_DOC: Run 'yuko_snowball --help' for usage instructions.
      if [[ "$1" == "--help" ]]; then
        echo "yuko_snowball: Cleans, formats, and validates the Nix configuration."
        echo "Usage: yuko_snowball"
        echo "  1. Formats Nix files (nix fmt or nixfmt)."
        echo "  2. Fixes issues with 'statix fix'."
        echo "  3. Checks for unused attributes with 'deadnix'."
        return 0
      fi

      echo "[yuko] formatting nix…"
      if command -v nix fmt >/dev/null 2>&1; then
        nix fmt . || yuko_status=1
      elif command -v nixfmt >/dev/null 2>&1; then
        nixfmt **/*.nix || yuko_status=1
      else
        echo "[yuko] no nix formatter (nix fmt / nixfmt) found"
      fi

      echo "[yuko] statix pass…"
      command -v statix >/dev/null 2>&1 && statix fix . || echo "[yuko] statix not found, skipping"

      echo "[yuko] deadnix pass…"
      command -v deadnix >/dev/null 2>&1 && deadnix . || echo "[yuko] deadnix not found, skipping"

      return $yuko_status
    }
    # --- YUKO CUSTOM SHELL CODE END ---
  '';

  yukoZshSourceFile = pkgs.writeText "yuko-zsh-functions.zsh" yukoZshFunctionContent;

in
{

  options.yuko.shell.zsh = {
    enable = lib.mkEnableOption "Zsh shell configuration (including yk helper functions/aliases).";
  };

  config = lib.mkIf config.yuko.shell.zsh.enable {

    programs.zsh = {
      enable = true;
      enableCompletion = true;
      
      # --- Aliases (Guaranteed to work) ---
      # yuko:doc
      shellAliases = {
        ll = "ls -lh";
        la = "ls -lah";
        l = "ls -la";
        lt = "tree -L 2";
        gs = "git status";
        "~" = "cd ~";

        # YUKO_ALIAS_DOC: Invokes the 'pay-respects' command (replaces 'fuck').
        f = ''eval "$(pay-respects zsh)"''; 
        # YUKO_ALIAS_DOC: Clears current shell history and the zoxide directory history.
        history_clean_all = ''
          history -c \
          && ${pkgs.gnused}/bin/sed -i '/^#\+ /d' ~/.zsh_history \
          && rm -f "$(${pkgs.zoxide}/bin/zoxide data)" \
          && echo "Current session, zsh history file, and zoxide history cleared." \
          && history -r
        '';

        # YUKO_ALIAS_DOC: Change directory to the root of the Yuko configuration.
        nh = "cd /etc/nixos";
        # YUKO_ALIAS_DOC: Change directory to the Yuko modules directory.
        ny = "cd ${yukoRoot}/.yuko";
        # YUKO_ALIAS_DOC: Opens Neovim.
        n = "nvim";
        # YUKO_ALIAS_DOC: Formats all Nix files in the Yuko root.
        yfmt = "cd ${yukoRoot}/.yuko && (nix fmt . || nixfmt **/*.nix)";
        # YUKO_ALIAS_DOC: Runs static check (statix check and deadnix) on the Yuko config.
        ylint = "cd ${yukoRoot}/.yuko && statix check . && deadnix .";
        # YUKO_ALIAS_DOC: Runs static fixers (statix fix and deadnix) on the Yuko config.
        yfix = "cd ${yukoRoot}/.yuko && statix fix . && deadnix .";
        # YUKO_ALIAS_DOC: Builds the Home Manager derivation without activating it.
        ybuild = "cd ${yukoRoot}/.yuko && home-manager build --flake .#yuko-core";
        # YUKO_ALIAS_DOC: Switches to the Home Manager configuration for the current user.
        ym = "cd ${yukoRoot}/.yuko && home-manager switch --flake .#yuko-core";
        # YUKO_ALIAS_DOC: Runs the 'yuko_snowball' maintenance function.
        ysnow = "yuko_snowball";
      };

      # yuko:todo configure zsh plugins
      # --- initExtra: THE ENTIRE ZSH ENVIRONMENT CONFIGURATION ---
      initExtra = ''
        # --- Powerlevel10k: Suppress the Instant Prompt Warning (Recommended) ---
        typeset -g POWERLEVEL9K_INSTANT_PROMPT=quiet

        # Load the core Powerlevel10k theme script first.
        # This is where the prompt is defined and its functions are loaded.
        [[ -f ${p10kPath}/powerlevel10k.zsh-theme ]] && source ${p10kPath}/powerlevel10k.zsh-theme
        
        # Manually configure fpath to find plugin functions
        fpath=(
          ${p10kPath}
          ${syntaxHighlighterPath}
          ${autosuggestionsPath}
          # YUKO_PLUGIN_PATH: zsh-navigation-tools path
          ${zshNavigationToolsPath}
          $fpath
        )
        
        # Load the custom function file (Must be loaded after fpath is set)
        source ${yukoZshSourceFile}
        
        # Load Zsh Autosuggestions 
        [[ -f ${autosuggestionsPath}/zsh-autosuggestions.plugin.zsh ]] && source ${autosuggestionsPath}/zsh-autosuggestions.plugin.zsh
        
        # Load Zsh Navigation Tools 
        [[ -f ${zshNavigationToolsPath}/zsh-navigation-tools.plugin.zsh ]] && source ${zshNavigationToolsPath}/zsh-navigation-tools.plugin.zsh
        
        # Load P10k config if it exists (Must be loaded before zsh-syntax-highlighting)
        [[ -f ~/.p10k.zsh ]] && source ~/.p10k.zsh
        
        # MUST BE SOURCED LAST or very near the end to ensure it hooks correctly
        # into the Zsh Line Editor (ZLE) without interference.
        [[ -f ${syntaxHighlighterPath}/zsh-syntax-highlighting.plugin.zsh ]] && source ${syntaxHighlighterPath}/zsh-syntax-highlighting.plugin.zsh
      '';
    };
    
    # --- Home Manager Programs Modules ---
    
    # YUKO_MODULE_DOC: Installs zoxide and ensures Zsh integration is enabled.
    programs.zoxide = {
      enable = true;
      enableZshIntegration = true;
      # Aliases 'z' and 'zi' are enabled by default.
    };

    # Add the new module:
    # YUKO_MODULE_DOC: Installs the 'pay-respects' command (a replacement for thefuck).
    programs.pay-respects = {
      enable = true;
    };
    
    # YUKO_MODULE_DOC: Installs fzf and enables Zsh keybindings for history search (Ctrl+R) and fuzzy completion (Tab).
    programs.fzf = {
      enable = true;
      enableZshIntegration = true; # Enables keybindings (Ctrl+R) and fuzzy completion for files (Ctrl+T)
      # enableFzfCompletion and enableFzfHistory are handled by the Zsh integration flag.
    };
    
    # YUKO_SERVICE_DOC: Configures and manages the OpenSSH Agent service on login.
    services.ssh-agent = {
      enable = true;
      enableZshIntegration = true;
      # The ssh-agent will start automatically and set $SSH_AUTH_SOCK.
      # This replaces the need for the external zsh-agent plugin you linked.
    };
    
    # --- home.packages: We ensure all binaries/packages are installed ---
    home.packages = with pkgs; [
      zsh
      # Includes all packages needed for the manual sourcing above
      zsh-autosuggestions
      zsh-syntax-highlighting
      zsh-powerlevel10k 
      zsh-history-substring-search # Still listed here for completeness
      zsh-fzf-tab                 # Still listed here for completion override

      # Core utilities needed for new aliases:
      gnused # Required for the history_clean_all aliask 

      # The package for the manually-sourced plugin
      zsh-navigation-tools # Required for its functions to exist in fpath
      
      # General utilities
      tree 
      git
      fzf 

      # YUKO_PACKAGE_DOC: Taskwarrior (2.x branch).
      # FIX: Rename the binary to 'tw' and remove ALL conflicting completion scripts
      (taskwarrior2.overrideAttrs (old: { 
        # The build process is complete, so we use postInstall to modify the output directory ($out)
        postInstall = (old.postInstall or "") + ''
          # 1. Rename the main binary to 'tw' to resolve the conflict with go-task
          mv $out/bin/task $out/bin/tw
          
          # 2. Remove all completion directories to avoid conflicts with go-task and others
          rm -rf $out/share/bash-completion
          rm -rf $out/share/fish
          rm -rf $out/share/zsh/site-functions
        '';
      }))

      # Taskfile.dev task runner , cross-platform method for automating command-line tasks using a simple YAML file instead of complex scripts
      go-task

      # YUKO_PACKAGE_DOC: Simple, fast, and community-driven man pages.
      tealdeer 
      
      # YUKO_PACKAGE_DOC: A terminal interface for Git.
      tig 
      
      # We list zoxide, thefuck, and taskwarrior here for robustness, although their
      # dedicated programs modules above often handle the package dependency as well.
      # Listing them explicitly is a good habit.
      zoxide
      pay-respects
    ];
  };
}

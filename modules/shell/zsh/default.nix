# modules/shell/zsh/default.nix
{ config, lib, pkgs, ... }:

let
  yukoRoot = config.home.homeDirectory;
  p10kPath = "${pkgs.zsh-powerlevel10k}/share/zsh-powerlevel10k";
  
  # PINNED PATHS: Resolves the _task collision and fixes Yang Sync
  tw3Bin = "/nix/store/2r0ryqw8ay9fs38rj38q3bfzv47drija-taskwarrior-3.4.2/bin/task";
  goTaskBin = "${pkgs.go-task}/bin/task";

  yukoZshFunctionContent = ''
    yuko_snowball() {
      cd "${yukoRoot}/.yuko" || return 1
      echo "[yuko] formatting and syncing…"
      nix fmt . 2>/dev/null
      git add .
      # Restored 'nh' workflow
      nh home switch --flake .#yuko-core
    }

    # A dedicated triage loop
    yuko_triage() {
      while [[ $(${tw3Bin} +inbox count) -gt 0 ]]; do
        ${tw3Bin} +inbox +READY sort:entry+ limit:1
        echo -n "Triage (Modify ID <args> / 'q' to quit): "
        read -r cmd
        [[ "$cmd" == "q" ]] && break
        ${tw3Bin} $cmd -inbox
      done
    }
  '';

  yukoZshSourceFile = pkgs.writeText "yuko-zsh-functions.zsh" yukoZshFunctionContent;
in
{
  imports = [ ./taskwarrior.nix ];

  options.yuko.shell.zsh.enable = lib.mkEnableOption "Zsh configuration";

  config = lib.mkIf config.yuko.shell.zsh.enable {
    programs.zsh = {
      enable = true;
      enableCompletion = true;

      shellAliases = {
        # Navigation & Core
        ll = "ls -lh"; la = "ls -lah"; l = "ls -la";
        gs = "git status"; n = "nvim";
        
        # Maintenance (Restored 'nh' and 'ny')
        ym = "yuko_snowball";
        ny = "cd ${yukoRoot}/.yuko";
        ysnow = "yuko_snowball";

        # Taskwarrior 3 Braid
        task = "${tw3Bin}";
        ic = "${tw3Bin} add +inbox";
        ir = "${tw3Bin} +inbox list";
        vwi = "nvim ~/yang_wiki/index.md";

	# THE 'IT' FUNCTION: Inbox Triage
        # This shows the oldest (+inbox) task and prepares the 'modify' command
        it = "yuko_triage";
        
        # Quick Project Assignment (Helper)
        # Usage: ip 10 project:Re-L -inbox
        ip = "${tw3Bin} modify";

        # Go-Task (Fixed Collision)
        tk = "${goTaskBin}"; 
      };

      # Fixed Deprecation: Using initContent
      initContent = ''
        typeset -g POWERLEVEL9K_INSTANT_PROMPT=quiet
        [[ -f ${p10kPath}/powerlevel10k.zsh-theme ]] && source ${p10kPath}/powerlevel10k.zsh-theme
        
        source ${yukoZshSourceFile}
        source ${pkgs.zsh-autosuggestions}/share/zsh-autosuggestions/zsh-autosuggestions.zsh
        source ${pkgs.zsh-syntax-highlighting}/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
        
        [[ -f ~/.p10k.zsh ]] && source ~/.p10k.zsh
        compdef _task ${tw3Bin}
      '';
    };

    # FIXED: Restored 'z' command integration
    programs.zoxide = {
      enable = true;
      enableZshIntegration = true;
    };

    home.packages = with pkgs; [
      taskwarrior3
      nh
      gnused
      tree
      git
      fzf
    ];
  };
}


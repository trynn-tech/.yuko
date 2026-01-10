# modules/shell/zsh/default.nix
{ config, lib, pkgs, ... }:

let
  yukoRoot = config.home.homeDirectory;
  yukoFlake = "${yukoRoot}/.yuko";
  p10kPath = "${pkgs.zsh-powerlevel10k}/share/zsh-powerlevel10k";
  
  # PINNED PATHS: Resolves the _task collision and fixes binary paths
  tw3Bin = "/nix/store/2r0ryqw8ay9fs38rj38q3bfzv47drija-taskwarrior-3.4.2/bin/task";
  goTaskBin = "${pkgs.go-task}/bin/task";

  yukoZshFunctionContent = ''
    # YUKO_SNOWBALL: Formats, adds to git, and switches home-manager

    yuko_snowball() {
    cd "${yukoFlake}" || return 1
      echo "[yuko] formatting..."
      nix fmt . 2>/dev/null
      git add .
      echo "[yuko] activating configuration..."
      # Using the verbose command you prefer:
      home-manager switch --flake .#yuko-core
    }

    # YUKO_TRIAGE: The 'it' function for Inbox Space/Time Management
    yuko_triage() {
      while [[ $(${tw3Bin} +inbox count) -gt 0 ]]; do
        echo "--- Next Inbox Item ---"
        ${tw3Bin} +inbox +READY sort:entry+ limit:1
        echo ""
        echo "TEMPORAL LOGIC: due:today (Milestone) | sch:tmw (Process) | wait:1w (Space)"
        echo -n "Triage (Modify ID <args> / 'q' to quit): "
        read -r cmd
        [[ "$cmd" == "q" ]] && break
        # Append -inbox to ensure the task leaves the triage list
        ${tw3Bin} $cmd -inbox
      done
      echo "[yuko] Inbox cleared."
    }
  '';

  yukoZshSourceFile = pkgs.writeText "yuko-zsh-functions.zsh" yukoZshFunctionContent;
in
{
  imports = [ ./taskwarrior.nix ];

  # 1. OPTION DEFINITION (Crucial: Must be at top-level)
  options.yuko.shell.zsh.enable = lib.mkEnableOption "Zsh configuration";

  # 2. CONFIGURATION IMPLEMENTATION
  config = lib.mkIf config.yuko.shell.zsh.enable {
    programs.zsh = {
      enable = true;
      enableCompletion = true;

      shellAliases = {
        # Navigation
        ll = "ls -lh"; la = "ls -lah"; l = "ls -la";
        gs = "git status"; n = "nvim";
        cy = "cd ${yukoFlake}";           # Root of Yuko
        cm = "cd ${yukoFlake}/modules";  # Modules directory
        cn = "cd /etc/nixos";             # System Root (Renamed from nh)
        
        # Maintenance
        ym = "yuko_snowball";
        ysnow = "yuko_snowball";

        # Taskwarrior 3 (Spacetime Braid)
        task = "${tw3Bin}";
        ic = "${tw3Bin} add +inbox";
        ir = "${tw3Bin} +inbox list";
        it = "yuko_triage";
        vwi = "nvim ~/yang_wiki/index.md";
        ip = "${tw3Bin} modify";

        # Go-Task
        tk = "${goTaskBin}"; 
      };

      initContent = ''
        export FLAKE="${yukoFlake}"
        typeset -g POWERLEVEL9K_INSTANT_PROMPT=quiet
        [[ -f ${p10kPath}/powerlevel10k.zsh-theme ]] && source ${p10kPath}/powerlevel10k.zsh-theme
        
        source ${yukoZshSourceFile}
        source ${pkgs.zsh-autosuggestions}/share/zsh-autosuggestions/zsh-autosuggestions.zsh
        source ${pkgs.zsh-syntax-highlighting}/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
        
        [[ -f ~/.p10k.zsh ]] && source ~/.p10k.zsh
        
        # Completion fix for pinned binary
        compdef _task ${tw3Bin}
      '';
    };

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
      tig
    ];
  };
}

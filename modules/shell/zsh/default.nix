# modules/shell/zsh/default.nix
{ config, lib, pkgs, ... }:

let
  yukoRoot = config.home.homeDirectory;
  yukoFlake = "${yukoRoot}/.yuko";
  p10kPath = "${pkgs.zsh-powerlevel10k}/share/zsh-powerlevel10k";
  taskBin = "${pkgs.taskwarrior3}/bin/task";
in
{
  options.yuko.shell.zsh.enable = lib.mkEnableOption "Zsh and Taskwarrior configuration";

  config = lib.mkIf config.yuko.shell.zsh.enable {

    home.sessionVariables = {
      EDITOR = "nvim";
      VISUAL = "nvim";
    };

    # Restoring zoxide (z)
    programs.zoxide = {
      enable = true;
      enableZshIntegration = true;
    };

    # --- FZF Configuration ---
    programs.fzf = {
      enable = true;
      enableZshIntegration = true;
    };
    programs.taskwarrior = {
      enable = true;
      package = pkgs.taskwarrior3;
      extraConfig = ''
        data.location=~/.local/share/task
        sync.server.url=http://100.117.104.112:8080
        sync.server.client_id=58f0b3c8-9c13-427d-8921-1cebfe441a70
        sync.encryption_secret=HelloInternet42!
        confirmation=no
        dependency.confirmation=no
        recurrence.confirmation=no
        verbose=nothing
        report.inbox.filter=status:pending +inbox
        report.inbox.columns=id,entry.age,description
        confirmation=no
        confirmation=no
	include dark-green-256.theme
	color.tagged=cyan
      '';
    };

    programs.zsh = {
      enable = true;
      enableCompletion = true;

      shellAliases = {
        ll = "ls -la"; la = "ls -lah"; l = "ls -lh"; # Describe directory elements
        size = "du -hs"; ds = "du -hs"; # Print directory data volume
        gs = "git status"; n = "nvim";
        cy = "cd ${yukoFlake}";
        cs = "cd /etc/nixos";
        ym = "yuko_snowball";
	ys = "sudo nixos-rebuild switch";
        task = "${taskBin}";
        ic = "${taskBin} add +inbox";
        ir = "${taskBin} +inbox list";
        vwi = "nvim ~/wiki_yuko/index.md";
        vd = "nvim -c 'VimwikiMakeDiaryNote'";
        t = "task";
        te = "task edit";
        tu = "task modify";
        tf = "task done";
        td = "task delete";
        ts = "task sync";
        r = "report";
  	yuko-arch = "OPENAI_API_KEY=unused nix run nixpkgs#aider-chat -- --openai-api-base http://localhost:8081/v1 --model openai/architect --architect --edit-format editor-diff --no-stream --auto-commits";
      };

      initContent = ''
        export FLAKE="${yukoFlake}"
        
        if [ -e "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh" ]; then
          . "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh"
        fi

        # --- THE CORE ENGINES ---

        yuko_snowball() {
          cd "${yukoFlake}" || return 1
          echo "[yuko] formatting..."
          nix fmt . 2>/dev/null
          echo "[yuko] activating configuration..."
	  home-manager switch -b backup --flake .#yuko-core
        }

        it() {
          while true; do
            local id=$(${taskBin} +inbox +READY _ids | awk -F',' '{print $1}')
            if [ -z "$id" ]; then
              echo -e "\033[1;32m✅ Inbox empty\033[0m"
              break
            fi
            echo -e "\n\033[1;35m--- Next Inbox Item ---\033[0m"
            ${taskBin} "$id" info
            echo -e "\n\033[1;36mMAP:\033[0m [s] system | [t] technical | [y] yuko | [w] re-l | [e] emporium | [l] life | [r] radiant"
            echo -n "🚀 Move to (Key/Name/q): "
            read input
            [[ "$input" == "q" ]] && break
            case "$input" in
              s) proj="system" ;; t) proj="technical" ;; w) proj="re-l" ;;
              e) proj="emporium" ;; l) proj="life" ;; r) proj="radiant" ;;
              y) proj="yuko" ;; *) proj="$input" ;;
            esac
            ${taskBin} "$id" modify project:"$proj" -inbox
          done
        }

        tlo() {
          clear
          echo -e "\033[1;35m=== DAILY RECAP ===\033[0m"
          echo -e "\n\033[1;32m🏆 DONE TODAY:\033[0m"
          ${taskBin} end:today status:completed export | jq -r '.[].description' | sed 's/^/ [✓] /'
          echo -e "\n\033[1;36m🚀 TOMORROW:\033[0m"
          ${taskBin} +READY +PENDING limit:3
          ${taskBin} sync
        }

        # The missing Report function for active tasks
        report() {
          echo -e "\033[1;35m--- [ PERFORMANCE REPORT ] ---\033[0m"
          local done=$(${taskBin} end:today status:completed count)
          local pending=$(${taskBin} status:pending count)
          echo -e "Completed Today: \033[1;32m$done\033[0m | Pending: \033[1;33m$pending\033[0m"
          echo -e "\n\033[1;34mCurrently Clocked In:\033[0m"
          ${taskBin} +ACTIVE list || echo "  (No tasks currently started)"
        }

        _proj() {
          local p=$1 action=$2; shift 2
          case $action in
            c) ${taskBin} add project:"$p" "$@" ;;
            r) ${taskBin} project:"$p" list ;;
            u) ${taskBin} "$1" modify "''${@:2}" ;;
            d) ${taskBin} "$1" done ;;
            rm) ${taskBin} "$1" delete ;;
            *) ${taskBin} project:"$p" "$action" "$@" ;;
          esac
        }

        _ctx() {
          ${taskBin} context define "$1" project:"$1" 2>/dev/null
          ${taskBin} context "$1"
          clear
          echo -e "\033[1;33mContext switched to: $1\033[0m"
          report
        }

        # ALIAS GENERATOR
        for entry in "s:system" "t:technical" "y:yuko" "w:re-l" "e:emporium" "r:radiant" "l:life"; do
          key="''${entry%%:*}"; name="''${entry#*:}"
          alias "''${key}c"="_proj $name c"
          alias "''${key}r"="_proj $name r"
          alias "''${key}x"="_ctx $name"
          alias "''${key}u"="_proj $name u"
          alias "''${key}d"="_proj $name d"
        done

        alias cx="${taskBin} context none && clear && echo -e '\033[1;32mContext Cleared\033[0m'"
        alias review='${taskBin} status:pending age.gt:2w list'
        alias tll='${taskBin} summary; echo -e "\n--- GAPS ---"; ${taskBin} gprojects'

        # P10K and Plugins
        [[ -f ${p10kPath}/powerlevel10k.zsh-theme ]] && source ${p10kPath}/powerlevel10k.zsh-theme
        source ${pkgs.zsh-autosuggestions}/share/zsh-autosuggestions/zsh-autosuggestions.zsh
        source ${pkgs.zsh-syntax-highlighting}/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
        [[ -f ~/.p10k.zsh ]] && source ~/.p10k.zsh
        
        compdef _task ${taskBin}
      '';
    };

    home.packages = with pkgs; [ 
        taskwarrior3 nh gnused tree git tig jq psmisc 
    ];
  };
}

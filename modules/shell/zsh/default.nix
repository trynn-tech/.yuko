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
      SSL_CERT_FILE = "/etc/ssl/certs/ca-bundle.crt";
    };

    programs.zoxide = {
      enable = true;
      enableZshIntegration = true;
    };

    programs.fzf = {
      enable = true;
      enableZshIntegration = true;
    };

    # Automatically provision the dark-violets theme file for Taskwarrior
    home.file.".config/task/dark-violets-256.theme".text = ''
      # Taskwarrior Dark Violets 256 Theme
      color.label=bold cyan
      color.label.sort=cyan
      color.alternate=on color235
      color.header=bold yellow
      color.footnote=yellow
      color.warning=bold red
      color.error=bold white on red
      color.debug=cyan
      color.summary.background=on color235
      color.summary.bar=white on color141
      color.active=bold white on color54
      color.completed=color245
      color.deleted=color240
      color.recurring=magenta
      color.scheduled=green
      color.until=yellow
      color.waiting=color248
      color.priority.H=bold color141
      color.priority.M=color103
      color.priority.L=color60
    '';

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
        include dark-violets-256.theme
        color.tagged=cyan
      '';
    };

    programs.zsh = {
      enable = true;
      enableCompletion = true;
      shellAliases = {
        ll = "ls -la"; la = "ls -lah"; l = "ls -lh";
        size = "du -hs"; ds = "du -hs";
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
        # --- AUTOSTART TMUX (Independent Sessions) ---
        # Spawns a brand new unshared tmux session per terminal instance
        if [[ -z "$TMUX" ]] && [[ -n "$PS1" ]] && [[ $- == *i* ]]; then
          exec tmux
        fi

        export FLAKE="${yukoFlake}"
        if [ -e "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh" ]; then
          . "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh"
        fi

        ccl() {
          if [ -n "$WAYLAND_DISPLAY" ]; then
            ${pkgs.wl-clipboard}/bin/wl-copy --clear
          else
            ${pkgs.xclip}/bin/xclip -selection clipboard /dev/null
            ${pkgs.xclip}/bin/xclip -selection primary /dev/null
          fi
          echo -e "\033[1;31m🧹 Clipboard securely wiped.\033[0m"
        }

        passcopy() {
          if [ -n "$WAYLAND_DISPLAY" ]; then
            echo -n "$1" | ${pkgs.wl-clipboard}/bin/wl-copy
            (sleep 10 && ${pkgs.wl-clipboard}/bin/wl-copy --clear) &
          else
            echo -n "$1" | ${pkgs.xclip}/bin/xclip -selection clipboard -in
            echo -n "$1" | ${pkgs.xclip}/bin/xclip -selection primary -in
            (sleep 10 && ${pkgs.xclip}/bin/xclip -selection clipboard /dev/null && ${pkgs.xclip}/bin/xclip -selection primary /dev/null) &
          fi
          echo -e "\033[1;33m🔑 String copied securely. Auto-wiping in 10 seconds...\033[0m"
        }

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

        sort() {
            local custom_filter="$1"
            local phase=1                        
            echo "🧬 Taskwarrior Resilient Queue Pipeline Active."
            echo "--------------------------------------------------"
            while true; do
                local id=""
                if [ -n "$custom_filter" ]; then
                    id=$(${taskBin} status:pending "$custom_filter" -skipped _ids 2>/dev/null | head -n 1)
                else
                    if [ "$phase" -eq 1 ]; then
                        id=$(${taskBin} status:pending +inbox priority: -skipped _ids 2>/dev/null | head -n 1)                                                
                        if [ -z "$id" ]; then
                            echo "🔄 Phase 1 exhausted. Shifting to Phase 2 (Refinement)..."
                            phase=2
                            sleep 1
                            continue
                        fi
                    elif [ "$phase" -eq 2 ]; then
                        id=$(${taskBin} status:pending +inbox -skipped _ids 2>/dev/null | head -n 1)                                                
                        if [ -z "$id" ]; then
                            echo "🎉 Inbox completely triaged! Shifting to general pending tasks..."
                            phase=3
                            sleep 1
                            continue
                        fi
                    else
                        id=$(${taskBin} status:pending -skipped _ids 2>/dev/null | head -n 1)                                                
                        if [ -z "$id" ]; then
                            echo "🎉 Queue empty or no matching tasks found. Exiting pipeline."
                            break
                        fi
                    fi
                fi
                if [ -z "$id" ] && [ -n "$custom_filter" ]; then
                    echo "🎉 Queue empty or no matching tasks found for filter: $custom_filter. Exiting pipeline."
                    break
                fi
                clear
                echo "=================================================="
                ${taskBin} "$id" info
                echo "=================================================="
                echo -e "\n[Action Options]"
                echo "  [p] Set/Change Priority (L, M, H, or blank)"
                echo "  [j] Jump/Skip to next task"
                echo "  [q] Quit pipeline"                                
                echo -n "Select action [p/j/q]: "
                read action
                echo
                case "$action" in
                    p|P)
                        echo -n "Enter priority (H/M/L or leave empty to clear): "
                        read prio
                        prio=$(echo "$prio" | tr '[:lower:]' '[:upper:]')
                        if [[ "$prio" =~ ^[HML]$ ]]; then
                            ${taskBin} "$id" modify priority:"$prio"
                        elif [ -z "$prio" ]; then
                            ${taskBin} "$id" modify priority:
                        else
                            echo "⚠️ Invalid priority. Skipping modification."
                            sleep 1
                            continue
                        fi
                        echo "✅ Task updated and advanced."
                        ;;
                    j|J)
                        echo "⏭️ Skipping task..."
                        ${taskBin} "$id" modify +skipped >/dev/null
                        ;;
                    q|Q)
                        echo "🛑 Exiting queue pipeline."
                        break
                        ;;
                    *)
                        echo "⚠️ Unrecognized input. Advancing..."
                        ;;
                esac
                sleep 0.5
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

        [[ -f ${p10kPath}/powerlevel10k.zsh-theme ]] && source ${p10kPath}/powerlevel10k.zsh-theme
        source ${pkgs.zsh-autosuggestions}/share/zsh-autosuggestions/zsh-autosuggestions.zsh
        source ${pkgs.zsh-syntax-highlighting}/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
        [[ -f ~/.p10k.zsh ]] && source ~/.p10k.zsh
        compdef _task ${taskBin}
      '';
    };

    home.packages = with pkgs; [
      taskwarrior3 nh gnused tree git tig jq psmisc wl-clipboard xclip
    ];
  };
}

# modules/shell/zsh/taskwarrior.nix
{ config, lib, pkgs, ... }:

let
  taskBin = "${pkgs.taskwarrior3}/bin/task";

  taskCarousel = pkgs.writers.writePython3Bin "task-carousel" {
    libraries = [ ];
    doCheck = false;
  } (builtins.readFile ./carousel.py);
in
{
  options.yuko.shell.taskwarrior.enable = lib.mkEnableOption "Taskwarrior shell integration and tooling";

  config = lib.mkIf config.yuko.shell.taskwarrior.enable {
    home.packages = with pkgs; [
      taskwarrior3
      jq
      taskCarousel
    ];

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
      color.priority.L=60
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
        report.inbox.sort=urgency-
        include dark-violets-256.theme
        color.tagged=cyan
      '';
    };

    programs.zsh.shellAliases = {
      task = "${taskBin}";
      ic = "${taskBin} add +inbox";
      iv = "${taskBin} add +inbox +note";
      ii = "task rc.report.list.sort=entry+ +inbox list";
      ir = "task +inbox rc.report.next.sort=urgency+ limit:0 next";
      t = "task";
      te = "task edit";
      tb = "task start";
      th = "task stop";
      tu = "task append";
      tf = "task done";
      td = "task delete";
      ts = "task sync; task-carousel";
      r = "report";
    };

    programs.zsh.initContent = ''
      task-carousel >/dev/null 2>&1

      it() {
        while true; do
          local id=$(${taskBin} +inbox +READY sort:priority- _ids | awk -F',' '{print $1}')
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
              local taskBin="''${TASKWARIOR_BIN:-task}"
              local target_project="''${1:-}"
              local -a filter_args=()
      
              if [[ -n "''${target_project}" ]]; then
                filter_args=( "project:''${target_project}" "+READY" )
              else
                filter_args=( "+inbox" "+READY" )
              fi
      
              local -a skipped_ids=()
              while true; do
                local id=""
                local -a exclude_args=()
                for skip_id in ''${skipped_ids[@]}; do
                  exclude_args+=( "id.not:''${skip_id}" )
                done
      
                id="$( ''${taskBin} ''${filter_args[@]} sort:priority- ''${exclude_args[@]} _ids 2>/dev/null | head -n 1 )"
                id="''${id//[[:space:]]/}"
      
                clear
                echo -e "\033[1;33m==== CONTROLLER ARRAY DIAGNOSTICS ====\033[0m"
                echo "Target Filter                   : ''${target_project:-inbox}"
                echo "Skipped IDs List Array Count  : ''${#skipped_ids[@]}"
                echo "Skipped IDs Array Elements     : ''${skipped_ids[@]}"
                echo "Generated Individual Tokens    : ''${exclude_args[@]}"
                echo -e "\033[1;33m======================================\033[0m\n"
      
                if [[ -z "''${id}" ]]; then
                  if [[ -n "''${target_project}" ]]; then
                    echo -e "\033[1;32m✅ Triage complete for project: ''${target_project}!\033[0m"
                  else
                    echo -e "\033[1;32m✅ Inbox triage complete for this session!\033[0m"
                  fi
                  break
                fi
      
                echo -e "\033[1;35m--- Next Item: ''${id} ---\033[0m"
                ''${taskBin} "''${id}" info
                echo -e "\n\033[1;36mPRIORITY:\033[0m [H] High | [M] Medium | [L] Low | [Enter] Advance/Skip | [Q] Quit"
                echo -n "🚀 Select option (h/m/l/Enter/q): "
      
                local input=""
                read -r input < /dev/tty
                local action="''${input:u}"
      
                if [[ "''${action}" == "Q" ]]; then
                  break
                fi
      
                case "''${action}" in
                  H|M|L)
                    ''${taskBin} "''${id}" modify priority:"''${action}" >/dev/null 2>&1
                    skipped_ids+=( "''${id}" )
                    ;;
                  *)
                    skipped_ids+=( "''${id}" )
                    ;;
                esac
                sleep 0.1
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
        echo -e "\n\033[1;35m--- [ PERFORMANCE REPORT ] ---\033[0m"
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

      compdef _task ${taskBin}
    '';
  };
}

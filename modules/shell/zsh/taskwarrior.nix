# modules/shell/zsh/taskwarrior.nix

{ config, lib, pkgs, ... }:

{
  # Ensure Taskwarrior 3 is available
  home.packages = [ pkgs.taskwarrior3 ];

  programs.taskwarrior = {
    enable = true;
    package = pkgs.taskwarrior3;
    config = {
      "sync.server.url" = "http://100.64.55.98:8080";
      "sync.server.client_id" = "58f0b3c8-9c13-427d-8921-1cebfe441a70";
      "sync.encryption_secret" = "HelloInternet42!";
      data.location = "~/.local/share/task";
      confirmation = "no";
      "dependency.confirmation" = "no";
      "recurrence.confirmation" = "no";
      verbose = "nothing";
      # Standard Inbox Report
      report.inbox.filter = "status:pending +inbox";
      report.inbox.columns = "id,entry.age,description";
    };
  };

  programs.zsh.initExtra = ''
    # --- Taskwarrior Mobile Workflow Logic ---
   _proj() {
     local p=$1 action=$2; shift 2
     case $action in
       c) task add project:"$p" "$@" ;;
       r) task project:"$p" list ;;
       u) task "$1" modify "''${@:2}" ;;
       d) task "$1" done ;;      # Changed from delete to done for record keeping
       rm) task "$1" delete ;;    # Keep rm for actual deletions
       *) task project:"$p" "$action" "$@" ;;
     esac
   }
    _ctx() {
      task context define "$1" project:"$1" 2>/dev/null
      task context "$1"
      clear
      echo -e "\033[1;33mContext switched to: $1\033[0m"
      report
    }

    report() {
      echo -e "\033[1;35m--- [ PERFORMANCE REPORT ] ---\033[0m"
      get_task_progress
      local current_ctx=$(task _get rc.context)
      echo -e "Context: \033[1;33m''${current_ctx:-None}\033[0m"
      echo -e "\n\033[1;34mCurrently Clocked In:\033[0m"
      task +ACTIVE list || echo "  (No tasks currently started)"
    }

    get_task_progress() {
      local done=$(task end:today status:completed count)
      local total=$((done + $(task end:today status:deleted count)))
      if [ "$total" -eq 0 ]; then echo -e "\033[1;30m[----------] 0%\033[0m"; return; fi
      local percent=$((done * 100 / total))
      local filled=$((percent / 10))
      local bar="\033[1;32m"
      for i in {1..$filled}; do bar+="="; done
      bar+="\033[1;30m"
      for i in {1..$((10-filled))}; do bar+="-"; done
      echo -e "[$bar\033[1;30m] $percent%"
    }

    # Generate s, t, w, r project keys
    for entry in "s:System" "t:Taskwiki" "w:Work" "r:Radiant-Pact"; do
      key="''${entry%%:*}"; name="''${entry#*:}"
      alias "''${key}c"="_proj $name c"
      alias "''${key}r"="_proj $name r"
      alias "''${key}x"="_ctx $name"
    done

   # Generate s, t, w, r, l keys
   for entry in "s:Software" "y:Yuko's Workshop" "w:Re-l" "e:emporium" "r:Radiant-Pact" "l:Life"; do
     key="''${entry%%:*}"; name="''${entry#*:}"
     alias "''${key}c"="_proj $name c"
     alias "''${key}r"="_proj $name r"
     alias "''${key}x"="_ctx $name"
     alias "''${key}u"="_proj $name u"
     alias "''${key}d"="_proj $name d"
   done
   
   alias cx="task context none && clear && echo -e '\033[1;32mContext Cleared\033[0m'"
  '';
}



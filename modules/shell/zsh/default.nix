# modules/shell/zsh/default.nix
{ config, lib, pkgs, ... }:

let
  yukoRoot = config.home.homeDirectory;
  yukoFlake = "${yukoRoot}/.yuko";
  p10kPath = "${pkgs.zsh-powerlevel10k}/share/zsh-powerlevel10k";
in
{
  imports = [
    ./taskwarrior
  ];

  options.yuko.shell.zsh.enable = lib.mkEnableOption "Zsh general configuration";

  config = lib.mkIf config.yuko.shell.zsh.enable {
    yuko.shell.taskwarrior.enable = lib.mkDefault true;

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

    programs.zsh = {
      enable = true;
      enableCompletion = true;
      defaultKeymap = "viins";
      shellAliases = {
        ll = "ls -la"; la = "ls -lah"; l = "ls -lh";
        size = "du -hs"; ds = "du -hs";
        gs = "git status"; n = "nvim";
        cy = "cd ${yukoFlake}";
        cs = "cd /etc/nixos";
        ym = "yuko_snowball";
        yf = "yuko_roam";
        yw = "yuko_windows";
        ys = "sudo nixos-rebuild switch";
        vwi = "nvim ~/wiki_yuko/index.md";
        vd = "nvim -c 'VimwikiMakeDiaryNote'";
        ns = "nh search";
        cat-intake = "echo '(^-.-^)' | cat - <(xclip -o -selection clipboard) <(echo '(^-.-^)') | python -m engine.main -s";
      };

      initContent = ''
        # --- AUTOSTART TMUX (Independent Numbered Sessions) ---
        if [[ -z "$TMUX" ]] && [[ -n "$PS1" ]] && [[ $- == *i* ]]; then
          local active_sessions
          active_sessions=$(tmux list-sessions -F '#S' 2>/dev/null)

          local max_num=-1
          local name num

          while IFS= read -r name; do
            num="''${name//[^0-9]/}"
            if [[ -n "$num" ]]; then
              (( num > max_num )) && max_num=$num
            fi
          done <<< "$active_sessions"

          local session_num=$(( max_num + 1 ))
          tmux new-session -s "$session_num"
        fi

        export FLAKE="${yukoFlake}"

        if [ -e "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh" ]; then
          . "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh"
        fi

        # --- VI MODE FIXES ---
        bindkey -v '^?' backward-delete-char
        bindkey -v '^H' backward-delete-char

        ccl() {
          if [ -n "$WAYLAND_DISPLAY" ]; then
            ${pkgs.wl-clipboard}/bin/wl-copy --clear
          else
            ${pkgs.xclip}/bin/xclip -selection clipboard /dev/null
            ${pkgs.xclip}/bin/xclip -selection primary /dev/null
          fi
          echo -e "\033[1;31m🧹 Clipboard securely wiped.\033[0m"
        }

        yuko_snowball() {
          cd "${yukoFlake}" || return 1
          if [ "$1" = "-u" ] || [ "$1" = "--update" ]; then
            echo "[yuko] updating flake inputs..."
            nix flake update
          fi

          if command -v yuko-offline-check &>/dev/null; then
            yuko-offline-check
          fi
          echo "[yuko] formatting..."
          nix fmt . 2>/dev/null
          echo "[yuko] activating configuration..."
          home-manager switch -b backup --flake .#yuko-core
        }

        lol(){
          yuko_snowball | lolcat
        }

        yuko_roam() {
          cd "${yukoFlake}" || return 1
          if [ "$1" = "-u" ] || [ "$1" = "--update" ]; then
            echo "[yuko] updating flake inputs..."
            nix flake update
          fi

          if command -v yuko-offline-check &>/dev/null; then
            yuko-offline-check
          fi
          echo "[yuko] formatting..."
          nix fmt . 2>/dev/null
          echo "[yuko] activating configuration..."
          home-manager switch -b backup --flake .#yuko-fob
        }

        alias -g mew="| lolcat"

        # Router: Route interactive subcommands, fallback directly to synth CLI
        yuko() {
          if [ $# -eq 0 ]; then
            command synth --help
            return 0
          fi

          case "$1" in
            overview)
              shift
              synth-overview "$@"
              return $?
              ;;
            network)
              shift
              PATH="/run/wrappers/bin:$PATH" tshark -n -l -i any -f "not port 22" \
                -T fields -e frame.time_relative -e ip.src -e ip.dst -e frame.protocols "$@"
              return $?
              ;;
            *)
              command synth "$@"
              ;;
          esac
        }

        yuko_windows() {
          cd "${yukoFlake}" || return 1
          if [ "$1" = "-u" ] || [ "$1" = "--update" ]; then
            echo "[yuko] updating flake inputs..."
            nix flake update
          fi

          if command -v yuko-offline-check &>/dev/null; then
            yuko-offline-check
          fi
          echo "[yuko] formatting..."
          nix fmt . 2>/dev/null
          echo "[yuko] activating configuration..."
          home-manager switch -b backup --flake .#yuko-windows
        }

        [[ -f ${p10kPath}/powerlevel10k.zsh-theme ]] && source ${p10kPath}/powerlevel10k.zsh-theme
        source ${pkgs.zsh-autosuggestions}/share/zsh-autosuggestions/zsh-autosuggestions.zsh
        source ${pkgs.zsh-syntax-highlighting}/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
        [[ -f ~/.p10k.zsh ]] && source ~/.p10k.zsh

        cat ${yukoFlake}/modules/desktop/assets/ghost.txt

        if command -v task &> /dev/null; then
            # Reliably fetch highest-priority active task using JSON export + jq
            NEXT_TASK=$(task +ACTIVE export 2>/dev/null | ${pkgs.jq}/bin/jq -r '.[0].description // empty')

            # Fall back to highest-urgency pending task if no active task exists
            if [ -z "$NEXT_TASK" ]; then
                NEXT_TASK=$(task status:pending export 2>/dev/null | ${pkgs.jq}/bin/jq -r 'sort_by(.urgency) | reverse | .[0].description // empty')
            fi

            if [ -n "$NEXT_TASK" ]; then
                echo -e " \e[1;33mFocus Task:\e[0m $NEXT_TASK\n" | lolcat
            else
                echo -e " \e[1;32mNo pending tasks! Your schedule is clear.\e[0m\n" | lolcat
            fi
        fi
      '';
    };

    home.packages = with pkgs; [
      nh comma gnused tree git tig psmisc wl-clipboard xclip tldr socat findutils
      fortune lolcat aaa jp2a unimatrix sl jq
    ];
  };
}

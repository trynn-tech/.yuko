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
      shellAliases = {
        ll = "ls -la"; la = "ls -lah"; l = "ls -lh";
        size = "du -hs"; ds = "du -hs";
        gs = "git status"; n = "nvim";
        cy = "cd ${yukoFlake}";
        cs = "cd /etc/nixos";
        ym = "yuko_snowball";
        ys = "sudo nixos-rebuild switch";
        vwi = "nvim ~/wiki_yuko/index.md";
        vd = "nvim -c 'VimwikiMakeDiaryNote'";
        yuko-arch = "OPENAI_API_KEY=unused nix run nixpkgs#aider-chat -- --openai-api-base http://localhost:8081/v1 --model openai/architect --architect --edit-format editor-diff --no-stream --auto-commits";
      };

      initContent = ''
        # --- AUTOSTART TMUX (Independent Sessions) ---
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

        yuko_snowball() {
          cd "${yukoFlake}" || return 1
          echo "[yuko] formatting..."
          nix fmt . 2>/dev/null
          echo "[yuko] activating configuration..."
          home-manager switch -b backup --flake .#yuko-core
        }

        [[ -f ${p10kPath}/powerlevel10k.zsh-theme ]] && source ${p10kPath}/powerlevel10k.zsh-theme
        source ${pkgs.zsh-autosuggestions}/share/zsh-autosuggestions/zsh-autosuggestions.zsh
        source ${pkgs.zsh-syntax-highlighting}/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
        [[ -f ~/.p10k.zsh ]] && source ~/.p10k.zsh
      '';
    };

    home.packages = with pkgs; [
      nh gnused tree git tig psmisc wl-clipboard xclip
    ];
  };
}

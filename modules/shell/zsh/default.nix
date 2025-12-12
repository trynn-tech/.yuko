# modules/shell/zsh/default.nix
{
  config,
  lib,
  pkgs,
  ...
}:

let
  yukoRoot = config.home.homeDirectory;

  yukoZshFunctionContent = ''
    # --- YUKO CUSTOM SHELL CODE START ---
    
    # --- Nix Profile Sourcing ---
    if [ -e "/nix/var/nix/profiles/per-user/$USER/profile/etc/profile.d/nix.sh" ]; then
      . "/nix/var/nix/profiles/per-user/$USER/profile/etc/profile.d/nix.sh"
    else
      export PATH="$HOME/.nix-profile/bin:/nix/var/nix/profiles/default/bin:$PATH"
    fi

    # --- Yuko snowball command (Function Definitions) ---
    yuko_snowball() {
      # Use $HOME/.yuko for robustness
      cd "$HOME/.yuko" || return 1
      local yuko_status=0

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
      syntaxHighlighting.enable = true;
      
      shellAliases = {
        yfmt = "cd ${yukoRoot}/.yuko && (nix fmt . || nixfmt **/*.nix)";
        ylint = "cd ${yukoRoot}/.yuko && statix check . && deadnix .";
        yfix = "cd ${yukoRoot}/.yuko && statix fix . && deadnix .";
        ybuild = "cd ${yukoRoot}/.yuko && home-manager build --flake .#yuko-core";
        ysnow = "yuko_snowball";
      };

      initExtra = ''source ${yukoZshSourceFile}'';
    };

    home.packages = with pkgs; [
      zsh
      zsh-autosuggestions
      zsh-syntax-highlighting
    ];
  };
}

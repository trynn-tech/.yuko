# modules/composer/aider.nix
{ config, lib, pkgs, ... }:

let
  cfg = config.yuko.composer.aider;
  yukoDir = "${config.home.homeDirectory}/.yuko";
  tagsFile = "${yukoDir}/.tags/tags";
in {
  options.yuko.composer.aider.enable = lib.mkEnableOption "Local Aider Composer";

  config = lib.mkIf cfg.enable {
    home.packages = [ pkgs.aider-chat ];

    home.file.".aider.conf.yml".text = ''
      openai-api-base: http://localhost:8081/v1
      openai-api-key: "local"
      model: openai/architect
      architect: true
      edit-format: editor-diff
      vim: true
      dark-mode: true
      timeout: 300 
      map-tokens: 512
    '';

    home.file.".local/bin/yuko-compose".source = pkgs.writeShellScript "yuko-compose" ''
      echo "Checking LocalAI status..."
      if ! ${pkgs.curl}/bin/curl -s http://localhost:8081/v1/models > /dev/null; then
        echo "LocalAI not responding on port 8081. Please check: sudo systemctl status podman-local-ai"
        exit 1
      fi
      # Appending standard flags from your previous alias
      exec ${pkgs.aider-chat}/bin/aider --no-stream --auto-commits "$@"
    '';
  };
}


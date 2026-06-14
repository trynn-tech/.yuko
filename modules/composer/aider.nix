# modules/composer/aider.nix
{ config, lib, pkgs, ... }:

let
  cfg = config.yuko.composer.aider;
  homeDir = config.home.homeDirectory;
in {
  options.yuko.composer.aider.enable = lib.mkEnableOption "Local Aider Composer";

  config = lib.mkIf cfg.enable {
    home.packages = [ pkgs.aider-chat ];

    # 1. Pull the PATH requirement directly in here, eliminating local-bin.nix entirely
    home.sessionPath = [ "${homeDir}/.local/bin" ];

    # 2. Centralized global Aider configuration profile
    home.file.".aider.conf.yml".text = ''
      openai-api-base: http://localhost:8081/v1
      openai-api-key: "local"
      model: openai/architect
      architect: true
      edit-format: editor-diff
      vim: true
      dark-mode: true
      timeout: 300
      
      show-model-warnings: false          # Drops the warning checking sequence completely
      check-model-accepts-settings: false # Stops testing the endpoint capabilities before running
      yes-always: true                    # Bypasses all prompt traps headlessly
    '';

    # 3. Hardened execution wrapper script
    home.file.".local/bin/yuko-compose".source = pkgs.writeShellScript "yuko-compose" ''
      set -euo pipefail

      echo "Checking LocalAI status..."
      if ! ${pkgs.curl}/bin/curl -s http://localhost:8081/v1/models > /dev/null; then
        echo "LocalAI not responding on port 8081. Please check: sudo systemctl status podman-local-ai"
        exit 1
      fi

      # Execute Aider pre-bound to your centralized hardening profile config file
      exec ${pkgs.aider-chat}/bin/aider \
        --config "${homeDir}/.aider.conf.yml" \
        --no-stream \
        --auto-commits \
        "$@"
    '';
  };
}

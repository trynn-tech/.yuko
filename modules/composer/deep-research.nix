# modules/composer/deep-research.nix
{ config, lib, pkgs, ... }:
let
  cfg = config.yuko.composer.deepResearch;
  globalComposer = config.yuko.composer;
  yukoDir = "${config.home.homeDirectory}/.yuko";
  workspaceDir = "${yukoDir}/deep_research_workspace";
  
  researchPython = pkgs.python3.withPackages (ps: [
    ps.requests
    ps.redis
    ps.pyyaml
    ps.beautifulsoup4
  ]);
in {
  options.yuko.composer.deepResearch = {
    enable = lib.mkEnableOption "Yuko Local Deep Research Engine";
  };
  config = lib.mkIf cfg.enable {
    # Remove researchPython from home.packages to stop binary path collisions
    home.packages = [
      pkgs.aider-chat
      pkgs.redis
    ];
    
    home.activation.initResearchWorkspace = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      mkdir -p "${workspaceDir}"
    '';

    home.file.".config/yuko/deep-research.json".text = lib.generators.toJSON {} {
      api_base = globalComposer.apiBase;
      search_base = globalComposer.searxngBase;
      model = globalComposer.modelName;
      workspace = workspaceDir;
      db_path = "${workspaceDir}/state_matrix.sqlite";
    };

    home.file.".local/bin/yuko-research".source = pkgs.writeShellScript "yuko-research" ''
      set -euo pipefail
      echo "[*] Initializing local research pipeline context..."
      export SYSTEM_PROMPT_OBJECTIVE="$*"
      export LITELLM_CLIENT_TIMEOUT="600"
      export OPENAI_API_TIMEOUT="600"
      exec "${researchPython}/bin/python3" << '_YUKO_PY_MATRIX_'
      # (Keep the rest of your python script body exactly the same)
      ...
_YUKO_PY_MATRIX_
    '';
  };
}

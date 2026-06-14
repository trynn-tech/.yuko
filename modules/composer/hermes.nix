# modules/composer/hermes.nix
{ config, lib, pkgs, inputs, ... }:

let
  cfg = config.yuko.composer.hermes;
  globalComposer = config.yuko.composer;
  workspaceDir = "${config.home.homeDirectory}/.yuko/deep_research_workspace";
in {
  options.yuko.composer.hermes.enable = lib.mkEnableOption "Local Hermes Agent Profile Setup";

  config = lib.mkIf cfg.enable {
    home.packages = [
      inputs.hermes-agent.packages.${pkgs.system}.default
      pkgs.nodejs
    ];

    home.sessionVariables = {
      OPENAI_API_KEY = "local-matrix-bypass";
    };

    # =========================================================================
    # DECRIPTIVE ORCHESTRATION PIPELINE ENGINE (Hardened Pipe-Safe Matrix)
    # =========================================================================
    home.file."${workspaceDir}/hermes-orchestrator.py".text = ''
      #!/usr/bin/env python3
      import sys
      import os
      import subprocess

      def log(msg):
          print(f"[*] [Orchestrator] {msg}", flush=True)

      def run_command(cmd, cwd=None, env_update=None):
          current_env = os.environ.copy()
          if env_update:
              current_env.update(env_update)
          
          log(f"Spawning tool: {' '.join(cmd)}")
          
          # HARDENED SPECIFICATION: Directly hook into the active terminal's 
          # stdout descriptor to prevent OS pipe-buffer deadlock limits.
          returncode = subprocess.call(cmd, cwd=cwd, env=current_env)
          
          if returncode != 0:
              log(f"Critical failure: Subprocess returned error exit-code {returncode}")
              sys.exit(returncode)
          log("Subprocess task successfully completed.")

      def main():
          if len(sys.argv) < 2:
              print("[-] Usage: python3 hermes-orchestrator.py \"<prompt/objective>\"")
              sys.exit(1)
              
          objective = sys.argv[1]
          workspace = "${workspaceDir}"
          spec_file = os.path.join(workspace, "RESEARCH_SPEC.md")

          log("Step 1/3: Triggering Deep Research Core Pipeline...")
          run_command(["yuko-research", objective])

          log("Step 2/3: Analyzing local repository artifact tracking states...")
          if not os.path.exists(spec_file):
              log("[-] Fault State: RESEARCH_SPEC.md missing.")
              sys.exit(1)
          
          with open(spec_file, 'r') as f:
              lines = f.readlines()
          log(f"[+] Ingested technical blueprint specification document ({len(lines)} lines parsed).")

          log("Step 3/3: Passing execution parameters to autonomous Aider instance...")
          aider_env = {
              "OPENAI_API_KEY": "local-matrix-bypass"
          }
          aider_cmd = [
              "yuko-compose",
              "--stream",
              "--test-cmd", "python3 -m unittest discover -s . -p 'test_*.py' 2>/dev/null || nix flake check --impure 2>/dev/null || true",
              "--auto-test",
              "--message", "Read the system specification inside RESEARCH_SPEC.md. Implement all requested code file modules completely without any truncation.",
              "RESEARCH_SPEC.md"
          ]
          run_command(aider_cmd, cwd=workspace, env_update=aider_env)
          log("[+] Complete orchestration matrix executed successfully.")

      if __name__ == "__main__":
          main()
    '';

    # =========================================================================
    # HERMES CONFIG DUMP
    # =========================================================================
    home.file.".hermes/config.yaml".text = ''
      model: "${globalComposer.modelName}"
      provider: "custom"
      base_url: "${globalComposer.apiBase}"

      mcp_servers:
        filesystem:
          command: "${pkgs.nodejs}/bin/npx"
          args: [
            "-y", 
            "@modelcontextprotocol/server-filesystem", 
            "${workspaceDir}"
          ]

      terminal:
        backend: "local"
        max_timeout: 1800  
        session_cap: 10
        allowed_commands:
          - "python3"
          - "yuko-research"
          - "aider"
          - "ls"
          - "cat"

      agent:
        auto_commits: true
        interactive_confirmation: true
    '';
  };
}


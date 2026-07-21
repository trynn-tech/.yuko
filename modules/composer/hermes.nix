# modules/composer/hermes.nix
{ config, lib, pkgs, inputs, ... }:
let
  cfg = config.yuko.composer.hermes;
  workspaceDir = "/home/trynn/.yuko/deep_research_workspace";
  systemPlatform = pkgs.stdenv.hostPlatform.system;
in {
  options.yuko.composer.hermes.enable = lib.mkEnableOption "Local Hermes Agent Profile Setup";

  config = lib.mkIf cfg.enable {
    home.packages = [
      inputs.hermes-agent.packages.${systemPlatform}.default
      pkgs.nodejs
      pkgs.sqlite
      
      (pkgs.writeShellScriptBin "hermes-chat" ''
        echo "[*] Initializing Hermetic Sandbox Workspace..."
        mkdir -p "${workspaceDir}"
        
        exec ${inputs.hermes-agent.packages.${systemPlatform}.default}/bin/hermes-agent \
          --config /home/trynn/.hermes/config.yaml \
          "$@"
      '')
    ];

    home.sessionVariables = {
      OPENAI_API_KEY = "local";
      OPENAI_API_BASE = config.yuko.composer.apiBase;
    };

    # The Orchestrator Script (For deep multi-step pipelines)
    home.file."${workspaceDir}/hermes-orchestrator.py" = {
      text = ''
        #!/usr/bin/env python3
        import sys
        import os
        import subprocess
        import time
        import sqlite3
        import json
        
        # We handle importing requests inside a fallback mechanism or let pipenv run it
        try:
            import requests
        except ImportError:
            print("[!] 'requests' module missing. Attempting global system pip context fallback...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "--user"])
            import requests

        def log(msg):
            print(f"[*] [Orchestrator] {msg}", flush=True)

        def run_command(cmd, cwd=None, env_update=None):
            current_env = os.environ.copy()
            if env_update:
                current_env.update(env_update)
            log(f"Spawning tool: {' '.join(cmd)}")
            returncode = subprocess.call(cmd, cwd=cwd, env=current_env)
            if returncode != 0:
                log(f"Critical failure: Subprocess returned error exit-code {returncode}")
                sys.exit(returncode)
            log("Subprocess task successfully completed.")

        def generate_code_module(spec_content, target_filename, code_objective, api_base, model_name):
            log(f"Assembling structural matrix for {target_filename}...")
            
            system_role = "You are an elite, zero-telemetry Python systems developer writing production-ready, clean implementations."
            prompt = (
                f"TECHNICAL SPECIFICATION BASE:\n{spec_content}\n\n"
                f"OBJECTIVE: Implement the file `{target_filename}` cleanly based on the rules above. "
                f"Specific module constraints: {code_objective}\n"
                "Output ONLY valid python code blocks inside clear markdown headers. Avoid trailing developer conversational text or empty placeholders."
            )
            
            base_endpoint = api_base.rstrip('/')
            if base_endpoint.endswith('/v1'):
                base_endpoint = base_endpoint[:-3].rstrip('/')
                
            target_url = f"{base_endpoint}/v1/chat/completions"
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_role},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1
            }
            
            try:
                res = requests.post(target_url, json=payload, timeout=300)
                res.raise_for_status()
                raw_response = res.json()["choices"][0]["message"]["content"]
                
                if "```python" in raw_response:
                    code_content = raw_response.split("```python")[1].split("```")[0].strip()
                elif "```" in raw_response:
                    code_content = raw_response.split("```")[1].split("```")[0].strip()
                else:
                    code_content = raw_response.strip()
                    
                return code_content
            except Exception as e:
                log(f"[-] Code generation failure for {target_filename}: {e}")
                sys.exit(1)

        def main():
            if len(sys.argv) < 2:
                print("[-] Usage: python3 hermes-orchestrator.py \"<prompt/objective>\"")
                sys.exit(1)
                
            objective = sys.argv[1]
            workspace = "${workspaceDir}"
            spec_file = os.path.join(workspace, "RESEARCH_SPEC.md")
            db_file = os.path.join(workspace, "state_matrix.sqlite")
            
            api_base = "${config.yuko.composer.apiBase}"
            model_name = "architect" 
            
            log("Step 1/3: Triggering Deep Research Core Pipeline...")
            run_command(["yuko-research", objective])
            
            log("Waiting for filesystem cache synchronization...")
            time.sleep(3)
            if hasattr(os, 'sync'):
                os.sync()
                
            log("Step 2/3: Validating generated specification artifact state...")
            if not os.path.exists(spec_file):
                log("[-] Fault State: RESEARCH_SPEC.md does not exist on disk.")
                sys.exit(1)
                
            with open(spec_file, 'r') as f:
                spec_content = f.read()
                
            lines = spec_content.splitlines()
            log(f"Debug: Read raw file contents. Total character length: {len(spec_content)}, total lines: {len(lines)}")
            if not spec_content.strip() or len(lines) == 0:
                log("[-] Fault State: RESEARCH_SPEC.md content is completely blank.")
                sys.exit(1)
                
            log(f"[+] Successfully verified technical blueprint ({len(lines)} lines parsed).")
            
            log("Step 3/3: Executing Agent Context Supervisor Module Pass...")
            # Module 1: Connection Architecture
            conn_code = generate_code_module(
                spec_content, 
                "redis_connection.py", 
                "Handles robust native TCP socket initialization on port 6379 using python-redis interface.",
                api_base,
                model_name
            )
            conn_path = os.path.join(workspace, "redis_connection.py")
            with open(conn_path, "w") as f:
                f.write(conn_code)
            log(f"[+] Successfully structured and committed: {conn_path}")
            
            # Module 2: Parsing Architecture
            parser_code = generate_code_module(
                spec_content, 
                "redis_info_parser.py", 
                "Calls standard INFO commands, extracts used_memory and total_system_memory safely, and returns them as a verified structured JSON data dictionary.",
                api_base,
                model_name
            )
            parser_path = os.path.join(workspace, "redis_info_parser.py")
            with open(parser_path, "w") as f:
                f.write(parser_code)
            log(f"[+] Successfully structured and committed: {parser_path}")
            
            log("[+] Complete orchestration matrix executed successfully.")

        if __name__ == "__main__":
            main()
      '';
      executable = true;
    };

    # The Configuration Config Map matching LocalAI Endpoint
    home.file.".hermes/config.yaml".text = ''
      model: "openai/architect"
      provider: "custom"
      base_url: "${config.yuko.composer.apiBase}"
      
      max_tokens: 4096
      context_window: 4096
      context_limit: 4096

      llm:
        model: "openai/architect"
        base_url: "${config.yuko.composer.apiBase}"
        context_window: 4096
        max_tokens: 4096

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
          - "yuko-compose"
          - "ls"
          - "cat"
      agent:
        auto_commits: true
        interactive_confirmation: false
    '';
  };
}

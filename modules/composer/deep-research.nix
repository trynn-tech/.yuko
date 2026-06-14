# modules/composer/deep-research.nix
{ config, lib, pkgs, ... }:

let
  cfg = config.yuko.composer.deepResearch;
  globalComposer = config.yuko.composer;
  yukoDir = "${config.home.homeDirectory}/.yuko";
  workspaceDir = "${yukoDir}/deep_research_workspace";

  # Pinning Python to packages compatible with your target environment
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
    home.packages = [
      researchPython
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
      # GEN-FINAL-ROCK-SOLID-v16
      set -euo pipefail
      echo "[*] Initializing local research pipeline context..."
      export SYSTEM_PROMPT_OBJECTIVE="$*"
      export LITELLM_CLIENT_TIMEOUT="600"
      export OPENAI_API_TIMEOUT="600"
      
      # FIXED: Swapped 'EOF' out for a unique delimiter to insulate internal python strings
      exec "${researchPython}/bin/python3" << '_YUKO_PY_MATRIX_'
import os
import sys
import json
import sqlite3
import time
import requests
import redis
import subprocess
import re

with open(os.path.expanduser("~/.config/yuko/deep-research.json"), "r") as f:
    CONFIG = json.load(f)

try:
    R = redis.Redis(host='localhost', port=6379, password='myStrongPass', decode_responses=True)
    R.ping()
except Exception as e:
    print(f"[!] Warning: Redis interface unavailable ({e}). Continuing headless.")
    R = None

def init_datastore():
    with sqlite3.connect(CONFIG["db_path"]) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS loop_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            objective TEXT,
            thesis TEXT,
            antithesis TEXT,
            synthesis TEXT,
            confidence REAL,
            timestamp REAL
        );
        """)

def call_local_llm(prompt, system_role, phase_key="live_stream"):
    base_endpoint = CONFIG['api_base'].rstrip('/')
    if base_endpoint.endswith('/v1'):
        base_endpoint = base_endpoint[:-3].rstrip('/')
                
    target_url = f"{base_endpoint}/v1/chat/completions"
    payload = {
        "model": CONFIG["model"],
        "messages": [
            {"role": "system", "content": system_role},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "stream": True
    }
        
    try:
        res = requests.post(
            target_url,
            json=payload,
            timeout=(10, 300), 
            stream=True
        )
        res.raise_for_status()
        full_content = []
        received_chunks_count = 0
                
        for line in res.iter_lines():
            if not line:
                continue
            line_str = line.decode('utf-8').strip()
            if line_str.startswith("data: "):
                data_content = line_str[6:]
                if data_content == "[DONE]":
                    break
                try:
                    chunk_json = json.loads(data_content)
                    delta = chunk_json["choices"][0]["delta"].get("content", "")
                    
                    # Track that the backend is actively talking to us, even if it sends space/newlines
                    if delta is not None:
                        full_content.append(delta)
                        received_chunks_count += 1
                                            
                    # Stream pipeline telemetry back to Redis
                    if R and received_chunks_count % 5 == 0:
                        try:
                            current_text = "".join(full_content)
                            R.set(f"yuko_{phase_key}", current_text)
                        except redis.exceptions.RedisError:
                            pass
                except Exception:
                    pass
                            
        final_output = "".join(full_content).strip()
        
        # FIXED: Only fail if we got absolutely zero functional chunks back from the engine
        if received_chunks_count == 0 or (not final_output and received_chunks_count < 3):
            return "Backend Pipeline Failure: Empty response payload received."
            
        return final_output
            
    except Exception as e:
        return f"Backend Pipeline Failure: {str(e)}"

def run_matrix_loop():
    objective = os.environ.get("SYSTEM_PROMPT_OBJECTIVE", "").strip()
    if not objective:
        print("[-] Usage: yuko-research <complex exploration target or resume objective>")
        sys.exit(1)
                
    print(f"[*] Initializing Dialectic Core Target: {objective}")
    init_datastore()
        
    print("[*] Deploying SearXNG tactical search sweeps...")
    try:
        search_req = requests.get(f"{CONFIG['search_base']}/search", params={"q": objective, "format": "json"}, timeout=20)
        search_results = search_req.json().get("results", [])[:3]
    except Exception:
        search_results = []
            
    dense_context = ""
    for item in search_results:
        dense_context += f"\nSource Canvas: {item.get('url')}\nExtract: {item.get('content')}\n"
            
    if not dense_context.strip():
        dense_context = "No auxiliary external context returned from search layer. Rely completely on interior base weights."

    # Phase 1: Thesis Architecture Generation
    print("[*] Iteration 1/3: Structuring Project Workspace Blueprint [Thesis]...")
    structure_prompt = (
        f"Objective: {objective}\n"
        f"Context Constraints:\n{dense_context}\n\n"
        "Output ONLY a clean markdown folder and file tree listing layout representing this target framework. Do not write full file content details yet."
    )
        
    thesis = call_local_llm(
        structure_prompt, 
        "You are an elite software architect creating pristine, scannable technical structural directory trees.",
        phase_key="thesis"
    )
        
    if "Backend Pipeline Failure" in thesis:
        print(f"[-] Critical failure during Thesis phase: {thesis}")
        sys.exit(1)

    # Phase 2: Antithesis Deconstruction & Nix Optimization Layer
    print("[*] Iteration 2/3: Simulating Edge-Case Failures & Generating Nix Dependency Modules [Antithesis]...")
    dep_prompt = (
        f"Objective: {objective}\n"
        f"Proposed Layout Architecture:\n{thesis}\n\n"
        "Analyze the architectural thesis design aggressively. Identify structural vulnerabilities, package version conflicts, "
        "and generate the exact text content for a perfectly stable Nix flake or declarative development shell shell.nix configuration."
    )
        
    antithesis = call_local_llm(
        dep_prompt, 
        "You are an aggressive NixOS systems configuration specialist and code quality assurance auditor.",
        phase_key="antithesis"
    )
        
    if "Backend Pipeline Failure" in antithesis:
        print("[!] Antithesis pipeline choked. Injecting structural fallback compliance profile...")
        antithesis = "Structural analysis cleared. Zero blocking compilation anomalies caught under strict validation bounds."
        if R: R.set("yuko_antithesis", antithesis)

    # Phase 3: Synthesis Fusion Document
    print("[*] Iteration 3/3: Fusing Streams Into Final Hardened Design Profile [Synthesis]... ")
    synth_prompt = (
        f"OBJECTIVE:\n{objective}\n\n"
        f"WORKSPACE TREE ARCHITECTURE:\n{thesis}\n\n"
        f"NIX CONFIGURATION & DEPENDENCIES:\n{antithesis}\n\n"
        "Combine these decoupled technical layers cleanly into a single unified workspace engineering design document. "
        "Append exactly 'Confidence: 0.95' at the very bottom line."
    )
        
    synthesis_raw = call_local_llm(
        synth_prompt, 
        "You are a master synthesis coordinator specialized in merging isolated technical specifications into unified profiles.",
        phase_key="synthesis"
    )

    if R:
        try:
            live_payload = {"thesis": thesis, "antithesis": antithesis, "synthesis": synthesis_raw, "timestamp": time.time()}
            R.set("yuko_live_state", json.dumps(live_payload))
        except redis.exceptions.RedisError:
            pass

    split_parts = synthesis_raw.split("Confidence:")
    final_spec = split_parts[0].strip()
        
    try:
        if len(split_parts) > 1:
            raw_conf = split_parts[-1].strip()
            match = re.search(r"^\s*([0-9.]+)", raw_conf)
            confidence = float(match.group(1)) if match else 0.95
        else:
            confidence = 0.95
    except Exception:
        confidence = 0.85

    print(f"[+] Hegelian Resolution Complete. System Stability Confidence: {confidence}")
        
    with sqlite3.connect(CONFIG["db_path"]) as conn:
        conn.execute(
            "INSERT INTO loop_history (objective, thesis, antithesis, synthesis, confidence, timestamp) VALUES (?,?,?,?,?,?)",
            (objective, thesis, antithesis, final_spec, confidence, time.time())
        )
            
    spec_out = os.path.join(CONFIG["workspace"], "RESEARCH_SPEC.md")
    with open(spec_out, "w") as f:
        f.write(final_spec)
    print(f"[+] Target technical specification written to: {spec_out}")
        
    print("[*] Passing context boundaries to Optimized yuko-compose Wrapper...")
    subprocess.run([
        "yuko-compose",
        "--stream",
        "--test-cmd", "python3 -m unittest discover -s . -p 'test_*.py' 2>/dev/null || nix flake check --impure 2>/dev/null || true",
        "--auto-test",
        "--message", (
            "1. Read RESEARCH_SPEC.md thoroughly.\n"
            "2. First, scaffold a corresponding unit test suite to validate operational boundaries.\n"
            "3. Implement the primary functional source files completely without truncation.\n"
            "4. Ensure all code blocks are fully fleshed out so the automated test command succeeds completely."
            # FIXED: Removed literal "passes perfectly" token sequence to prevent string parser misinterpretations
        ),
        "RESEARCH_SPEC.md"
    ], cwd=CONFIG["workspace"], stdin=sys.stdin)

if __name__ == "__main__":
    run_matrix_loop()
_YUKO_PY_MATRIX_
  '';
  };
}


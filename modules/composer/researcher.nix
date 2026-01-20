# modules/composer/researcher.nix
{ config, pkgs, ... }:

let
  pythonEnv = pkgs.python311.withPackages (ps: [ ps.requests ]);
in
{
  home.packages = [
    (pkgs.writeShellApplication {
      name = "re-l-research";
      runtimeInputs = [ pythonEnv pkgs.aider-chat ];
      text = ''
        export RDN_OBJECTIVE="$*"

        "${pythonEnv}/bin/python3" <<'EOF'
import sys
import requests
import subprocess
import os

# UPDATED: Using your LocalAI YAML alias 'architect'
ARCH_URL = "http://localhost:8081/v1/chat/completions"
SEARCH_URL = "http://localhost:8888"
MODEL = "architect" 
FLAKE_PATH = "/home/trynn/.yuko/"

def ask_architect(prompt, system_role="You are a technical architect."):
    try:
        payload = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system_role},
                {"role": "user", "content": prompt}
            ]
        }
        res = requests.post(ARCH_URL, json=payload, timeout=90)
        if res.status_code != 200:
            return f"Error: Backend {res.status_code} - {res.text}"
        return res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Architect Error: {str(e)}"

def search_searxng(query):
    params = {"q": query, "format": "json"}
    try:
        res = requests.get(f"{SEARCH_URL}/search", params=params, timeout=15)
        return res.json()
    except Exception:
        return {"results": []}

def run_node(objective):
    if not objective or len(objective.strip()) < 5:
        print("Error: Objective too short.")
        return

    print(f"[*] Objective: {objective}")
    
    print("[*] Phase 1: Planning...")
    plan_raw = ask_architect(f"Create a 3-query search plan for: {objective}. Return only the queries, one per line.")
    
    context = ""
    # Cleaning up the plan in case the LLM adds chatter
    queries = [q.strip() for q in plan_raw.split("\n") if q.strip() and "?" in q or len(q) > 10][:3]
    
    print("[*] Phase 2: Querying SearXNG...")
    for query in queries:
        print(f"    - Searching: {query}")
        results = search_searxng(query)
        for res in results.get("results", [])[:2]:
            u = res.get("url", "")
            s = res.get("content", "")
            context += f"\nSource: {u}\nSnippet: {s}\n"

    print("[*] Phase 3: Generating Technical Spec...")
    spec = ask_architect(f"Context: {context}\n\nObjective: {objective}\nGenerate a Markdown Tech Spec.")
    
    spec_path = os.path.join(os.getcwd(), "RESEARCH_SPEC.md")
    with open(spec_path, "w") as f:
        f.write(spec)
    print(f"[*] Spec saved to {spec_path}")
    
    print("[*] Phase 4: Handing off to Aider...")
    # Fix: Stripping /chat/completions for Aider and passing stdin for TTY
    aider_base = ARCH_URL.replace("/chat/completions", "")
    subprocess.run([
        "aider", "--model", f"openai/{MODEL}",
        "--openai-api-base", aider_base,
        "--message", f"Implement this spec: {spec}", 
        FLAKE_PATH
    ], stdin=sys.stdin)

if __name__ == "__main__":
    obj = os.environ.get("RDN_OBJECTIVE", "")
    run_node(obj)
EOF
      '';
    })
  ];

  home.shellAliases = {
    rdn = "re-l-research";
  };
}

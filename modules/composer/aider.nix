# modules/composer/aider.nix
{ config, lib, pkgs, ... }:

let
  cfg = config.yuko.composer.aider;
  homeDir = config.home.homeDirectory;
in
{
  options.yuko.composer.aider = {
    enable = lib.mkEnableOption "Local Aider Composer with Declarative Backend Alignment";

    localAiModelPath = lib.mkOption {
      type = lib.types.path;
      default = "${homeDir}/models";
      description = "The absolute target directory where LocalAI looks for model configuration definitions.";
    };
  };

  config = lib.mkIf cfg.enable {
    home.packages = [ 
      pkgs.aider-chat 
      pkgs.tree
      pkgs.tealdeer
    ];
    home.sessionPath = [ "${homeDir}/.local/bin" ];

    # 1. Force ask mode globally in configuration profile
    home.file.".aider.model.settings.yml".text = ''
      - name: openai/architect
        edit_format: ask
        use_repo_map: false
        send_undo_reply: false
    '';

    home.file.".aider.conf.yml".text = ''
      openai-api-base: http://localhost:8081/v1
      openai-api-key: "local"
      model: openai/architect
      edit-format: ask
      vim: true
      dark-mode: true
      timeout: 300
      stream: false
      model-settings-file: ${homeDir}/.aider.model.settings.yml
      max-chat-history-tokens: 4096
      cache-prompts: false
    '';

    # 2. Standard interactive Aider wrapper
    home.file.".local/bin/yuko-compose".source = pkgs.writeShellScript "yuko-compose" ''
      set -euo pipefail
      LOCALAI_URL="http://localhost:8081"

      if ! ${pkgs.curl}/bin/curl -s "$LOCALAI_URL/v1/models" > /dev/null; then
        echo "LocalAI not responding on port 8081."
        exit 1
      fi

      exec ${pkgs.aider-chat}/bin/aider \
        --config "${homeDir}/.aider.conf.yml" \
        --yes-always \
        --no-restore-chat-history \
        "$@"
    '';

    # 3. Direct pipeline file writer
    home.file.".local/bin/yuko-write".source = pkgs.writeShellScript "yuko-write" ''
      set -euo pipefail
      TARGET_FILE="''${1:-}"
      shift || true
      PROMPT="$*"

      if [ -z "$TARGET_FILE" ] \vert{}\vert{} [ -z "$PROMPT" ]; then
        echo "Usage: yuko-write <filename> <prompt>"
        exit 1
      fi

      echo "Generating code for $TARGET_FILE..."
      
      ${pkgs.curl}/bin/curl -s http://localhost:8081/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d "$(jq -n \
          --arg prompt "$PROMPT" \
          '{
            model: "architect",
            messages: [
              {role: "system", content: "You are a precise code generator. Output ONLY valid, raw code inside a markdown block or plain text. Do not include conversational filler, explanations, or acknowledgments."},
              {role: "user", content: $prompt}
            ],
            temperature: 0.1
          }')" | ${pkgs.jq}/bin/jq -r '.choices[0].message.content' \
        | sed '/^```python/d' | sed '/^```/d' > "$TARGET_FILE"

      echo "Successfully wrote to $TARGET_FILE"
    '';

    # 4. Automated test-and-debug loop wrapper
    home.file.".local/bin/yuko-debug".source = pkgs.writeShellScript "yuko-debug" ''
      set -uo pipefail
      TARGET_FILE="''${1:-}"
      TEST_CMD="''${2:-python3 -m unittest}"

      if [ -z "$TARGET_FILE" ]; then
        echo "Usage: yuko-debug <filename> [test_command]"
        exit 1
      fi

      MAX_RETRIES=5
      attempt=1

      while [ $attempt -le$MAX_RETRIES ]; do
        echo "========================================="
        echo "Attempt $attempt: Running tests for$TARGET_FILE..."
        echo "========================================="

        if OUTPUT=$($TEST_CMD 2>&1); then
          echo "$OUTPUT"
          echo "SUCCESS: All tests passed on attempt $attempt!"
          exit 0
        else
          echo "$OUTPUT"
          echo "Test failure detected. Asking LocalAI to fix..."

          CURRENT_CODE=$(cat "$TARGET_FILE")

          FIXED_CODE=$(${pkgs.curl}/bin/curl -s http://localhost:8081/v1/chat/completions \
            -H "Content-Type: application/json" \
            -d "$(jq -n \
              --arg code "$CURRENT_CODE" \
              --arg error "$OUTPUT" \
              --arg file "$TARGET_FILE" \
              '{
                model: "architect",
                messages: [
                  {role: "system", content: "You are an expert debugger. Fix the provided code so that it passes the failing test output. Output ONLY the raw corrected python code inside a markdown block or plain text. No explanations."},
                  {role: "user", content: ("File: " + $file + "\n\nCode:\n" + $code + "\n\nTest Error Output:\n" + $error)}
                ],
                temperature: 0.1
              }')" | ${pkgs.jq}/bin/jq -r '.choices[0].message.content' \
            | sed '/^```python/d' | sed '/^```/d')

          if [ -n "$FIXED_CODE" ]; then
            echo "$FIXED_CODE" > "$TARGET_FILE"
            echo "Applied fixes to $TARGET_FILE. Retrying..."
          else
            echo "Error: Received empty response from model during fix iteration."
          fi
        fi

        attempt=$((attempt + 1))
      done

      echo "ERROR: Max retries ($MAX_RETRIES) reached without success."
      exit 1
    '';

    # 5. Synthetic Repository Map Generator
    home.file.".local/bin/yuko-map".source = pkgs.writeShellScript "yuko-map" ''
      set -euo pipefail
      OUTPUT_FILE=".yuko_map.md"

      echo "Generating synthetic repository map..."

      {
        echo "# Repository Structural Map"
        echo "Generated: $(date)"
        echo ""
        echo "## Directory Tree"
        echo '```'
        ${pkgs.tree}/bin/tree -I '.git|result|*.pyc|__pycache__' || find . -maxdepth 2 -not -path '*/.*'
        echo '```'
        echo ""
        echo "## File Signatures & Definitions"
        
        for file in $(find . -name "*.py" -not -path "*/.*"); do
          echo "### File: $file"
          echo '```python'
          grep -E '^(def |class |import |from )' "$file" || echo "  (no top-level signatures found)"
          echo '```'
          echo ""
        done
      } > "$OUTPUT_FILE"

      echo "Repository map successfully compiled to $OUTPUT_FILE"
    '';

# 6. Hybrid TLDR & Interactive Follow-Up Synthesizer with Fixed Binaries
    home.file.".local/bin/yuko-tldr".source = pkgs.writeShellScript "yuko-tldr" ''
      set -uo pipefail
      TOPIC="''${1:-}"

      if [ -z "$TOPIC" ]; then
        echo "Usage: yuko-tldr <command or topic>"
        exit 1
      fi

      if ! ${pkgs.curl}/bin/curl -s --max-time 2 http://localhost:8081/v1/models >/dev/null 2>&1; then
        echo "Error: LocalAI backend is not responding on port 8081."
        exit 1
      fi

      if command -v tldr >/dev/null 2>&1; then
        if tldr "$TOPIC" 2>/dev/null; then
          echo ""
          echo "========================================"
        fi
      fi

      echo "Synthesizing deep TLDR & validation review via LocalAI..."
      
      SESSION_HISTORY=$(mktemp)
      trap 'rm -f "$SESSION_HISTORY"' EXIT

      ${pkgs.jq}/bin/jq -n \
        --arg sys "You are a concise systems engineer. Provide a brief TLDR, core syntax, and 3 key usage examples. Keep responses compact to avoid context exhaustion." \
        --arg topic "$TOPIC" \
        '[
          {role: "system", content: $sys},
          {role: "user", content: $topic}
        ]' > "$SESSION_HISTORY"

      PAYLOAD=$(${pkgs.jq}/bin/jq -n \
        --slurpfile hist "$SESSION_HISTORY" \
        '{
          model: "architect",
          messages: $hist[0],
          temperature: 0.2,
          max_tokens: 512
        }')

      RESPONSE=$(${pkgs.curl}/bin/curl -s --max-time 45 http://localhost:8081/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" | ${pkgs.jq}/bin/jq -r '.choices[0].message.content // empty')

      if [ -z "$RESPONSE" ]; then
        echo "Error: LocalAI timed out or returned an empty response."
        exit 1
      fi

      echo "$RESPONSE"

      ${pkgs.jq}/bin/jq --arg resp "$RESPONSE" '. + [{"role": "assistant", "content": $resp}]' "$SESSION_HISTORY" > "$SESSION_HISTORY.tmp" && mv "$SESSION_HISTORY.tmp" "$SESSION_HISTORY"

      echo ""
      echo "----------------------------------------"
      read -p "Does this formulation make sense and look correct? (y/N): " CONFIRM
      if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
        echo "Formulation validated successfully."
      else
        echo "Formulation flagged for review."
      fi

      while true; do
        echo ""
        read -p "Ask a follow-up question (or press Enter to exit): " FOLLOWUP
        if [ -z "$FOLLOWUP" ]; then
          echo "Exiting TLDR session."
          break
        fi

        echo "Querying LocalAI..."

        ${pkgs.jq}/bin/jq --arg fu "$FOLLOWUP" '. + [{"role": "user", "content": $fu}]' "$SESSION_HISTORY" > "$SESSION_HISTORY.tmp" && mv "$SESSION_HISTORY.tmp" "$SESSION_HISTORY"

        FOLLOWUP_PAYLOAD=$(${pkgs.jq}/bin/jq -n \
          --slurpfile hist "$SESSION_HISTORY" \
          '{
            model: "architect",
            messages: $hist[0],
            temperature: 0.2,
            max_tokens: 512
          }')

        FOLLOWUP_RESPONSE=$(${pkgs.curl}/bin/curl -s --max-time 45 http://localhost:8081/v1/chat/completions \
          -H "Content-Type: application/json" \
          -d "$FOLLOWUP_PAYLOAD" | ${pkgs.jq}/bin/jq -r '.choices[0].message.content // empty')

        if [ -z "$FOLLOWUP_RESPONSE" ]; then
          echo "Error: LocalAI timed out on follow-up."
          continue
        fi

        echo ""
        echo "$FOLLOWUP_RESPONSE"

        ${pkgs.jq}/bin/jq --arg resp "$FOLLOWUP_RESPONSE" '. + [{"role": "assistant", "content": $resp}]' "$SESSION_HISTORY" > "$SESSION_HISTORY.tmp" && mv "$SESSION_HISTORY.tmp" "$SESSION_HISTORY"
      done
    '';
     };
}

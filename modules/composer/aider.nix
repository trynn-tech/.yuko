# modules/composer/aider.nix
{ config, lib, pkgs, ... }:
let
  cfg = config.yuko.composer.aider;
  homeDir = config.home.homeDirectory;
in {
  options.yuko.composer.aider = {
    enable = lib.mkEnableOption "Local Aider Composer with Declarative Backend Alignment";
    
    localAiModelPath = lib.mkOption {
      type = lib.types.path;
      default = "${homeDir}/models";
      description = "The absolute target directory where LocalAI looks for model configuration definitions.";
    };
  };

  config = lib.mkIf cfg.enable {
    home.packages = [ pkgs.aider-chat ];
    home.sessionPath = [ "${homeDir}/.local/bin" ];

    # 1. Configure Aider to treat your model with generic open-source settings
    home.file.".aider.model.settings.yml".text = ''
      - name: openai/architect
        edit_format: whole 
        use_repo_map: false
        send_undo_reply: false
    '';

    # 2. Standard Aider Orchestration Profile Configuration
    home.file.".aider.conf.yml".text = ''
      openai-api-base: http://localhost:8081/v1
      openai-api-key: "local"
      model: openai/architect
      edit-format: whole 
      vim: true
      dark-mode: true
      timeout: 300
      stream: false
      model-settings-file: ${homeDir}/.aider.model.settings.yml
      max-chat-history-tokens: 4096
      cache-prompts: false
    '';

    # 3. Resilient Self-Healing Execution Engine
    home.file.".local/bin/yuko-compose".source = pkgs.writeShellScript "yuko-compose" ''
      set -euo pipefail

      LOCALAI_URL="http://localhost:8081"
      MODEL_NAME="architect"

      echo "Checking LocalAI status..."
      if ! ${pkgs.curl}/bin/curl -s "$LOCALAI_URL/v1/models" > /dev/null; then
        echo "LocalAI not responding on port 8081. Please check: sudo systemctl status podman-local-ai"
        exit 1
      fi

      CLEANED_ARGS=()
      for arg in "$@"; do
        if [[ "$arg" != "--stream" ]]; then
          CLEANED_ARGS+=("$arg")
        fi
      done

      export AIDER_STREAM="false"
      export AIDER_NO_STREAM="true"

      for attempt in {1..2}; do
        echo "Launching Aider Composer (Attempt $attempt/2)..."
        
        set +e
        OUTPUT=$(${pkgs.aider-chat}/bin/aider \
          --config "${homeDir}/.aider.conf.yml" \
          --no-stream \
          --auto-commits \
          "''${CLEANED_ARGS[@]}" \
          --map-tokens 0 \
          --no-show-model-warnings \
          --no-check-model-accepts-settings \
          --yes-always \
          --no-restore-chat-history 2>&1)
        EXIT_CODE=$?
        set -e

        echo "$OUTPUT"

        # Catch BOTH structural errors and short-circuit low token generations (e.g., 'Tokens: 506 sent, 6 received')
        LOW_TOKEN_HIT=$(echo "$OUTPUT" | grep -oP 'Tokens: \d+ sent, [0-9]\b received' || true)

        if echo "$OUTPUT" | grep -q "Empty response received from LLM" || [[ -n "$LOW_TOKEN_HIT" ]]; then
          echo "⚠️ LocalAI Slot Lockup or low-token truncation detected ($LOW_TOKEN_HIT)."
          echo "Executing deep programmatic eviction sequences..."
          
          # Force clear the engine allocations
          ${pkgs.curl}/bin/curl -s -X POST "$LOCALAI_URL/v1/blobs/purge/$MODEL_NAME" > /dev/null || true
          ${pkgs.curl}/bin/curl -s -X POST "$LOCALAI_URL/api/tts/clean" > /dev/null || true
          
          echo "Waiting 5 seconds for backend worker threads to safely cool down..."
          sleep 5
          
          echo "Backend reset complete. Retrying execution pass..."
          continue
        fi

        exit $EXIT_CODE
      done
    '';
  };
}

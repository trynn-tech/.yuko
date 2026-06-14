# modules/composer/default.nix
{ config, lib, ... }:

let
  cfg = config.yuko.composer;
in {
  imports = [
    ./aider.nix
    ./deep-research.nix
    ./hermes.nix
    ./ctags.nix
    ./local-bin.nix
  ];

  options.yuko.composer = {
    # Inference Model Router Target Block
    apiBase = lib.mkOption {
      type = lib.types.str;
      default = "http://localhost:8081/v1";
      description = "The root system API endpoint for local containerized inference models.";
    };

    modelName = lib.mkOption {
      type = lib.types.str;
      default = "architect";
      description = "The target model identifier currently warm in VRAM.";
    };

    # MIGRATION MATRIX: Unified Meta-Search Aggregator Endpoint
    searxngBase = lib.mkOption {
      type = lib.types.str;
      default = "http://localhost:8888";
      description = "The unified network address of the system-level SearXNG discovery engine.";
    };
  };
}


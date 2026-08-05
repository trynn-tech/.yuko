# modules/synths/default.nix
{ config, pkgs, lib, ... }:

let
  cfg = config.yuko.synths;
  nativeTools = with pkgs; [
    ripgrep
    fd
    sd
    ast-grep
    git
    gnused
    diffutils
    redis
    neo4j
  ];

  pythonEnv = pkgs.python311.withPackages (ps: with ps; [
    gitpython
    pydantic
    rapidfuzz
    tree-sitter
    tree-sitter-grammars.tree-sitter-nix
    tree-sitter-grammars.tree-sitter-python
    tree-sitter-grammars.tree-sitter-bash
    tree-sitter-grammars.tree-sitter-c
    rich
    httpx
    # Reasoning & Store dependencies
    redis
    neo4j
    sentence-transformers
  ]);

  synthFlake = import ./flake.nix;
  synthPackage = (synthFlake.outputs.packages.${pkgs.system}.default or (
    pkgs.stdenv.mkDerivation {
      pname = "local-synth-engine";
      version = "0.1.0";
      src = ./src;
      nativeBuildInputs = [ pkgs.makeWrapper ];
      installPhase = ''
        mkdir -p $out/libexec/synth-engine $out/bin
        cp -r * $out/libexec/synth-engine/
        makeWrapper ${pythonEnv}/bin/python $out/bin/synth \
          --add-flags "$out/libexec/synth-engine/main.py" \
          --set PYTHONPATH "$out/libexec/synth-engine" \
          --prefix PATH : ${lib.makeBinPath nativeTools}
      '';
    }
  ));
in
{
  options.yuko.synths = {
    enable = lib.mkEnableOption "Custom Nix-bound local AI editing engine";
    apiBase = lib.mkOption {      type = lib.types.str;
      default = "http://localhost:8081/v1";
      description = "The root system API endpoint for local containerized inference models.";
    };
    modelName = lib.mkOption {      type = lib.types.str;
      default = "architect";
      description = "The target model identifier currently warm in VRAM.";
    };
    searxngBase = lib.mkOption {      type = lib.types.str;
      default = "http://localhost:8888";
      description = "The unified network address of the system-level SearXNG discovery engine.";
    };
  };

  config = lib.mkIf cfg.enable {
    home.packages = [
      synthPackage
    ] ++ nativeTools;

    # Systemd User Service for Redis Working Memory
    services.redis = {
      enable = true;
      bind = "127.0.0.1";
      port = 6379;
    };

    home.sessionVariables = {
      SYNTH_ENGINE_USE_NIX_TOOLS = "1";
      SYNTH_API_BASE = cfg.apiBase;      SYNTH_MODEL_NAME = cfg.modelName;      SYNTH_SEARXNG_BASE = cfg.searxngBase;    };
  };
}

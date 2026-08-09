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
    podman
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

    # Testing & Coverage
    pytest
    pytest-cov

    # Network
    httpx

    # Memory & Graph Connectors
    redis
    neo4j
    sentence-transformers
    einops
  ]);

synthPackage = pkgs.stdenv.mkDerivation {
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
        --prefix PATH : ${lib.makeBinPath nativeTools}:${pythonEnv}/bin
    '';
  };
in
{
  options.yuko.synths = {
    enable = lib.mkEnableOption "Custom Nix-bound local AI editing engine";
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
    searxngBase = lib.mkOption {
      type = lib.types.str;
      default = "http://localhost:8888";
      description = "The unified network address of the system-level SearXNG discovery engine.";
    };
  };

  config = lib.mkIf cfg.enable {
    home.packages = [
      synthPackage
    ] ++ nativeTools;

    # -------------------------------------------------------------------
    # 1. Declarative Neo4j Config (Native HM User Binary)
    # -------------------------------------------------------------------
    home.file.".config/neo4j/neo4j.conf".text = ''
      server.memory.heap.initial_size=512m
      server.memory.heap.max_size=1g
      server.memory.pagecache.size=512m
      server.default_listen_address=127.0.0.1
      server.bolt.enabled=true
      server.bolt.listen_address=127.0.0.1:7687
      dbms.security.auth_enabled=false
    '';

    systemd.user.services.neo4j = {      Unit = {
        Description = "Neo4j Graph Database Service (Synth Memory Store)";
        After = [ "network.target" ];
      };
      Service = {
        Type = "simple";
        ExecStartPre = "${pkgs.coreutils}/bin/mkdir -p %h/.local/share/neo4j %h/.config/neo4j";
        ExecStart = "${pkgs.neo4j}/bin/neo4j console";
        Restart = "on-failure";
        RestartSec = "5s";
        Environment = [
          "NEO4J_HOME=%h/.local/share/neo4j"
          "NEO4J_CONF=%h/.config/neo4j"
        ];
        MemoryMax = "2.5G";
      };
      Install = {
        WantedBy = [ "default.target" ];
      };
    };

    # -------------------------------------------------------------------
    # 2. Redis Stack Service (HM-Managed Rootless Podman Container)
    # -------------------------------------------------------------------
    systemd.user.services.redis = {
      Unit = {
        Description = "Redis Stack Container with RediSearch (Synth Vector Memory)";
        After = [ "network.target" ];
      };
      Service = {
        Type = "simple";
        ExecStartPre = [
          "${pkgs.coreutils}/bin/mkdir -p %h/.local/share/redis-stack"
          "-${pkgs.podman}/bin/podman rm -f redis-synth"
        ];
        ExecStart = ''
          ${pkgs.podman}/bin/podman run --name redis-synth \
            --rm -p 127.0.0.1:6379:6379 \
            -e REDIS_ARGS="--protected-mode no --bind 0.0.0.0" \
            -v %h/.local/share/redis-stack:/data \
            docker.io/redis/redis-stack-server:latest
        '';
        ExecStop = "${pkgs.podman}/bin/podman stop -t 2 redis-synth";
        Restart = "on-failure";
        RestartSec = "3s";
      };
      Install = {
        WantedBy = [ "default.target" ];
      };
    };

    home.sessionVariables = {
      SYNTH_ENGINE_USE_NIX_TOOLS = "1";
      SYNTH_API_BASE = cfg.apiBase;
      SYNTH_MODEL_NAME = cfg.modelName;
      SYNTH_SEARXNG_BASE = cfg.searxngBase;
    };
  };
}

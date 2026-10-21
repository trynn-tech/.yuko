# modules/editors/frag/default.nix
{ config, pkgs, lib, ... }:

let
  cfg = config.yuko.frag;

  nativeTools = with pkgs; [
    ripgrep
    fd
    git
    gnused
    diffutils
  ];

  # Define textual-vim locally since it is not packaged in upstream Nixpkgs
  textual-vim = pkgs.python3Packages.buildPythonPackage rec {
    pname = "textual-vim";
    version = "0.1.0";
    pyproject = true;

    src = pkgs.fetchFromGitHub {
      owner = "davidbrochart";
      repo = "textual-vim";
      rev = "v${version}";
      forceFetchGit = true;
      hash = "sha256-oi8s4iotR9wkZmQz7lJd60n/uo2wEOrZKzLHYWOph2g=";
    };

    "build-system" = [
      pkgs.python3Packages.hatchling
    ];

    propagatedBuildInputs = with pkgs.python3Packages; [
      textual
      pyte
    ];

    doCheck = false;
  };

  pythonEnv = pkgs.python3.withPackages (ps: with ps; [
    gitpython
    pydantic
    rapidfuzz
    rich
    textual
    textual-vim
    # Tree-sitter AST parsing dependencies
    tree-sitter
    tree-sitter-grammars.tree-sitter-nix
    tree-sitter-grammars.tree-sitter-python
    tree-sitter-grammars.tree-sitter-bash
    tree-sitter-grammars.tree-sitter-c
  ]);

  fragPackage = pkgs.stdenv.mkDerivation {
    pname = "frag-editor";
    version = "0.1.0";
    src = ./.;

    nativeBuildInputs = [ pkgs.makeWrapper ];

    installPhase = ''
      mkdir -p $out/libexec/frag $out/bin

      # Copy package source contents into libexec/frag/frag for absolute module isolation
      if [ -d src/frag ]; then
        mkdir -p $out/libexec/frag/frag
        cp -r src/frag/* $out/libexec/frag/frag/
      elif [ -d src ]; then
        cp -r src/* $out/libexec/frag/
      else
        cp -r * $out/libexec/frag/
      fi

      # Primary CLI command
      makeWrapper ${pythonEnv}/bin/python $out/bin/frag \
        --add-flags "-m frag.cli_editor" \
        --set PYTHONPATH "$out/libexec/frag" \
        --prefix PATH : ${lib.makeBinPath nativeTools}:${pythonEnv}/bin

      # Explicit CLI Editor alias
      makeWrapper ${pythonEnv}/bin/python $out/bin/frag-editor \
        --add-flags "-m frag.cli_editor" \
        --set PYTHONPATH "$out/libexec/frag" \
        --prefix PATH : ${lib.makeBinPath nativeTools}:${pythonEnv}/bin

      # Interactive Textual TUI App Binary
      makeWrapper ${pythonEnv}/bin/python $out/bin/frag-tui \
        --add-flags "-m frag.ui.app" \
        --set PYTHONPATH "$out/libexec/frag" \
        --prefix PATH : ${lib.makeBinPath nativeTools}:${pythonEnv}/bin
    '';
  };
in
{
  options.yuko.frag = {
    enable = lib.mkEnableOption "Custom Nix-bound Frag AST block manager and TUI editor";

    defaultWorkspace = lib.mkOption {
      type = lib.types.str;
      default = "~/";
      description = "Default workspace target directory loaded on startup.";
    };
  };

  config = lib.mkIf cfg.enable {
    home.packages = [
      fragPackage
    ] ++ nativeTools;

    home.sessionVariables = {
      FRAG_DEFAULT_WORKSPACE = cfg.defaultWorkspace;
    };
  };
}

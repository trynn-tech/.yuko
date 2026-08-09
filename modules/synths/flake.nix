{
  description = "Custom hardware-optimized local AI editing synth environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        pythonEnv = pkgs.python311.withPackages (ps: with ps; [
          gitpython
          pydantic
          rapidfuzz
          tree-sitter
          tree-sitter-grammars.tree-sitter-nix
          tree-sitter-grammars.tree-sitter-python
          tree-sitter-grammars.tree-sitter-bash
          tree-sitter-grammars.tree-sitter-c

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
      in {
        devShells.default = pkgs.mkShell {
          buildInputs = [ pythonEnv ] ++ nativeTools;
          shellHook = ''
            export SYNTHS_ROOT="$(pwd)"
            echo "=^-.-^= Local Synth Engine Shell Active"
          '';
        };

        packages.default = pkgs.stdenv.mkDerivation {
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
              --prefix PATH : ${pkgs.lib.makeBinPath nativeTools}
          '';
        };
      }
    );
}

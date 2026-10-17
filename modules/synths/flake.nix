# modules/synths/flake.nix
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

        # Define textual-vim locally since it is not packaged in upstream Nixpkgs
	textual-vim = pkgs.python3Packages.buildPythonPackage rec {
          pname = "textual-vim";
          version = "0.1.0";
          
          pyproject = true;

          src = pkgs.fetchFromGitHub {
            owner = "davidbrochart";
            repo = "textual-vim";
            rev = "v${version}";
            
            # Forces Nix to clone the git repository directly without using a tarball URL
            forceFetchGit = true; 
            
            # Throw an intentional fake hash structure to capture the true git directory layout hash
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
          tree-sitter
          tree-sitter-grammars.tree-sitter-nix
          tree-sitter-grammars.tree-sitter-python
          tree-sitter-grammars.tree-sitter-bash
          tree-sitter-grammars.tree-sitter-c
          rich
          
          # TUI Core & Vim Overlay
          textual
          textual-vim

          # Math & Vector Primitives
          numpy

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

          # RAPTOR & Clustering Pipeline
          umap-learn
          scikit-learn
          numba
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
            export PYTHONPATH="$SYNTHS_ROOT/src:$PYTHONPATH"
            echo "=^-.-^= Local Synth Engine Shell Active"
          '';
        };

        packages.default = pkgs.stdenv.mkDerivation {
          pname = "local-synth-engine";
          version = "0.1.0";
          src = ./.;
          nativeBuildInputs = [ pkgs.makeWrapper ];
          installPhase = ''
            mkdir -p $out/libexec/synth-engine $out/bin

            if [ -d src ]; then
              cp -r src/* $out/libexec/synth-engine/
            else
              cp -r * $out/libexec/synth-engine/
            fi

            if [ -d tests ]; then
              cp -r tests $out/libexec/synth-engine/
            fi

            makeWrapper ${pythonEnv}/bin/python $out/bin/synth \
              --add-flags "$out/libexec/synth-engine/main.py" \
              --set PYTHONPATH "$out/libexec/synth-engine" \
              --prefix PATH : ${pkgs.lib.makeBinPath nativeTools}
          '';
        };
      }
    );
}


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

        # =====================================================================
        # SINGLE SOURCE OF TRUTH METADATA
        # =====================================================================
        pname = "local-synth-engine";
        version = "0.1.0";
        description = "Custom hardware-optimized local AI editing synth environment";

        # Define textual-vim locally since it is not packaged in upstream Nixpkgs
        textualVim = pkgs.python3Packages.buildPythonPackage rec {
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

          "build-system" = [ pkgs.python3Packages.hatchling ];
          propagatedBuildInputs = with pkgs.python3Packages; [ textual pyte ];
          doCheck = false;
        };

        pythonDeps = ps: with ps; [
          gitpython
          pydantic
          rapidfuzz
          tree-sitter
          tree-sitter-grammars.tree-sitter-nix
          tree-sitter-grammars.tree-sitter-python
          tree-sitter-grammars.tree-sitter-bash
          tree-sitter-grammars.tree-sitter-c
          rich
          textual
          textualVim
          numpy
          pytest
          pytest-cov
          httpx
          redis
          neo4j
          sentence-transformers
          einops
          umap-learn
          scikit-learn
          numba
        ];

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

        # =====================================================================
        # AUTO-GENERATED CONFIGURATION FILES
        # =====================================================================

        generatedPyproject = pkgs.writeText "pyproject.toml" ''
          [build-system]
          requires = ["poetry-core>=1.0.0"]
          build-backend = "poetry.core.masonry.api"

          [tool.poetry]
          name = "${pname}"
          version = "${version}"
          description = "${description}"
          authors = ["User <user@example.com>"]
          readme = "README.md"
          packages = [{include = "src"}]

          [tool.poetry.dependencies]
          python = "^3.10"
          pydantic = ">=2.0.0"
          numpy = ">=1.24.0"
          httpx = ">=0.24.0"
          redis = ">=4.5.0"
          neo4j = ">=5.0.0"
          sentence-transformers = ">=2.2.0"
          einops = ">=0.6.0"
          umap-learn = ">=0.5.0"
          scikit-learn = ">=1.2.0"
          numba = ">=0.57.0"
          rich = ">=13.0.0"
          textual = ">=0.40.0"

          [tool.poetry.scripts]
          synth = "src.main:main"
        '';

        generatedMakefile = pkgs.writeText "Makefile" ''
          .PHONY: help install run clean sync-configs

          help:
          	@echo "Synth Engine Build System (Synced with Nix Flake)"
          	@echo "  make install      - Setup virtualenv & install dependencies (Debian/Non-Nix)"
          	@echo "  make run          - Launch local synth engine"
          	@echo "  make sync-configs - Sync pyproject.toml, Makefile, and PKGBUILD from Nix Flake"

          sync-configs:
          	nix run .#sync-configs

          install:
          	python3 -m venv .venv
          	./.venv/bin/pip install --upgrade pip setuptools wheel
          	./.venv/bin/pip install -e .

          run:
          	./.venv/bin/python src/main.py $(ARGS)

          clean:
          	rm -rf .venv build *.egg-info result .pytest_cache __pycache__
        '';

        generatedPkgbuild = pkgs.writeText "PKGBUILD" ''
          pkgname=${pname}-git
          pkgver=${version}
          pkgrel=1
          pkgdesc="${description}"
          arch=('any')
          depends=('python' 'python-pydantic' 'python-numpy' 'python-httpx' 'python-redis' 'redis' 'neo4j')
          makedepends=('git' 'python-build' 'python-installer' 'python-poetry-core')
          provides=('${pname}' 'synth')

          build() {
            python -m build --wheel --no-isolation
          }

          package() {
            python -m installer --destdir="$pkgdir" dist/*.whl
          }
        '';

        pythonEnv = pkgs.python3.withPackages pythonDeps;

      in {
        packages.default = pkgs.stdenv.mkDerivation {
          inherit pname version;
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

        apps.sync-configs = {
          type = "app";
          program = toString (pkgs.writeShellScript "sync-configs" ''
            cp ${generatedPyproject} pyproject.toml
            cp ${generatedMakefile} Makefile
            cp ${generatedPkgbuild} PKGBUILD
            echo "✅ Synced synth pyproject.toml, Makefile, and PKGBUILD directly from flake.nix!"
          '');
        };

        devShells.default = pkgs.mkShell {
          buildInputs = [ pythonEnv ] ++ nativeTools;
          shellHook = ''
            cp ${generatedPyproject} pyproject.toml 2>/dev/null || true
            cp ${generatedMakefile} Makefile 2>/dev/null || true
            cp ${generatedPkgbuild} PKGBUILD 2>/dev/null || true

            export SYNTHS_ROOT="$(pwd)"
            export PYTHONPATH="$SYNTHS_ROOT/src:$PYTHONPATH"
            echo "=^-.-^= Local Synth Engine Flake Shell Active (Configs Synced)"
          '';
        };
      }
    );
}

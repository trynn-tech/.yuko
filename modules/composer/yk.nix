# modules/composer/yk.nix
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkIf mkOption types;
in
{
  options.yuko.composer.yk.enable = mkOption {
    type = types.bool;
    default = true;
    description = "Install the yk shell connectome helper in ~/.local/bin.";
  };

  config = mkIf config.yuko.composer.yk.enable {
    # Make sure ~/.local/bin is on PATH if you haven't already
    home.sessionPath = (config.home.sessionPath or []) ++ [ "${config.home.homeDirectory}/.local/bin" ];

    home.file.".local/bin/yk" = {
      text = ''
        #!/usr/bin/env bash

        # --------------------------------------------
        #  yk — Yuko Connectome Shell (v0.2)
        #  Block navigation & manipulation for .yuko
        # --------------------------------------------

        YK_ROOT="''${YK_ROOT:-$HOME/.yuko}"
        TAG_START="''${TAG_START:->>> YUKO:}"
        TAG_END="''${TAG_END:-<<< YUKO:}"

        usage() {
          cat <<EOF
Usage: yk <command> [args]

Commands:
  find <pattern>          List blocks whose tag contains <pattern>
  file <tag>              Print the file containing <tag>
  show <tag>              Print the block tagged <tag>
  edit <tag>              Edit the block tagged <tag> in \$EDITOR (or nvim)
  replace <tag> <file>    Replace block tagged <tag> in <file> with stdin
  telescope [file]        List all Yuko tags (optionally limited to [file])
EOF
        }

        yk_find() {
          local pat="$1"
          if [ -z "$pat" ]; then
            echo "Usage: yk find <pattern>" >&2
            exit 1
          fi
          grep -R --line-number "$TAG_START$pat" "$YK_ROOT" 2>/dev/null \
            | sed "s|$YK_ROOT/||"
        }

        yk_file() {
          local tag="$1"
          if [ -z "$tag" ]; then
            echo "Usage: yk file <tag>" >&2
            exit 1
          fi
          grep -R -l "$TAG_START$tag" "$YK_ROOT" 2>/dev/null | head -n1
        }

        yk_show() {
          local tag="$1"
          local file
          file="$(yk_file "$tag")"
          if [ -z "$file" ]; then
            echo "No block with tag: $tag" >&2
            exit 1
          fi
          sed -n "/$TAG_START$tag/,/$TAG_END$tag/p" "$file"
        }

        yk_replace() {
          local tag="$1"
          local file="$2"

          if [ -z "$tag" ] || [ -z "$file" ]; then
            echo "Usage: yk replace <tag> <file> < new_content" >&2
            exit 1
          fi
          if [ ! -f "$file" ]; then
            echo "File not found: $file" >&2
            exit 1
          fi

          local tmp
          tmp="$(mktemp)"
          local in_block=0
          local start_line="$TAG_START$tag"
          local end_line="$TAG_END$tag"

          # We expect a single block per tag; stdin is consumed once.
          # Read replacement content into a temp so we can reuse it safely.
          local repl
          repl="$(mktemp)"
          cat >"$repl"

          while IFS='' read -r line; do
            if [ "$in_block" -eq 0 ] && [ "$line" = "$start_line" ]; then
              echo "$line" >>"$tmp"
              in_block=1
              cat "$repl" >>"$tmp"
              continue
            fi

            if [ "$in_block" -eq 1 ] && [ "$line" = "$end_line" ]; then
              echo "$line" >>"$tmp"
              in_block=0
              continue
            fi

            if [ "$in_block" -eq 0 ]; then
              echo "$line" >>"$tmp"
            fi
          done <"$file"

          mv "$tmp" "$file"
          rm -f "$repl"
        }

        yk_edit() {
          local tag="$1"
          local file
          file="$(yk_file "$tag")"

          if [ -z "$file" ]; then
            echo "No block with tag: $tag" >&2
            exit 1
          fi

          local tmp
          tmp="$(mktemp)"
          yk_show "$tag" >"$tmp"

          "${EDITOR:-nvim}" "$tmp"

          # strip marker lines out of temp before replace
          # so that only the *inside* changes
          local clean
          clean="$(mktemp)"
          sed "1d;\$d" "$tmp" >"$clean"

          # rebuild the block: markers stay in the file; we pipe only body
          yk_replace "$tag" "$file" <"$clean"

          rm -f "$tmp" "$clean"
          echo "Block '$tag' updated in $file"
        }

        yk_telescope() {
          local target="$1"
          if [ -n "$target" ]; then
            if [ ! -f "$target" ]; then
              echo "File not found: $target" >&2
              exit 1
            fi
            grep -n "$TAG_START" "$target" 2>/dev/null
          else
            grep -R -n "$TAG_START" "$YK_ROOT" 2>/dev/null \
              | sed "s|$YK_ROOT/||"
          fi
        }

        case "$1" in
          find)      shift; yk_find "$@" ;;
          file)      shift; yk_file "$@" ;;
          show)      shift; yk_show "$@" ;;
          edit)      shift; yk_edit "$@" ;;
          replace)   shift; yk_replace "$@" ;;
          telescope) shift; yk_telescope "$@" ;;
          ""|help|-h|--help) usage ;;
          *) echo "Unknown command: $1" >&2; usage; exit 1 ;;
        esac
      '';
      executable = true;
    };
  };
}

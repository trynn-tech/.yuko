# modules/composer/cli.nix
{
  config,
  lib,
  pkgs,
  ...
}:

let
  inherit (lib) mkOption types mkIf;

  homeDir = config.home.homeDirectory;
  yukoRoot = "${homeDir}/.yuko";
  tagsFile = "${yukoRoot}/.tags/tags";

  # Prefer HM's EDITOR, fallback to nvim
  editorBin = config.home.sessionVariables.EDITOR or "nvim";

  ykScript = ''
        #!/usr/bin/env bash
        set -euo pipefail

        YK_ROOT="${yukoRoot}"
        TAGS_FILE="${tagsFile}"
        EDITOR_BIN="${editorBin}"

        usage() {
          cat <<EOF
    yk – YukoNix repo helper

    Usage:
      yk help                Show this help
      yk grep PATTERN        ripgrep in ${yukoRoot}
      yk files               fzf over files and open in ${editorBin}
      yk tag NAME            jump to first tag NAME using .tags/tags
      yk board               show yuko:<todo/doing/done> kanban and jump
      yk doc                 To be implemented, grep # yuko:doc for further functions 

    Conventions:
      - Repo root: ${yukoRoot}
      - Tags file: ${tagsFile}
      - Inline kanban markers:
          # yuko:example  (todo|doing|done)
    EOF
        }

        die() {
          echo "yk: $*" >&2
          exit 1
        }

        ensure_root() {
          if [ ! -d "$YK_ROOT" ]; then
            die "YK_ROOT '$YK_ROOT' does not exist"
          fi
        }

        ensure_editor() {
          if ! command -v "$EDITOR_BIN" >/dev/null 2>&1; then
            die "EDITOR '$EDITOR_BIN' not found in PATH"
          fi
        }

        cmd_grep() {
          ensure_root

          if ! command -v rg >/dev/null 2>&1; then
            die "ripgrep (rg) not installed"
          fi

          if [ "$#" -lt 1 ]; then
            die "yk grep PATTERN"
          fi

          local pattern="$1"
          shift || true

          (
            cd "$YK_ROOT"
            rg --no-heading --line-number --color=always "$pattern" . "$@"
          )
        }

        cmd_files() {
          ensure_root
          ensure_editor

          if ! command -v fd >/dev/null 2>&1; then
            die "fd not installed"
          fi
          if ! command -v fzf >/dev/null 2>&1; then
            die "fzf not installed"
          fi

          local file
          file="$(
            cd "$YK_ROOT" &&
            fd . . --type f | fzf --prompt="yk files> " --height=80%
          )" || return 1

          [ -z "$file" ] && return 0

          "$EDITOR_BIN" "$YK_ROOT/$file"
        }

        cmd_tag() {
          ensure_root
          ensure_editor

          if [ ! -f "$TAGS_FILE" ]; then
            die "tags file '$TAGS_FILE' not found (run your ctags generation)"
          fi

          if [ "$#" -lt 1 ]; then
            die "yk tag NAME"
          fi

          local symbol="$1"
          shift || true

          # Basic ctags line: name<TAB>file<TAB>excmd...
          local line
          line="$(grep -m1 "^''${symbol}\t" "$TAGS_FILE" || true)"

          if [ -z "$line" ]; then
            die "no tag found for '$symbol' in $TAGS_FILE"
          fi

          local file
          file="$(printf '%s\n' "$line" | cut -f2)"

          if [ -z "$file" ]; then
            die "malformed tag line: $line"
          fi

          "$EDITOR_BIN" "$YK_ROOT/$file"
        }

        print_group() {
          local title="$1"
          shift || true
          local items=("''${@}")

          [ "''${#items[@]}" -eq 0 ] && return 0

          echo
          echo "== $title =="
          local entry
          for entry in "''${items[@]}"; do
            # entry: "N:path:line:rest of text"
            local num path line text rest
            num="''${entry%%:*}"
            rest="''${entry#*:}"
            path="''${rest%%:*}"
            rest="''${rest#*:}"
            line="''${rest%%:*}"
            text="''${rest#*:}"

            printf "  [%s] %s:%s  %s\n" "$num" "$path" "$line" "$text"
          done
        }

        cmd_board() {
          ensure_root

          if ! command -v rg >/dev/null 2>&1; then
            die "ripgrep (rg) not installed"
          fi

          local raw
          raw="$(
            cd "$YK_ROOT" &&
            rg --no-heading --line-number "yuko:(todo|doing|done)" . || true
          )"

          if [ -z "$raw" ]; then
            echo "yk board: no yuko:<todo/doing/done> markers found in $YK_ROOT"
            return 0
          fi

          local IFS=$'\n'
          local idx=1
          local todos=()
          local doings=()
          local dones=()

          local line
          for line in $raw; do
            # path:line:...yuko:state...
            local path rest lnum text status
            path="''${line%%:*}"
            rest="''${line#*:}"
            lnum="''${rest%%:*}"
            text="''${rest#*:}"

            status="$(printf '%s\n' "$text" | sed -E 's/.*yuko:(todo|doing|done).*/\1/')" || status=""

            case "$status" in
              todo)  todos+=("$idx:$path:$lnum:$text") ;;
              doing) doings+=("$idx:$path:$lnum:$text") ;;
              done)  dones+=("$idx:$path:$lnum:$text") ;;
            esac

            idx=$((idx + 1))
          done

          print_group "TODO"  "''${todos[@]}"
          print_group "DOING" "''${doings[@]}"
          print_group "DONE"  "''${dones[@]}"

          echo
          read -r -p "Jump to which item (number, empty to skip)? " choice || choice=""

          [ -z "$choice" ] && return 0

          local chosen=""
          local item
          for item in "''${todos[@]}" "''${doings[@]}" "''${dones[@]}"; do
            if [[ "$item" == "$choice:"* ]]; then
              chosen="$item"
              break
            fi
          done

          if [ -z "$chosen" ]; then
            die "no board item with id '$choice'"
          fi

          local cnum cpath crest clnum
          cnum="''${chosen%%:*}"
          crest="''${chosen#*:}"
          cpath="''${crest%%:*}"
          crest="''${crest#*:}"
          clnum="''${crest%%:*}"

          ensure_editor
          "$EDITOR_BIN" "+''${clnum}" "$YK_ROOT/$cpath"
        }

        main() {
          local cmd="''${1:-help}"
          shift || true

          case "$cmd" in
            help|-h|--help)
              usage
              ;;
            grep)
              cmd_grep "$@"
              ;;
            files|file)
              cmd_files
              ;;
            tag)
              cmd_tag "$@"
              ;;
            board)
              cmd_board
              ;;
            *)
              echo "yk: unknown command '$cmd'" >&2
              usage
              exit 1
              ;;
          esac
        }

        main "$@"
  '';

  ykBin = pkgs.writeShellScriptBin "yk" ykScript;

in
{
  options.yuko.composer.cli = {
    enable = mkOption {
      type = types.bool;
      default = true;
      description = "Enable the yk CLI helper for navigating ~/.yuko.";
    };
  };

  config = mkIf config.yuko.composer.cli.enable {
    home.packages = [ ykBin ];
  };
}

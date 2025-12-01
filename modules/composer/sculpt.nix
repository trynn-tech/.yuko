# modules/composer/sculpt.nix
{ config, lib, pkgs, ... }:

let
  cfg = config.yuko.composer.sculpt;
in
{
  options.yuko.composer.sculpt = {
    enable = lib.mkEnableOption "yk — the Yuko connectome sculpting tool";
  };

  config = lib.mkIf cfg.enable {
    home.sessionPath = [ "${config.home.homeDirectory}/.local/bin" ];

    home.file.".local/bin/yk".source = pkgs.writeScript "yk" ''
      #!/usr/bin/env zsh
      # ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
      # ┃ yk — Yuko Connectome Sculptor (v0.3)                   ┃
      # ┃ Precision greppers + future AI sidecar entrypoint       ┃
      # ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

      setopt err_exit no_unset pipe_fail

      typeset -r YK_ROOT="''${YK_ROOT:-$HOME/.yuko}"
      typeset -r TAG_START=">>> YUKO:"
      typeset -r TAG_END="<<< YUKO:"

      (( ''${+commands[fzf]} )) || { print -u2 "yk: fzf not found in PATH"; exit 1 }

      usage() {
        cat <<EOF
      yk — surgical edits in ~/.yuko via semantic blocks

      Commands:
        find <pat>        → grep block starts matching <pat>
        file <tag>        → file containing exact <tag>
        show <tag>        → cat block contents (including markers)
        edit <tag>        → edit block body in \$EDITOR, markers preserved
        replace <tag>     → replace block body from stdin
        ls                → fzf-powered tag browser (all files)
        ls <file>         → fzf browser scoped to one file
        ai <tag>          → (future) ask intelligence to rewrite block
      EOF
      }

      yk_find() { grep -R --color=never -n "$TAG_START$1" "$YK_ROOT" 2>/dev/null | sed "s|$YK_ROOT/||" }
      yk_file() { grep -R -l "$TAG_START$1" "$YK_ROOT" 2>/dev/null | head -n1 }

      yk_show() {
        local file=$(yk_file "$1") || return 1
        sed -n "/^$TAG_START$1"'$/,/^$TAG_END$1'''$/p' "$file"
      }

      yk_edit() {
        local tag="$1" file=$(yk_file "$tag") || return 1
        local tmp=\( (mktemp) clean= \)(mktemp)

        yk_show "$tag" > "$tmp"
        ''${EDITOR:-nvim} "$tmp"

        sed '1d;$d' "$tmp" > "$clean"   # strip markers
        yk_replace "$tag" < "$clean"

        rm -f "$tmp" "$clean"
        print "Sculpted block '$tag' in $file"
      }

      yk_replace() {
        local tag="$1" file=$(yk_file "$tag") || return 1
        local tmp=\( (mktemp) input= \)(cat)

        local in_block=0
        while IFS= read -r line; do
          [[ "$line" == "$TAG_START$tag" ]] && { in_block=1; print "$line"; print "$input"; continue; }
          [[ "$line" == "$TAG_END$tag" ]] && { in_block=0; print "$line"; continue; }
          (( in_block )) || print "$line"
        done < "$file" > "$tmp"
        mv "$tmp" "$file"
      }

      yk_ls() {
        local target="''${1:-$YK_ROOT}"
        local chosen
        if [[ -f "$target" ]]; then
          chosen=$(grep -n "$TAG_START" "$target" | fzf --with-nth=2.. --preview="echo {} | cut -d: -f2- | sed 's|^.*YUKO:|YUKO:|' | xargs -I% yk show %")
        else
          chosen=$(grep -R -n "$TAG_START" "$YK_ROOT" | sed "s|$YK_ROOT/||" | fzf --with-nth=2.. --preview="echo {} | cut -d: -f2- | sed 's|^.*YUKO:|YUKO:|' | xargs -I% yk show %")
        fi
        [[ -n "\( chosen" ]] && yk edit " \)(echo "$chosen" | awk -F: '{print $3}' | sed "s|$TAG_START||")"
      }

      # ── Entry ─────────────────────────────────────
      case "$1" in
        find)     shift; yk_find "$@" ;;
        file)     shift; yk_file "$@" ;;
        show)     shift; yk_show "$@" ;;
        edit)     shift; yk_edit "$@" ;;
        replace)  shift; yk_replace "$@" ;;
        ls|"")    yk_ls "$2" ;;
        ai)       shift; print "Intelligence sidecar not yet summoned… (tag: $1)"; exit 1 ;;
        -h|--help|help) usage ;;
        *) print "Unknown command: $1"; usage; exit 1 ;;
      esac
    '';

    home.file.".local/bin/yk".executable = true;
  };
}

# modules/cli.nix
{ config, lib, pkgs, ... }:

with lib;
let
  cfg = config.yuko.cli;
in
{
  options.yuko.cli = {
    enable = mkEnableOption "Yuko CLI tools (yk connectome sculptor)";
  };

  config = mkIf cfg.enable {
    # Install yk as a proper Home Manager package (goes to ~/.local/bin/yk)
    home.packages = [
      pkgs.fzf
      (pkgs.writeShellScriptBin "yk" ''
        #!/usr/bin/env zsh
        # ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
        # ┃ yk — Yuko Connectome Sculptor (v0.3)                   ┃
        # ┃ Precision grepping + future AI sidecar entrypoint      ┃
        # ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

        setopt err_exit no_unset pipe_fail

        typeset -r YK_ROOT="''${YK_ROOT:-$HOME/.yuko}"
        typeset -r TAG_START=">>> YUKO:"
        typeset -r TAG_END="<<< YUKO:"

        (( ''${+commands[fzf]} )) || { print -u2 "yk: fzf not found in PATH"; exit 1 }

        usage() { cat <<'EOF'
        yk — surgical edits in ~/.yuko via semantic blocks

        Commands:
          find <pat>        → grep block starts matching <pat>
          file <tag>        → file containing exact <tag>
          show <tag>        → cat block contents (including markers)
          edit <tag>        → edit block body in $EDITOR, markers preserved
          replace <tag>     → replace block body from stdin
          ls                → fzf-powered tag browser (all files)
          ls <file>         → fzf browser scoped to one file
          ai <tag>          → (future) ask intelligence to rewrite block
        EOF
        }

        yk_find() {
          grep -R --color=never -n "$TAG_START$1" "$YK_ROOT" 2>/dev/null | sed "s|^$YK_ROOT/||"
        }

        yk_file() {
          grep -Rl "$TAG_START$1" "$YK_ROOT" 2>/dev/null | head -n1
        }

        yk_show() {
          local file=$(yk_file "$1") || return 1
          sed -n "/^$TAG_START$1"'$/,/^$TAG_END$1'''$/p' "$YK_ROOT/$file"
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
            if [[ "$line" == "$TAG_START$tag" ]]; then
              in_block=1
              print "$line"
              print "$input"
              continue
            elif [[ "$line" == "$TAG_END$tag" ]]; then
              in_block=0
              print "$line"
              continue
            fi
            (( in_block )) || print "$line"
          done < "$YK_ROOT/$file" > "$tmp"
          mv "$tmp" "$YK_ROOT/$file"
        }

        yk_ls() {
          local target="''${1:-$YK_ROOT}"
          local chosen
          if [[ -f "$target" ]]; then
            chosen=$(grep -n "$TAG_START" "$target" | \
              fzf --with-nth=2.. --preview='echo {} | cut -d: -f2- | sed "s|^.*YUKO:|"YUKO:|" | xargs -I% yk show %')
          else
            chosen=$(grep -Rn "$TAG_START" "$YK_ROOT" | sed "s|^$YK_ROOT/||" | \
              fzf --with-nth=2.. --preview='echo {} | cut -d: -f2- | sed "s|^.*YUKO:|"YUKO:|" | xargs -I% yk show %')
          fi
          [[ -n "\( chosen" ]] && yk edit \)(echo "$chosen" | awk -F: '{print $3}' | sed "s/$TAG_START//")
        }

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
      '')
    ];


    # Prepend ~/.local/bin to PATH for instant access
    home.sessionVariables.PATH = "$HOME/.local/bin:$PATH";

    # Seed a welcome block in ~/.yuko on first activation
    home.activation.seedYukoConnectome = hm.dag.entryAfter ["writeBoundary"] ''
      mkdir -p "$HOME/.yuko"
      if [[ ! -f "$HOME/.yuko/welcome.yk" ]]; then
        cat > "$HOME/.yuko/welcome.yk" <<'EOF'
>>> YUKO: yk-welcome
yk is alive! Your connectome sculptor is ready.
- Sculpt new blocks: yk edit my-first-tag
- Browse: yk ls
- Future: yk ai brainstorm-flake-ideas
<<< YUKO: yk-welcome
        EOF
        echo "Seeded ~/.yuko/welcome.yk — run 'yk ls' to explore!"
      fi
    '';
  };
}

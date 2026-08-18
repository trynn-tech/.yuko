# modules/programs/mpv.nix
{ config, lib, pkgs, ... }:

{
  # 1. Enable mpv cleanly via Home Manager with native bindings configuration
  programs.mpv = {
    enable = true;
    scripts = [
      pkgs.mpvScripts.mpris
    ];

    # Enforces the secure socket location globally for all mpv invocations
    extraInput = ''
      input-ipc-server=''${XDG_RUNTIME_DIR}/mpv-socket-yuko
    '';

    # Native mpv window keybindings integrated here to fix file generation conflicts
    bindings = {
      j = "playlist-prev";
      k = "playlist-next";
      n = "playlist-next";
      b = "playlist-prev";
      i = "run \"\${config.home.homeDirectory}/.local/bin/mpv-fzf-menu\"";
      "0" = "seek 0 absolute-percent";
      "1" = "seek 10 absolute-percent";
      "2" = "seek 20 absolute-percent";
      "3" = "seek 30 absolute-percent";
      "4" = "seek 40 absolute-percent";
      "5" = "seek 50 absolute-percent";
      "6" = "seek 60 absolute-percent";
      "7" = "seek 70 absolute-percent";
      "8" = "seek 80 absolute-percent";
      "9" = "seek 90 absolute-percent";
    };
  };

  # 2. Secure interactive menu script
  home.file.".local/bin/mpv-fzf-menu" = {
    text = ''
      #!/usr/bin/env bash
      MUSIC_DIR="$HOME/Music"
      SOCKET="''${XDG_RUNTIME_DIR}/mpv-socket-yuko"
      PLAYLIST_TMP="''${XDG_RUNTIME_DIR}/mpv-playlist-yuko.m3u"

      if [ ! -e "$SOCKET" ]; then
          exit 0
      fi

      mapfile -t playlist < <(find "$MUSIC_DIR" -type f \( -name "*.mp3" -o -name "*.flac" -o -name "*.m4a" -o -name "*.ogg" -o -name "*.wav" -o -name "*.mp4" -o -name "*.m4v" \))

      selected=$(printf "%s\n" "''${playlist[@]}" | fzf \
          --prompt="🎵 Search Media > " \
          --height=40% \
          --reverse \
          --bind "tab:down" \
          --bind "alt-j:down" \
          --bind "alt-k:up")

      if [ -n "$selected" ]; then
          {
              echo "$selected"
              printf "%s\n" "''${playlist[@]}" | grep -vFx "$selected" | shuf
          } > "$PLAYLIST_TMP"
          printf "loadlist \"%s\" replace\nset pause no\n" "$PLAYLIST_TMP" | ${pkgs.socat}/bin/socat - "$SOCKET" >/dev/null 2>&1
      fi
    '';
    executable = true;
  };

  # 3. Main terminal controller script
  home.file.".local/bin/mpv-fzf" = {
    text = ''
      #!/usr/bin/env bash
      MUSIC_DIR="''${1:-$HOME/Music}"
      SOCKET="''${XDG_RUNTIME_DIR}/mpv-socket-yuko"
      PLAYLIST_TMP="''${XDG_RUNTIME_DIR}/mpv-playlist-yuko.m3u"

      rm -f "$SOCKET" "$PLAYLIST_TMP"

      mapfile -t playlist < <(find "$MUSIC_DIR" -type f \( -name "*.mp3" -o -name "*.flac" -o -name "*.m4a" -o -name "*.ogg" -o -name "*.wav" -o -name "*.mp4" -o -name "*.m4v" \))

      if [ ''${#playlist[@]} -eq 0 ]; then
          echo "Error: No matching media files found in $MUSIC_DIR"
          exit 1
      fi

      printf "%s\n" "''${playlist[@]}" | shuf > "$PLAYLIST_TMP"

      # Handled securely via XDG_RUNTIME_DIR socket
      mpv --input-ipc-server="$SOCKET" --quiet --geometry=75%x75% --playlist="$PLAYLIST_TMP" </dev/null>/dev/null 2>&1 &
      MPV_PID=$!
      sleep 0.8
      clear
      echo "========================================"
      echo "       MPV-FZF Terminal Controller      "
      echo "========================================"
      echo "  [j] Previous Track"
      echo "  [k] Next Track"
      echo "  [p] Play / Pause (via playerctl)"
      echo "  [i] Open fzf Search Menu"
      echo "  [q] Quit Player"
      echo "----------------------------------------"

      while kill -0 $MPV_PID 2>/dev/null; do
          echo -n "mpv-fzf> "
          read -rsn1 key
          echo "$key"
          case "$key" in
              j)
                  printf "playlist-prev\nset pause no\n" | ${pkgs.socat}/bin/socat - "$SOCKET" >/dev/null 2>&1
                  echo "-> Previous track playing"
                  ;;
              k)
                  printf "playlist-next\nset pause no\n" | ${pkgs.socat}/bin/socat - "$SOCKET" >/dev/null 2>&1
                  echo "-> Next track playing"
                  ;;
              p)
                  ${pkgs.playerctl}/bin/playerctl --player=mpv play-pause
                  echo "-> Toggled Playback State"
                  ;;
              i)
                  selected=$(printf "%s\n" "''${playlist[@]}" | fzf \
                      --prompt="🎵 Search Media > " \
                      --height=40% \
                      --reverse \
                      --bind "tab:down" \
                      --bind "alt-j:down" \
                      --bind "alt-k:up")
                  if [ -n "$selected" ]; then
                      {
                          echo "$selected"
                          printf "%s\n" "''${playlist[@]}" | grep -vFx "$selected" | shuf
                      } > "$PLAYLIST_TMP"
                      printf "loadlist \"%s\" replace\nset pause no\n" "$PLAYLIST_TMP" | ${pkgs.socat}/bin/socat - "$SOCKET" >/dev/null 2>&1
                      echo "-> Playing: $(basename "$selected") (New random queue generated)"
                  fi
                  ;;
              q)
                  echo "Exiting..."
                  kill $MPV_PID 2>/dev/null
                  break
                  ;;
          esac
      done

      rm -f "$SOCKET" "$PLAYLIST_TMP"
    '';
    executable = true;
  };

  # 4. Status worker daemon to process active metadata with scrolling and instant i3status refresh signals
  home.file.".local/bin/mpv-status-daemon" = {
    text = ''
      #!/usr/bin/env bash
      SOCKET="''${XDG_RUNTIME_DIR}/mpv-socket-yuko"
      TARGET_FILE="$HOME/.cache/mpv-current-song"
      
      MAX_LEN=25
      PADDING="   "
      
      LAST_RAW=""
      CURRENT_SONG=""
      SCROLL_IDX=0
      CHECK_COUNTER=0

      mkdir -p "$(dirname "$TARGET_FILE")"
      touch "$TARGET_FILE"

      trigger_refresh() {
          killall -SIGUSR1 i3status >/dev/null 2>&1
      }

      while true; do
          # 1. Fetch metadata from MPV less frequently (every ~2 seconds) to preserve CPU
          if [ $CHECK_COUNTER -eq 0 ] || [ $CHECK_COUNTER -ge 5 ]; then
              CHECK_COUNTER=0
              NEW_RAW=""
              
              if [ -S "$SOCKET" ]; then
                  RAW_TITLE=$(echo '{ "command": ["get_property", "media-title"] }' | ${pkgs.socat}/bin/socat - "$SOCKET" 2>/dev/null | ${pkgs.jq}/bin/jq -r '.data // empty')

                  if [ -n "$RAW_TITLE" ]; then
                      # Clean paths, extensions, and strip leading/trailing spaces cleanly
                      CLEAN_TITLE=$(basename "$RAW_TITLE" | sed -E 's/\.(mp3|flac|m4a|ogg|wav|mp4|m4v)$//I')
                      NEW_RAW=$(echo "$CLEAN_TITLE" | xargs)
                  elif ${pkgs.playerctl}/bin/playerctl --player=mpv status >/dev/null 2>&1; then
                      ARTIST=$(${pkgs.playerctl}/bin/playerctl --player=mpv metadata artist 2>/dev/null | xargs)
                      TITLE=$(${pkgs.playerctl}/bin/playerctl --player=mpv metadata title 2>/dev/null | xargs)
                      if [ -n "$ARTIST" ] && [ -n "$TITLE" ]; then
                          NEW_RAW="$ARTIST - $TITLE"
                      elif [ -n "$TITLE" ]; then
                          NEW_RAW="$TITLE"
                      fi
                  fi
              fi

              # Reset index if the track has actually changed
              if [ "$NEW_RAW" != "$LAST_RAW" ]; then
                  LAST_RAW="$NEW_RAW"
                  CURRENT_SONG="$NEW_RAW"
                  SCROLL_IDX=0
              fi
          fi

          ((CHECK_COUNTER++))

          # 2. Frame generator: Handle empty, fitting, or scrolling text states
          if [ -z "$CURRENT_SONG" ]; then
              if [ -s "$TARGET_FILE" ]; then
                  :> "$TARGET_FILE"
                  trigger_refresh
              fi
          elif [ ''${#CURRENT_SONG} -le $MAX_LEN ]; then
              # Track fits perfectly: write once, no scroll animation loop needed
              if [ "$(cat \"$TARGET_FILE\" 2>/dev/null)" != "$CURRENT_SONG" ]; then
                  echo "$CURRENT_SONG" > "$TARGET_FILE"
                  trigger_refresh
              fi
          else
              # Track is too long: slice text, advance frame index, and refresh i3status
              EXTENDED="''${CURRENT_SONG}''${PADDING}''${CURRENT_SONG}''${PADDING}"
              DISPLAY_TEXT="''${EXTENDED:$SCROLL_IDX:$MAX_LEN}"
              
              echo "$DISPLAY_TEXT" > "$TARGET_FILE"
              trigger_refresh

              ((SCROLL_IDX++))
              # Loop animation seamless frame calculation reset
              if [ $SCROLL_IDX -ge $((''${#CURRENT_SONG} + ''${#PADDING})) ]; then
                  SCROLL_IDX=0
              fi
          fi

          sleep 0.4 # Controls the movement speed of the scrolling text on your bar
      done
    '';
    executable = true;
  };

  # 5. Background User-space Service to run the daemon smoothly
  systemd.user.services.mpv-status-daemon = {
    Unit = {
      Description = "Bridges active mpv stream track profiles to i3status target pipelines";
      After = [ "graphical-session.target" ];
      PartOf = [ "graphical-session.target" ];
    };
    Service = {
      ExecStart = "${config.home.homeDirectory}/.local/bin/mpv-status-daemon";
      Restart = "always";
      RestartSec = 3;
    };
    Install = {
      WantedBy = [ "graphical-session.target" ];
    };
  };
}

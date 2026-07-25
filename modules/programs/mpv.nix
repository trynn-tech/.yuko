# modules/programs/mpv.nix
{ config, lib, pkgs, ... }:

{
  home.packages = with pkgs; [
    mpv
    socat
    findutils
    fzf
  ];

  # Native mpv window keybindings
  home.file.".config/mpv/input.conf" = {
    text = ''
      j playlist-prev
      k playlist-next
      n playlist-next
      b playlist-prev
      i run "${config.home.homeDirectory}/.local/bin/mpv-fzf-menu"
      0 seek 0 absolute-percent
      1 seek 10 absolute-percent
      2 seek 20 absolute-percent
      3 seek 30 absolute-percent
      4 seek 40 absolute-percent
      5 seek 50 absolute-percent
      6 seek 60 absolute-percent
      7 seek 70 absolute-percent
      8 seek 80 absolute-percent
      9 seek 90 absolute-percent
    '';
  };

  # Helper script when 'i' is pressed inside mpv
  home.file.".local/bin/mpv-fzf-menu" = {
    text = ''
      #!/usr/bin/env bash
      MUSIC_DIR="$HOME/Music"
      SOCKET="/tmp/mpv-socket-yuko"
      PLAYLIST_TMP="/tmp/mpv-playlist-yuko.m3u"

      if [ ! -e "$SOCKET" ]; then
          exit 0
      fi

      # Find all files for fzf selection
      mapfile -t playlist < <(find "$MUSIC_DIR" -type f \( -name "*.mp3" -o -name "*.flac" -o -name "*.m4a" -o -name "*.ogg" -o -name "*.wav" -o -name "*.mp4" -o -name "*.m4v" \))

      selected=$(printf "%s\n" "''${playlist[@]}" | fzf \
          --prompt="🎵 Search Media > " \
          --height=40% \
          --reverse \
          --bind "tab:down" \
          --bind "alt-j:down" \
          --bind "alt-k:up")

      if [ -n "$selected" ]; then
          # Generate a brand new randomized playlist queue starting with the selected track
          {
              echo "$selected"
              printf "%s\n" "''${playlist[@]}" | grep -vFx "$selected" | shuf
          } > "$PLAYLIST_TMP"

          # Tell mpv to load the new playlist from the top and play immediately
          printf "loadlist \"%s\" replace\nset pause no\n" "$PLAYLIST_TMP" | socat - "$SOCKET" >/dev/null 2>&1
      fi
    '';
    executable = true;
  };

  # Main terminal controller script
  home.file.".local/bin/mpv-fzf" = {
    text = ''
      #!/usr/bin/env bash
      MUSIC_DIR="''${1:-$HOME/Music}"
      SOCKET="/tmp/mpv-socket-yuko"
      PLAYLIST_TMP="/tmp/mpv-playlist-yuko.m3u"

      # Clean up stale files
      rm -f "$SOCKET" "$PLAYLIST_TMP"

      # Find media files
      mapfile -t playlist < <(find "$MUSIC_DIR" -type f \( -name "*.mp3" -o -name "*.flac" -o -name "*.m4a" -o -name "*.ogg" -o -name "*.wav" -o -name "*.mp4" -o -name "*.m4v" \))

      if [ ''${#playlist[@]} -eq 0 ]; then
          echo "Error: No matching media files found in $MUSIC_DIR"
          exit 1
      fi

      # Shuffle playlist
      printf "%s\n" "''${playlist[@]}" | shuf > "$PLAYLIST_TMP"

      # Start mpv completely detached from stdin/stdout
      mpv --input-ipc-server="$SOCKET" --quiet --geometry=75%x75% --playlist="$PLAYLIST_TMP" </dev/null>/dev/null 2>&1 &
      MPV_PID=$!

      # Give socket a moment to initialize
      sleep 0.8

      clear
      echo "========================================"
      echo "       MPV-FZF Terminal Controller      "
      echo "========================================"
      echo "  [j] Previous Track"
      echo "  [k] Next Track"
      echo "  [i] Open fzf Search Menu"
      echo "  [q] Quit Player"
      echo "----------------------------------------"

      # Terminal control loop
      while kill -0 $MPV_PID 2>/dev/null; do
          echo -n "mpv-fzf> "
          read -rsn1 key
          echo "$key"

          case "$key" in
              j)
                  printf "playlist-prev\nset pause no\n" | socat - "$SOCKET" >/dev/null 2>&1
                  echo "-> Previous track playing"
                  ;;
              k)
                  printf "playlist-next\nset pause no\n" | socat - "$SOCKET" >/dev/null 2>&1
                  echo "-> Next track playing"
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

                      printf "loadlist \"%s\" replace\nset pause no\n" "$PLAYLIST_TMP" | socat - "$SOCKET" >/dev/null 2>&1
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

      # Cleanup
      rm -f "$SOCKET" "$PLAYLIST_TMP"
    '';
    executable = true;
  };
}

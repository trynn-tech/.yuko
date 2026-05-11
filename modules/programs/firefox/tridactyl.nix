{ config, pkgs, lib, ... }:

let
  searchUrls = {
    yt = "https://www.youtube.com/search?q=";
    google = "https://www.google.com/search?q=";
  };

  bindings = [
    # --- SEARCH & OPEN ---
    "bind y fillcmdline tabopen yt"
    "bind T fillcmdline open"
    "bind t fillcmdline buffer"

    # --- MARKS (Fixed to prevent TypeError) ---
    "unbind --mode=normal '"
    "unbind --mode=insert '"
    "unbind --mode=ignore '"
    "unbind m"
    #"reset --mode=normal '"
    "bind m fillcmdline markaddglobal"
    "bind ' fillcmdline markjumpglobal"

    "bind / fillcmdline find"

    # --- SCROLLING ---
    "unbind e"
    "unbind d"
    "bind e scrollpage -1"
    "bind d scrollpage 1"
    "bind x tabclose"

    # --- TAB NAVIGATION & MOVEMENT ---
    "unbind E"
    "unbind R"
    "bind E tabprev"
    "bind R tabnext"

    "unbind >>"
    "unbind <<"
    "bind g] tabmove +1"
    "bind g[ tabmove -1"

    "unbind J"
    "bind J tab #" # Go to last active tab

    "unbind K"
    "bind K tabaudio" # Go to tab playing audio

    "bind g- tablast" # Go to last tab 

    # --- HINTS ---
    "bind u hint -J"
    "bind U hint -t"
    "bind gf hint -t" # Open and follow link
    "bind cd hint -F"
    "bind a hint -b" # Open background link
    "bind A hint -qb" # Open a queue of background links
    "bind i composite focusinput -l ; text.end_of_line" # Insert mode

    # --- HISTORY ---
    "bind H back"
    "bind L forward"

  ];

  hintCss = "font-family: 'JetBrains Mono NL', monospace; font-size: 13pt; color: #bf00ff !important; background-color: #000000 !important; border: 2px solid #bf00ff !important; font-weight: bold !important;";

in
{
  xdg.configFile."tridactyl/tridactylrc".text = ''
    " --- SEARCH ENGINES ---
    ${builtins.concatStringsSep "\n" (lib.mapAttrsToList (k: v: "set searchurls.${k} ${v}") searchUrls)}

    " --- KEYBINDINGS ---
    ${builtins.concatStringsSep "\n" bindings}

    " --- THEME ---
    colors rose-pine
    set hintfiltermode vimperator-reflow
    set hintcss ${hintCss}
    
    " --- SETTINGS ---
    set keystrokes always
    set editorcmd ${pkgs.alacritty}/bin/alacritty -e ${pkgs.neovim}/bin/nvim
    set downloadmethod native
  '';
}

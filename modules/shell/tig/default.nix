{ config, pkgs, lib, ... }:

{
  # 1. Ensure the 'tig' package is installed
  home.packages = [ pkgs.tig ];

  # 2. Declaratively define the ~/.tigrc file content.
  home.file.".tigrc" = {
    # Home Manager will overwrite (clobber) the file with this content.
    text = ''
      # --- YUKO TIG CONFIGURATION ---
      
      # Set up the Cherry-Pick binding for the main (generic) view
      # C: Cherry-Pick selected commit without sign-off
      bind generic C ! git cherry-pick %(commit)
      
      # S: Cherry-Pick selected commit with sign-off (a useful variant)
      bind generic S ! git cherry-pick -s %(commit)

      # Optional: Add other general utility bindings or settings here
      # For example, binding 't' to open the file in the editor:
      # bind blob t ! sh -c 'vi %(file)'
    '';
  };
}


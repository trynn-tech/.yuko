# modules/dev/git.nix
{ config, lib, pkgs, ... }:

{
  # Core Git configuration using modern Home Manager structure
  programs.git = {
    enable = true;
    settings = {
      core = {
        editor = "nvim";
      };
      merge = {
        conflictstyle = "zdiff3";
      };
    };
  };

  # Delta Module
  programs.delta = {
    enable = true;
    enableGitIntegration = true; 
    options = {
      navigate = true;
      light = false;
      side-by-side = true;
      line-numbers = true;
    };
  };

  # Lazygit configuration migrated to the new schema format
  programs.lazygit = {
    enable = true;
    settings = {
      git = {
        # FIXED: Migrated old paging object to the updated pagers / diffRenderers schema
        pagers = {
          # Defines the custom delta renderer matching the structural migration format
          delta = "delta --dark --paging=never";
        };
        diffRenderers = [
          {
            command = "delta --dark --paging=never";
            format = "color";
          }
        ];
        # Optional: You can explicitly tie the renderer target if needed
        paging = {
          colorArg = "always";
          pager = "delta --dark --paging=never";
        };
      };
      os = {
        edit = "nvim"; 
      };
    };
  };

  home.packages = with pkgs; [
    git-subrepo
    gh
  ];
}


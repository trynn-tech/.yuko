# modules/programs/file-managers.nix
{ pkgs, ... }: {
  home.packages = with pkgs; [
    nemo-with-extensions
  ];

  programs.yazi = {
    enable = true;
    enableZshIntegration = true;
    shellWrapperName = "y";
    settings = {
      manager = {
        show_hidden = true;
        sort_by = "natural";
      };
      # This is the part that forces nvim regardless of $EDITOR
      opener = {
        edit = [
          {
            run = ''nvim "$@"'';
            block = true;
            desc = "Edit with Neovim";
          }
        ];
      };
      open = {
        prepend_rules = [
          { name = "*.nix"; use = "edit"; }
          { name = "*.md"; use = "edit"; }
          { mime = "text/*"; use = "edit"; }
        ];
      };
    };
  };

  xdg.mimeApps = {
    enable = true;
    defaultApplications = {
      "inode/directory" = [ "nemo.desktop" ];
      "application/x-gnome-saved-search" = [ "nemo.desktop" ];
    };
  };
}


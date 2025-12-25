# modules/editors/nixvim

{ config, pkgs, ... }:

{
  programs.nixvim = {
    enable = true;

    globals.mapleader = " ";
    globals.maplocalleader = " "; # Good for plugin-specific maps

    opts = {
      number = true;
      relativenumber = true;
      termguicolors = true;
    };

    # 1. Disable the nixvim-managed vimwiki module to prevent conflicts
    plugins.vimwiki.enable = false;

    # 2. Add the plugin as a raw extra plugin
    extraPlugins = with pkgs.vimPlugins; [
      vimwiki
    ];

    # 3. SETTINGS: Initialize Vimscript globals before Lua loads
    extraConfigVim = ''
      let g:vimwiki_list = [{'path': '~/yang_wiki/', 'syntax': 'markdown', 'ext': '.md'}]
      let g:vimwiki_global_ext = 0
      
      " Force filetype detection for markdown/vimwiki
      filetype plugin on
    '';

    # 4. KEYMAPS: Use the simple command string again
    extraConfigLua = ''
      vim.g.mapleader = " "
      
      -- Standard Telescope
      vim.keymap.set("n", "<leader>ff", "<cmd>Telescope find_files<CR>")
      vim.keymap.set("n", "<leader>fg", "<cmd>Telescope live_grep<CR>")
      
      -- Wiki Handshake
      vim.keymap.set("n", "<leader>ww", "<cmd>VimwikiIndex<CR>", { desc = "Open Wiki" })
    '';

    plugins = {
      treesitter.enable = true;
      telescope.enable = true;
      which-key.enable = true;
      web-devicons.enable = true;

      # This forces the plugin to load even if you aren't in a .md file
      extraPlugins = with pkgs.vimPlugins; [
        vimwiki
      ];

      lsp = {
        enable = true;
        servers.nixd = {
          enable = true;

          settings.nixd = {
            formatting.command =
              if config.yuko.dev.nix.formatter == "alejandra" then [ "alejandra" ] else [ "nixfmt" ];

            autoCmd = [
              {
                event = [ "BufWritePre" ];
                pattern = [ "*.nix" ];
                command = [ "lua vim.lsp.buf.format()" ];
              }
            ];

            # Example: let nixd know about your flake/home config
            options = {
              home_manager = {
                expr = ''(builtins.getFlake ".").homeConfigurations."yuko-core".config'';
              };
            };
          };
        };
      };
    };


  };
}

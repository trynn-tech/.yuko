# modules/editors/nixvim.nix
{ config, pkgs, ... }:

{
  programs.nixvim = {
    enable = true;

    opts = {
      number = true;
      relativenumber = true;
      termguicolors = true;
    };

    plugins = {
      treesitter.enable = true;
      telescope.enable = true;
      which-key.enable = true;
      web-devicons.enable = true;
      lsp = {
        enable = true;
        servers.nixd = {
          enable = true;

          # Optional but nice: let nixd drive formatting
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
    # If nixvim has a dedicated formatter interface, you *can*
    # also hook conform/null-ls/etc here, but letting nixd format
    # is usually simpler to start.

    extraConfigLua = ''
      vim.keymap.set("n", "<leader>ff", "<cmd>Telescope find_files<CR>")
      vim.keymap.set("n", "<leader>fg", "<cmd>Telescope live_grep<CR>")
    '';
  };
}

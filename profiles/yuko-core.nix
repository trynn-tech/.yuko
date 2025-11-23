# profiles/yuko-core.nix
{ config, pkgs, ... }:

{
  imports = [
    ../modules/core.nix
    ../modules/shell/default.nix
    ../modules/tmux/default.nix
  ];

  # Turn on the “default shell” behavior for this profile/mode
  yuko.shell.default = true;

  programs.nixvim = {
    enable = true;

    # Basic options
    globals.mapleader = " ";
    opts = {
      number         = true;
      relativenumber = true;
      termguicolors  = true;
    };

    # A tiny starter plugin set – you can expand later
    plugins = {
      treesitter.enable = true;
      lsp.enable        = true;
      telescope.enable  = true;
      web-devicons.enable = true;
      which-key.enable  = true;
    };

    # Your own Lua on top (you can move this to a file later)
    extraConfigLua = ''
      -- YukoNix Scaffold: starter config
      vim.keymap.set("n", "<leader>ff", "<cmd>Telescope find_files<CR>")
      vim.keymap.set("n", "<leader>fg", "<cmd>Telescope live_grep<CR>")
    '';
  };
}

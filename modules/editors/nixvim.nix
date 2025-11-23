{ config, pkgs, ... }:

{
  programs.nixvim = {
    enable = true;

    opts = {
      number         = true;
      relativenumber = true;
      termguicolors  = true;
    };

    plugins = {
      treesitter.enable   = true;
      lsp.enable          = true;
      telescope.enable    = true;
      which-key.enable    = true;
      web-devicons.enable = true;
    };

    extraConfigLua = ''
      vim.keymap.set("n", "<leader>ff", "<cmd>Telescope find_files<CR>")
      vim.keymap.set("n", "<leader>fg", "<cmd>Telescope live_grep<CR>")
    '';
  };
}

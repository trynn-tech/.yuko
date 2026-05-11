# modules/editors/nixvim.nix
{ config, pkgs, ... }:

let
  pyEnv = pkgs.python3.withPackages (ps: with ps; [ 
    pynvim tasklib six packaging 
  ]);
  tw3Bin = "${pkgs.taskwarrior3}/bin/task";
in
{
  programs.nixvim = {
    enable = true;

    python3Provider = {
      enable = true;
      package = pyEnv;
    };

    globals = {
      mapleader = " ";
      maplocalleader = " ";
      python3_host_prog = "${pyEnv}/bin/python3";
      
      vimwiki_list = [{ path = "~/wiki_yuko/"; syntax = "markdown"; ext = ".md"; }];
      vimwiki_global_ext = 0;
      
      # THE BRAID: Pin to the exact same TW3 binary
      taskwiki_taskbin = "${tw3Bin}";
      taskwiki_dont_preserve_environment = 1; 
      taskwiki_source_tw_colors = 0;
      
      # Stop automatic re-creation loops
      taskwiki_disable_automatic_events = [ "InsertLeave" "TextChanged" "TextChangedI" "BufWinEnter" ];
    };

    opts = {
      number = true;
      relativenumber = true;
      termguicolors = true;
      clipboard = "unnamedplus";
      undofile = true;
      conceallevel = 2;
    };

    plugins = {
      treesitter.enable = true;
      web-devicons.enable = true;
      which-key.enable = true;
      telescope.enable = true;
      lsp.enable = true;
      lsp.servers.nixd.enable = true;
    };
    # If nixvim has a dedicated formatter interface, you *can*
    # also hook conform/null-ls/etc here, but letting nixd format
    # is usually simpler to start.

    extraPlugins = with pkgs.vimPlugins; [ vimwiki taskwiki vim-plugin-AnsiEsc ];
    extraPackages = with pkgs; [ wl-clipboard xclip taskwarrior3 ];

    extraConfigLua = ''
      local builtin = require('telescope.builtin')
      vim.keymap.set("n", "<leader>ff", builtin.find_files, { desc = "Find Files" })
      vim.keymap.set("n", "<leader>ww", "<cmd>VimwikiIndex<CR>", { desc = "Wiki Index" })
      vim.keymap.set("n", "<leader>tw", ":call YangSync()<CR>", { desc = "Manual Task Sync" })
    '';

    extraConfigVim = ''
      filetype plugin on
      autocmd BufRead,BufNewFile ~/wiki_yuko/*.md set filetype=vimwiki

      function! YangSync()
        if &ft != 'vimwiki' | return | endif
        let l:save = winsaveview()
        silent! update
        if exists(':TaskWikiBufferUpdate')
          silent! TaskWikiBufferUpdate
        endif
        call winrestview(l:save)
      endfunction

      augroup YangSyncGroup
        autocmd!
        autocmd BufWritePost ~/wiki_yuko/*.md call YangSync()
      augroup END

      " POINT OF TRUTH: Direct path to the TW3 Nix store binary
      let g:taskwiki_taskbin = '/nix/store/2r0ryqw8ay9fs38rj38q3bfzv47drija-taskwarrior-3.4.2/bin/task'
      
      " DATA BRIDGE: Ensure we are using the SQLite database
      let g:taskwiki_data_location = '~/.local/share/task'
      
      " SYNC STABILITY
      let g:taskwiki_dont_preserve_environment = 1
      let g:taskwiki_disable_prompts = 1
    '';
  };
}




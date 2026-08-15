# modules/editors/default.nix
{ config, pkgs, ... }:

let
  pyEnv = pkgs.python3.withPackages (ps: with ps; [
    pynvim
    tasklib
    six
    packaging
  ]);
  tw3Bin = "${pkgs.taskwarrior3}/bin/task";
in
{
  imports = [
    ./task_org.nix
  ];

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

      # UNDOTREE: Automatically switch focus to the tree window when toggled
      undotree_SetFocusWhenToggle = 1;
    };
    opts = {
      number = true;
      relativenumber = true;
      termguicolors = true;
      undofile = true;
      conceallevel = 2;
    };
    plugins = {
      treesitter.enable = true;
      web-devicons.enable = true;
      which-key.enable = true;
      telescope.enable = true;
      undotree.enable = true;
      lsp.enable = true;
      lsp.servers.nixd.enable = true;
      lsp.servers.pyright.enable = true;
    };
    extraPlugins = with pkgs.vimPlugins; [ vimwiki taskwiki vim-plugin-AnsiEsc ];
    extraPackages = with pkgs; [ wl-clipboard xclip taskwarrior3 jq ];

    extraConfigLua = ''
      local builtin = require('telescope.builtin')
      vim.keymap.set("n", "<leader>ff", builtin.find_files, { desc = "Find Files" })
      vim.keymap.set("n", "<leader>ww", "<cmd>VimwikiIndex<CR>", { desc = "Wiki Index" })
      vim.keymap.set("n", "<leader>tw", ":call YangSync()<CR>", { desc = "Manual Task Sync" })
      
      -- UNDOTREE: Toggle undo history tree
      vim.keymap.set("n", "<leader>u", "<cmd>UndotreeToggle<CR>", { desc = "Toggle Undotree" })

      -- FUNCTION & CONFIG OBJECT JUMPING: Universal symbol navigation for Nix and Python
      vim.keymap.set("n", "<leader>n", function()
        builtin.lsp_document_symbols({ 
          symbols = { 
            "Function", "Method", "Class",     -- Python
            "Module", "Struct", "Variable",    -- Nix top-level/attributes
            "Constant", "Field", "Property"    -- Nix nested config blocks
          } 
        })
      end, { desc = "Jump to function or config object" })

      -- SECURE CLIPBOARD SYSTEM
      vim.keymap.set("v", "<leader>y", '"+y', { desc = "Secure copy selection to system clipboard" })
      vim.keymap.set("n", "<leader>Y", '"+yg_', { desc = "Secure copy line to system clipboard" })

      -- PURPLE HIGHLIGHT FEATURE
      vim.api.nvim_set_hl(0, 'LeaderPurpleHighlight', { bg = '#8A2BE2', fg = '#FFFFFF', bold = true })
      local active_purple_match = nil
      vim.keymap.set("v", "<leader>h", function()
        vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<Esc>", true, false, true), "nx", false)
        if active_purple_match then
          pcall(vim.fn.matchdelete, active_purple_match)
          active_purple_match = nil
          vim.cmd("nohlsearch")
          return
        end
        local start_line = vim.fn.line("'<")
        local end_line = vim.fn.line("'>")
        local start_col = vim.fn.col("'<")
        local end_col = vim.fn.col("'>")
        local pos = {}
        if start_line == end_line then
          table.insert(pos, { start_line, start_col, (end_col - start_col + 1) })
        else
          table.insert(pos, { start_line, start_col })
          for l = start_line + 1, end_line - 1 do
            table.insert(pos, l)
          end
          table.insert(pos, { end_line, 1, end_col })
        end
        active_purple_match = vim.fn.matchaddpos('LeaderPurpleHighlight', pos)
        vim.opt.hlsearch = true
      end, { desc = "Toggle purple highlight on selection" })
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

      augroup PrettyPrintJsonWorkflows
        autocmd!
        autocmd BufReadPost,BufNewFile */wiki_yuko/*,*/inbox_yuko/*,*/wiki_yuko/*.md,*/inbox_yuko/*.md
            \ let l:is_json_array = (getline(1) =~ '^\s*\[') |
            \ if l:is_json_array || &filetype ==# 'json' |
            \   let l:test_cmd = "system('jq .', join(getline(1, '$'), \"\n\"))" |
            \   if v:shell_error != 0 |
            \     echohl WarningMsg |
            \     echo "JQ Parse Error: File contains invalid JSON. Bypassing auto-formatter." |
            \     echohl None |
            \   else |
            \     execute "%!jq '.'" |
            \     if l:is_json_array | setlocal filetype=json | endif |
            \   fi |
            \ endif
      augroup END

      let g:taskwiki_taskbin = '${tw3Bin}'
      let g:taskwiki_data_location = '~/.local/share/task'
      let g:taskwiki_dont_preserve_environment = 1
      let g:taskwiki_disable_prompts = 1
    '';
  };
}

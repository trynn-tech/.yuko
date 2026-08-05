# modules/editors/task_org.nix
{ pkgs, ... }:

{
  programs.nixvim = {
    extraPackages = with pkgs; [
      ripgrep
      taskwarrior3
      gawk
      jq
    ];

    extraConfigLua = ''
      local buffer_uuids = {}

      local function extract_uuid(str)
        return str:match("(%x%x%x%x%x%x%x%x%-%x%x%x%x%-%x%x%x%x%-%x%x%x%x%-%x%x%x%x%x%x%x%x%x%x%x%x)")
      end

      vim.api.nvim_create_autocmd("BufWritePost", {
        callback = function()
          local bufnr = vim.api.nvim_get_current_buf()
          local filepath = vim.api.nvim_buf_get_name(bufnr)
          if filepath == "" then return end

          local filename = vim.fn.fnamemodify(filepath, ":t")
          local lines = vim.api.nvim_buf_get_lines(bufnr, 0, -1, false)

          buffer_uuids[bufnr] = buffer_uuids[bufnr] or {}
          local current_file_uuids = {}

          local updated_lines = {}
          local modified = false

          for idx, line in ipairs(lines) do
            local line_num = idx
            local uuid = extract_uuid(line)
            
            if uuid then
              current_file_uuids[uuid] = true
            end

            -- Match lines containing `# TODO:`
            if line:match("#%s*[Tt][Oo][Dd][Oo]:") then
              if uuid then
                -- Already tracked, keep as is
                table.insert(updated_lines, line)
              else
                -- 1. Clean description text while ignoring anything inside brackets []
                local clean_text = line:gsub("^%s*#%s*[Tt][Oo][Dd][Oo]:%s*", "")
                clean_text = clean_text:gsub("%s*%b[]", "")
                clean_text = vim.trim(clean_text)

                if clean_text ~= "" then
                  local task_desc = string.format("%s (Ref: %s:%d)", clean_text, filename, line_num)
                  
                  -- 2. Create the task normally
                  local add_cmd = string.format(
                    "task add project:code +nix rc.confirmation=no %s > /dev/null 2>&1",
                    vim.fn.shellescape(task_desc)
                  )
                  os.execute(add_cmd)

                  -- 3. Export tasks, sort by entry/ID descending, and fetch the exact UUID of the newly created task via jq
                  local export_cmd = "task project:code status:pending export | " .. 
                                     "jq -r 'sort_by(.entry) | reverse | .[0].uuid // empty'"
                  local handle = io.popen(export_cmd)
                  local res = handle:read("*a")
                  handle:close()

                  local new_uuid = extract_uuid(res)
                  if new_uuid then
                    current_file_uuids[new_uuid] = true
                    local new_line = line:gsub("%s*$", "") .. " [" .. new_uuid .. "]"
                    table.insert(updated_lines, new_line)
                    modified = true
                    vim.notify("Taskwarrior: Tracked # TODO -> " .. new_uuid, vim.log.levels.INFO)
                  else
                    table.insert(updated_lines, line)
                  end
                else
                  table.insert(updated_lines, line)
                end
              end
            else
              table.insert(updated_lines, line)
            end
          end

          if modified then
            vim.api.nvim_buf_set_lines(bufnr, 0, -1, false, updated_lines)
            vim.cmd("silent noautocmd write")
          end

          -- Detect if previously tracked UUIDs were deleted from this file, then force task completion
          for old_uuid, _ in pairs(buffer_uuids[bufnr]) do
            if not current_file_uuids[old_uuid] then
              local done_cmd = string.format("task rc.confirmation=no %s done > /dev/null 2>&1", old_uuid)
              os.execute(done_cmd)
              vim.notify("Taskwarrior: Marked task " .. old_uuid .. " as DONE (# TODO removed).", vim.log.levels.INFO)
            end
          end

          buffer_uuids[bufnr] = current_file_uuids
        end,
      })
    '';
  };
}

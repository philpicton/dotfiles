return {
  "folke/snacks.nvim",
  config = function(_, opts)
    require("snacks").setup(opts)

    local color = "#FB923C"

    local function set_header_hl()
      vim.api.nvim_set_hl(0, "SnacksDashboardHeader", { fg = color })
    end

    -- 1. Apply immediately
    set_header_hl()

    -- 2. Re-apply after the colorscheme applies its highlights
    vim.api.nvim_create_autocmd("ColorScheme", {
      callback = set_header_hl,
    })

    -- 3. Re-apply when the Snacks dashboard is opened (Snacks redraws it)
    vim.api.nvim_create_autocmd("User", {
      pattern = "SnacksDashboardOpen",
      callback = set_header_hl,
    })
  end,
  opts = {
    -- show images in obsidian files
    image = {
      resolve = function(path, src)
        local api = require("obsidian.api")
        if api.path_is_note(path) then
          return api.resolve_attachment_path(src)
        end
      end,
    },
    dashboard = {
      preset = {
        header = [[
                                                
                          ↑↑↑↑↑↑                
                          ↑↑↑↑↑↑                
                          ↑↑↑↑↑↑                
                          ↑↑↑↑↑↑                
                          ↑↑↑↑↑↑                
                          ↑↑↑↑↑↑                
                          ↑↑↑↑↑↑↑↑              
               ↑↑↑         ↑↑↑↑↑↑↑↑↑            
             ↑↑↑↑↑↑          ↑↑↑↑↑↑↑↑↑          
           ↑↑↑↑↑↑↑↑↑↑          ↑↑↑↑↑↑↑↑↑        
         ↑↑↑↑↑↑↑↑↑↑↑↑↑↑          ↑↑↑↑↑↑↑↑↑      
        ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑          ↑↑↑↑↑↑↑↑↑    
      ↑↑↑↑↑↑↑↑    ↑↑↑↑↑↑↑↑↑          ↑↑↑↑↑↑↑↑   
    ↑↑↑↑↑↑↑↑↑       ↑↑↑↑↑↑↑↑↑         ↑↑↑↑↑↑↑↑↑ 
  ↑↑↑↑↑↑↑↑↑           ↑↑↑↑↑↑↑↑↑         ↑↑↑↑↑↑↑ 
 ↑↑↑↑↑↑↑↑              ↑↑↑↑↑↑↑↑          ↑↑↑↑↑↑ 
 ↑↑↑↑↑↑↑                 ↑↑↑↑↑↑          ↑↑↑↑↑↑ 
 ↑↑↑↑↑↑↑                 ↑↑↑↑↑↑          ↑↑↑↑↑↑ 
 ↑↑↑↑↑↑↑                 ↑↑↑↑↑↑          ↑↑↑↑↑↑ 
 ↑↑↑↑↑↑↑                 ↑↑↑↑↑↑          ↑↑↑↑↑↑ 
 ↑↑↑↑↑↑↑                 ↑↑↑↑↑↑          ↑↑↑↑↑↑ 
 ↑↑↑↑↑↑↑                 ↑↑↑↑↑↑          ↑↑↑↑↑↑ 
 ↑↑↑↑↑↑↑                 ↑↑↑↑↑↑          ↑↑↑↑↑↑ 
 ↑↑↑↑↑↑↑                 ↑↑↑↑↑↑          ↑↑↑↑↑↑ 
                                                
 ]],
        -- stylua: ignore
        ---@type snacks.dashboard.Item[]
        keys = {
          { icon = " ", key = "f", desc = "Find File", action = ":lua Snacks.dashboard.pick('files')" },
          { icon = " ", key = "n", desc = "New File", action = ":ene | startinsert" },
          { icon = " ", key = "g", desc = "Find Text", action = ":lua Snacks.dashboard.pick('live_grep')" },
          { icon = " ", key = "r", desc = "Recent Files", action = ":lua Snacks.dashboard.pick('oldfiles')" },
          { icon = " ", key = "o", desc = "Open obsidian note", action = ":Obsidian quick_switch" },
          { icon = " ", key = "c", desc = "Config", action = ":lua Snacks.dashboard.pick('files', {cwd = vim.fn.stdpath('config')})" },
          { icon = " ", key = "s", desc = "Restore Session", section = "session" },
          { icon = "󰒲 ", key = "l", desc = "Lazy", action = ":Lazy" },
          { icon = " ", key = "q", desc = "Quit", action = ":qa" },
        },
      },

      sections = {
        { section = "header" },
        { section = "keys", gap = 1, padding = 2 },

        -- Section to show CWD
        function()
          local cwd = vim.fn.fnamemodify(vim.fn.getcwd(), ":~")

          return {
            text = {
              { "  ", hl = "SnacksDashboardIcon" },
              { cwd, hl = "SnacksDashboardDesc" },
            },
            align = "center",
            padding = 1,
          }
        end,

        -- Section to show concise git status
        function()
          local root = Snacks.git.get_root()
          if not root then
            return {}
          end

          local function git(args)
            local result = vim.system(vim.list_extend({ "git", "-C", root }, args), { text = true }):wait()

            return vim.trim(result.stdout or "")
          end

          local branch = git({ "branch", "--show-current" })
          local status = git({ "status", "--porcelain" })

          local modified = 0
          local added = 0
          local deleted = 0
          local untracked = 0

          for line in status:gmatch("[^\r\n]+") do
            local x, y = line:sub(1, 1), line:sub(2, 2)

            if x == "?" and y == "?" then
              untracked = untracked + 1
            elseif x == "D" or y == "D" then
              deleted = deleted + 1
            elseif x == "A" or y == "A" then
              added = added + 1
            else
              modified = modified + 1
            end
          end

          local parts = { " " .. branch }

          if modified > 0 then
            table.insert(parts, modified .. " modified")
          end

          if added > 0 then
            table.insert(parts, added .. " added")
          end

          if deleted > 0 then
            table.insert(parts, deleted .. " deleted")
          end

          if untracked > 0 then
            table.insert(parts, untracked .. " untracked")
          end

          return {
            text = {
              { " ", hl = "SnacksDashboardIcon" },
              { branch, hl = "SnacksDashboardDesc" },

              modified > 0 and { "  •  " .. modified .. " modified", hl = "SnacksDashboardDesc" } or nil,
              added > 0 and { "  •  " .. added .. " added", hl = "SnacksDashboardDesc" } or nil,
              deleted > 0 and { "  •  " .. deleted .. " deleted", hl = "SnacksDashboardDesc" } or nil,
              untracked > 0 and { "  •  " .. untracked .. " untracked", hl = "SnacksDashboardDesc" } or nil,
            },
            align = "center",
            padding = 1,
          }
        end,
      },
    },
  },
}

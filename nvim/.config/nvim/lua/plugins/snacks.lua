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
      width = 100,
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
          { icon = " ", key = "b", desc = "Browse to Repo", action = ":lua Snacks.gitbrowse()" },
          { icon = "󰒲 ", key = "l", desc = "Lazy", action = ":Lazy" },
          { icon = " ", key = "q", desc = "Quit", action = ":qa" },
        },
      },

      sections = {
        { section = "header" },

        function()
          local cwd = vim.fn.fnamemodify(vim.fn.getcwd(), ":~")
          return {
            icon = " ",
            title = cwd,
            padding = 1,
          }
        end,

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

          local icon = branch and " " or " "
          return {
            icon = icon,
            title = branch or "Not in a git repo",
            padding = 2,
          }
        end,
        { section = "keys", gap = 1, padding = 2 },

        function()
          local in_git = Snacks.git.get_root() ~= nil
          local cmds = {
            {
              title = "GH Notifications",
              cmd = "gh notify -asf 'Haysto' -n 8",
              action = function()
                vim.ui.open("https://github.com/notifications?query=org%3AHaysto")
              end,
              key = "N",
              icon = " ",
              height = 20,
              enabled = true,
            },
            {
              icon = " ",
              title = "My open PRs",
              cmd = "gh pr list -L 5 --author @me",
              key = "P",
              action = function()
                vim.fn.jobstart("gh pr list --web --author @me", { detach = true })
              end,
              height = 7,
            },
            {
              icon = " ",
              title = "Git Status",
              cmd = "if [ -z \"$(git status --porcelain)\" ]; then echo 'Working tree clean'; else git --no-pager diff --stat -B -M -C; fi",
              height = 10,
            },
          }
          return vim.tbl_map(function(cmd)
            return vim.tbl_extend("force", {
              pane = 2,
              section = "terminal",
              enabled = in_git,
              padding = 1,
              ttl = 5 * 60,
              indent = 3,
              width = 90,
              footer = false,
            }, cmd)
          end, cmds)
        end,
      },
    },
  },
}

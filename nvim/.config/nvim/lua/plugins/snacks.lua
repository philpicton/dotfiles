-- Custom header function for my digitickets machine
local function getDTHeader()
  local hour = tonumber(os.date("%H"))

  local greeting = ""
  if hour >= 0 and hour <= 11 then
    greeting = "Good morning Phil you gorgeous muffin"
  elseif hour >= 12 and hour <= 17 then
    greeting = "Good afternoon Phil you absolute legend"
  elseif tonumber(hour) >= 18 and tonumber(hour) <= 23 then
    greeting = "Good evening Phil what you doing working? Turn it off mate"
  end

  local header = [[
            xxx                                                              
          xxxxxxx                                                            
        000Qnxxxxxx                                                          
      0000000Xxxxxxxr                                                        
    0000000JXXXzxxxxxrx        ____  _       _ _____ _      _        _       
  0000000mwwmYXXXzxxxxr/~     |  _ \(_) __ _(_)_   _(_) ___| | _____| |_ ___ 
0000000Zwwwwp YXz)1(r|~~~~~   | | | | |/ _` | | | | | |/ __| |/ / _ \ __/ __|
00000JYOwm000 11111}~~~~~~~   | |_| | | (_| | | | | | | (__|   <  __/ |_\__ \
  0JXXXXYQQQQJ)11{~~~~~~~     |____/|_|\__, |_| |_| |_|\___|_|\_\___|\__|___/
    YXXXXXYQQQQc~~~~~~~                |___/                                 
      XXXXXXYJ_~~~~~~                                                        
        XXXXXXc_~~~                                                          
          YYXXXXz                                                            
            YXY                                                              
]]
  header = header .. "\n" .. greeting
  return header
end

-- Are we on my DT mbp?
if vim.fn.hostname() == "Phils-MacBook-Pro.local" then
  return {
    "folke/snacks.nvim",
    opts = {
      dashboard = {
        preset = {
          header = getDTHeader(),
        -- stylua: ignore
        ---@type snacks.dashboard.Item[]
        keys = {
          { icon = " ", key = "f", desc = "Find File", action = ":lua Snacks.dashboard.pick('files')" },
          { icon = " ", key = "n", desc = "New File", action = ":ene | startinsert" },
          { icon = " ", key = "g", desc = "Find Text", action = ":lua Snacks.dashboard.pick('live_grep')" },
          { icon = " ", key = "r", desc = "Recent Files", action = ":lua Snacks.dashboard.pick('oldfiles')" },
          { icon = " ", key = "c", desc = "Config", action = ":lua Snacks.dashboard.pick('files', {cwd = vim.fn.stdpath('config')})" },
          { icon = " ", key = "s", desc = "Restore Session", section = "session" },
          { icon = " ", key = "v", desc = "DT Open vue3 folder", action = ":lua Snacks.dashboard.pick('files', {cwd = '~/dt/app/ui/backoffice-vue3'})" },
          { icon = " ", key = "a", desc = "DT Open app folder", action = ":lua Snacks.dashboard.pick('files', {cwd = '~/dt/app'})" },
          { icon = "󰒲 ", key = "l", desc = "Lazy", action = ":Lazy" },
          { icon = " ", key = "q", desc = "Quit", action = ":qa" },
        },
        },
      },
    },
    keys = {
      {
        "<leader>su",
        function()
          Snacks.picker.undo()
        end,
        desc = "Undotree",
      },
    },
  }
end
-- If not here's the default snacks setup
return {
  "folke/snacks.nvim",
  config = function(_, opts)
    require("snacks").setup(opts)

    local color = "#ff1515"

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
    dashboard = {
      preset = {
        header = [[
                                                                                                          
                                  █████  ██      ████          █████  █                                   
                               ████████████   ██████████   ████████████                                   
                              █████     ███  ████   █████ █████      ██                                   
                              ██████        █████    █████ █████                                          
                              ████████      █████    █████ ████████                                       
                               ███████████  █████    █████  ██████████                                    
                                  █████████ █████    █████     ████████                                   
             █████████████████ ██    ██████ █████    █████ ██    ██████ ████████████████                  
                               ████  █████   ████████████  ████  █████                                    
             ████████    ████  ██████████     ██████████   ██████████        ██████  █                    
              █████████  ███                                              ████████████                    
              ██████████ ███  ████████████ ███████████   ██████████      ██████     ██                    
              ██████████████  ██████  ████ █████  █████   ████████████  ████████     █                    
              ███ ██████████   ████      █  ████   ████   █████   █████  █████████                        
              ███   ████████   ████████  █  ████  ████    █████    █████  ███████████                     
              ███    ███████   █████████    █████████     █████     ████    ███████████                   
              ███      █████   █████        ██████████    █████     ████       █████████                  
              ███       ████   █████     █  █████ █████   █████     ████ █       ███████                  
              ███        ███   ████     ██  █████  ████    ████    █████ ███      █████                   
              █████      ███   ████   ████ █████   ██████ █████  ██████  ██████████████                   
             ██████     █████ ███████████  ██████  ██████ ███████████    ████████████                     
                                                                                                          
             ███████████████████████████████████████████████████████████████████████████                  
                                                                                                          
 ]],
        -- stylua: ignore
        ---@type snacks.dashboard.Item[]
        keys = {
          { icon = " ", key = "f", desc = "Find File", action = ":lua Snacks.dashboard.pick('files')" },
          { icon = " ", key = "n", desc = "New File", action = ":ene | startinsert" },
          { icon = " ", key = "g", desc = "Find Text", action = ":lua Snacks.dashboard.pick('live_grep')" },
          { icon = " ", key = "r", desc = "Recent Files", action = ":lua Snacks.dashboard.pick('oldfiles')" },
          { icon = " ", key = "c", desc = "Config", action = ":lua Snacks.dashboard.pick('files', {cwd = vim.fn.stdpath('config')})" },
          { icon = "", key = "a", desc = "Copilot Chat", action = ":CopilotChat" },
          { icon = " ", key = "s", desc = "Restore Session", section = "session" },
          { icon = "󰒲 ", key = "l", desc = "Lazy", action = ":Lazy" },
          { icon = " ", key = "q", desc = "Quit", action = ":qa" },
        },
      },
    },
  },
}

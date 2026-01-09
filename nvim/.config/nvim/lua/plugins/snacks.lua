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
          { icon = " ", key = "c", desc = "Config", action = ":lua Snacks.dashboard.pick('files', {cwd = vim.fn.stdpath('config')})" },
          { icon = " ", key = "s", desc = "Restore Session", section = "session" },
          { icon = "󰒲 ", key = "l", desc = "Lazy", action = ":Lazy" },
          { icon = " ", key = "q", desc = "Quit", action = ":qa" },
        },
      },
    },
  },
}

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
  }
end
-- If not here's the default snacks setup
return {
  "folke/snacks.nvim",
  opts = {
    dashboard = {
      preset = {
        header = [[
                c==o                                                        
              _/____\_                                                      
       _.,--'" ||^ || "`z._                                                 
      /_/^ ___\||  || _/o\ "`-._                                            
    _/  ]. L_| || .||  \_/_  . _`--._                                       
   /_~7  _ . " ||. || /] \ ]. (_)  . "`--.                                  
  |__7~.(_)_ []|+--+|/____T_____________L|                                  
  |__|  _^(_) /^   __\____ _   _|                                           
  |__| (_){_) J ]K{__ L___ _   _]                                           
  |__| . _(_) \v     /__________|________                                   
  l__l_ (_). []|+-+-<\^   L  . _   - ---L|                                  
   \__\    __. ||^l  \Y] /_]  (_) .  _,--'                                  
     \~_]  L_| || .\ .\\/~.    _,--'"                                       
      \_\ . __/||  |\  \`-+-<'"                                             
        "`---._|J__L|X o~~|[\\      "Millenium Falcon"                      
               \____/ \___|[//      Modified Corellian YT-1300 Transport (1)
                `--'   `--+-'                                               

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

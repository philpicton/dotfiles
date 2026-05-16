local milli_opts = { splash = "fire", loop = true }

return {
  "folke/snacks.nvim",
  dependencies = { "amansingh-afk/milli.nvim" },
  priority = 1000,
  lazy = false,
  opts = function(_, opts)
    local milli = require("milli")
    local splash = milli.load(milli_opts)

    opts.image = {
      resolve = function(path, src)
        local api = require("obsidian.api")
        if api.path_is_note(path) then
          return api.resolve_attachment_path(src)
        end
      end,
    }

    opts.dashboard = vim.tbl_deep_extend("force", opts.dashboard or {}, {
      enabled = true,
      preset = {
        header = table.concat(splash.frames[1], "\n"),
      },
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
      sections = {
        { section = "header", padding = 1 },
        { section = "keys", gap = 1, padding = 1 },
        { section = "startup" },
      },
    })

    return opts
  end,
  config = function(_, opts)
    local milli = require("milli")
    local notify = vim.notify

    local function find_dashboard_buf()
      for _, win in ipairs(vim.api.nvim_list_wins()) do
        local buf = vim.api.nvim_win_get_buf(win)
        if vim.bo[buf].filetype == "snacks_dashboard" then
          return buf
        end
      end
    end

    local function attach_milli()
      local buf = find_dashboard_buf()
      if not buf or vim.b[buf].milli_attached then
        return
      end

      milli.play(buf, milli_opts)
      vim.b[buf].milli_attached = true
      vim.api.nvim_buf_attach(buf, false, {
        on_detach = function()
          vim.b[buf].milli_attached = nil
        end,
      })
    end

    vim.api.nvim_create_autocmd("User", {
      group = vim.api.nvim_create_augroup("milli_snacks_dashboard", { clear = true }),
      pattern = { "SnacksDashboardOpened", "SnacksDashboardUpdatePost" },
      callback = function()
        vim.schedule(attach_milli)
      end,
    })

    require("snacks").setup(opts)
    if LazyVim.has("noice.nvim") then
      vim.notify = notify
    end
    vim.schedule(attach_milli)
  end,
}

-- Toggle for Copilot inline completions
return {
  {
    "folke/snacks.nvim",
    opts = function()
      Snacks.toggle({
        name = "Copilot Completions",
        get = function()
          return vim.lsp.inline_completion.is_enabled()
        end,
        set = function(state)
          vim.lsp.inline_completion.enable(state)
        end,
      }):map("<leader>ux")
    end,
  },

  -- Override lualine to show Copilot disabled state
  {
    "nvim-lualine/lualine.nvim",
    optional = true,
    event = "VeryLazy",
    opts = function(_, opts)
      local icon = LazyVim.config.icons.kinds.Copilot

      -- Remove the existing Copilot component added by copilot-native
      for i = #opts.sections.lualine_x, 1, -1 do
        local component = opts.sections.lualine_x[i]
        if type(component) == "table" and type(component[1]) == "function" then
          local ok, result = pcall(component[1])
          if ok and result == icon then
            table.remove(opts.sections.lualine_x, i)
            break
          end
        end
      end

      -- Add our custom Copilot status component that shows disabled state
      table.insert(opts.sections.lualine_x, 2, {
        function()
          return icon
        end,
        cond = function()
          -- Always show the icon (when copilot client exists or is disabled)
          local clients = vim.lsp.get_clients({ name = "copilot", bufnr = 0 })
          return #clients > 0 or not vim.lsp.inline_completion.is_enabled()
        end,
        color = function()
          -- Grey/dim when disabled, normal colors otherwise
          if not vim.lsp.inline_completion.is_enabled() then
            return { fg = Snacks.util.color("Comment") }
          end
          return { fg = Snacks.util.color("Special") }
        end,
      })
    end,
  },
}

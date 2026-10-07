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
      }):map("<leader>ac")
      Snacks.toggle({
        name = "Copilot NES",
        get = function()
          return require("sidekick.nes").enabled
        end,
        set = function(state)
          require("sidekick.nes").enable(state)
        end,
      }):map("<leader>an")
    end,
  },
}

return {
  {
    "saghen/blink.cmp",
    ---@module 'blink.cmp'
    ---@type blink.cmp.Config
    opts = { -- 'default' for mappings similar to built-in completion
      -- 'super-tab' for mappings similar to vscode (tab to accept, arrow keys to navigate)
      -- 'enter' for mappings similar to 'super-tab' but with 'enter' to accept
      -- see the "default configuration" section below for full documentation on how to define
      -- your own keymap.
      keymap = {
        preset = "super-tab",
        ["<Tab>"] = {
          function()
            -- Prefer AI on <Tab> (Sidekick NES and/or Neovim inline completions).
            local ok, sidekick = pcall(require, "sidekick")
            if ok and sidekick.nes_jump_or_apply and sidekick.nes_jump_or_apply() then
              return true
            end
          end,
          function()
            if vim.lsp.inline_completion and vim.lsp.inline_completion.get then
              return vim.lsp.inline_completion.get()
            end
          end,
          "snippet_forward",
          "fallback", -- insert a literal tab / whatever your non-blink mapping does
        },

        ["<S-Tab>"] = {
          function(cmp)
            -- Use <S-Tab> to accept the currently selected completion item.
            return cmp.select_and_accept()
          end,
          "snippet_backward",
          "fallback",
        },
        -- ["<S-CR>"] = { "select_and_accept" },
        -- ["<CR>"] = { "fallback" },
        -- ["<Tab>"] = {
        --   LazyVim.cmp.map({ "snippet_forward", "ai_accept" }),
        --   "fallback",
        -- },
      },
    },
  },
}

-- Autocmds are automatically loaded on the VeryLazy event
-- Default autocmds that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/autocmds.lua
-- Add any additional autocmds here

-- Disable diagnostics for .env files
-- Linter treats them as bash files, and complains about unused variables
local lsp_hacks = vim.api.nvim_create_augroup("LspHacks", { clear = true })

vim.api.nvim_create_autocmd({ "BufNewFile", "BufReadPost" }, {
  group = lsp_hacks,
  pattern = ".env*",
  callback = function(e)
    vim.diagnostic.enable(false, { bufnr = e.buf })
  end,
})
vim.api.nvim_create_user_command("Dash", function()
  local win = vim.api.nvim_get_current_win()

  Snacks.bufdelete({
    filter = function(buf)
      return vim.bo[buf].filetype ~= "snacks_dashboard"
    end,
  })

  vim.schedule(function()
    Snacks.dashboard.open({ win = win })
  end)
end, {
  desc = "Close all buffers and open dashboard",
})

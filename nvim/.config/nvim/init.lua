local vue_syntax_fallback = vim.api.nvim_create_augroup("vue_syntax_fallback", { clear = true })

local function set_vue_syntax(buf)
  if not vim.api.nvim_buf_is_valid(buf) or vim.bo[buf].filetype ~= "vue" then
    return
  end

  vim.schedule(function()
    if vim.api.nvim_buf_is_valid(buf) then
      vim.api.nvim_buf_call(buf, function()
        -- Tailwind @apply directives in lang="scss" blocks can leave large
        -- Treesitter error nodes, so keep Vue's regex syntax active too.
        vim.cmd("setlocal syntax=vue")
      end)
    end
  end)
end

vim.api.nvim_create_autocmd({ "FileType", "BufEnter" }, {
  group = vue_syntax_fallback,
  pattern = { "*.vue", "vue" },
  callback = function(event) set_vue_syntax(event.buf) end,
})

vim.api.nvim_create_autocmd("VimEnter", {
  group = vue_syntax_fallback,
  callback = function() set_vue_syntax(vim.api.nvim_get_current_buf()) end,
})

-- bootstrap lazy.nvim, LazyVim and your plugins
require("config.lazy")

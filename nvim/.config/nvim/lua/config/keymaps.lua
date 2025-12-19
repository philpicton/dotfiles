-- Keymaps are automatically loaded on the VeryLazy event
-- Default keymaps that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/keymaps.lua
-- Add any additional keymaps here

-- Relative or absolute number lines
vim.cmd([[
function! NumberToggle()
if(&nu == 1)
set nu!
set rnu
else
set nornu
set nu
endif
endfunction
]])

-- Toggle relative line numbers
vim.keymap.set("n", "<leader>8", ":call NumberToggle()<CR>", { desc = "Toggle relative line numbers" })

-- Move lines up and down
vim.keymap.set({ "n", "v" }, "<C-S-Down>", ":MoveLine(1)<CR>", { desc = "Move line down" })
vim.keymap.set({ "n", "v" }, "<C-S-Up>", ":MoveLine(-1)<CR>", { desc = "Move line up" })

-- Git diff pick left or right
vim.keymap.set("n", "<leader>g2", ":diffget //2<cr>", { desc = "diff get //2" })
vim.keymap.set("n", "<leader>g3", ":diffget //3<cr>", { desc = "diff get //3" })
-- vim.keymap.set("n", "<leader>gd", ":Gvdiffsplit!`<cr>", { desc = "3 way diff split" })

-- Lazydocker
vim.keymap.set("n", "<leader>k", "<cmd>LazyDocker<CR>", { desc = "Toggle LazyDocker", noremap = true, silent = true })

-- Save file with Cmd+S (macOS) or Ctrl+S
vim.keymap.set({ "n", "i", "v" }, "<D-s>", "<cmd>w<CR>", { desc = "Save file" })

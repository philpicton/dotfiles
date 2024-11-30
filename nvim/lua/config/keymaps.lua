-- Keymaps are automatically loaded on the VeryLazy event
-- Default keymaps that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/keymaps.lua
-- Add any additional keymaps here

-- leader key is space
vim.g.mapleader = " "

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

-- Toggle live grep
vim.keymap.set({ "n", "v" }, "<leader>gf", ":Telescope live_grep<CR>", { desc = "Telescope live grep" })

-- Git diff pick left or right
vim.keymap.set("n", "<leader>g2", ":diffget //2<cr>", { desc = "diff get //2" })
vim.keymap.set("n", "<leader>g3", ":diffget //3<cr>", { desc = "diff get //3" })
vim.keymap.set("n", "<leader>gd", ":Gvdiffsplit!`<cr>", { desc = "3 way diff split" })

-- Buffer Navigation
vim.keymap.set({ "n", "v" }, "<leader><Right>", ":bnext<CR>", { desc = "Buffer right" })
vim.keymap.set({ "n", "v" }, "<leader><Left>", ":bprevious<CR>", { desc = "Buffer left" })

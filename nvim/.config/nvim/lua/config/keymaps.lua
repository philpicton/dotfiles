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

-- Buffer Navigation
vim.keymap.set({ "n", "v" }, "<leader><Right>", ":bnext<CR>", { desc = "Buffer right" })
vim.keymap.set({ "n", "v" }, "<leader><Left>", ":bprevious<CR>", { desc = "Buffer left" })

-- Lazydocker
vim.keymap.set("n", "<leader>k", "<cmd>LazyDocker<CR>", { desc = "Toggle LazyDocker", noremap = true, silent = true })

-- Git blame
vim.keymap.set({ "n" }, "<leader>gt", ":GitBlameToggle<CR>", { desc = "Toggle Git Blame" })
vim.keymap.set({ "n" }, "<leader>gy", ":GitBlameCopySHA<CR>", { desc = "Copy Commit SHA" })
vim.keymap.set({ "n" }, "<leader>go", ":GitBlameOpenFileURL<CR>", { desc = "Browse to file in gh/bb" })

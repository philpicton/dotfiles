return {
  "obsidian-nvim/obsidian.nvim",
  version = "*", -- use latest release, remove to use latest commit
  lazy = false,
  dependencies = {
    "nvim-lua/plenary.nvim",
  },
  ---@module 'obsidian'
  ---@type obsidian.config
  opts = {
    ui = { enable = false },
    legacy_commands = false,
    workspaces = {
      {
        name = "Haysto",
        path = "/Users/phil/Documents/Obsidian/Haysto",
      },
    },
  },
}

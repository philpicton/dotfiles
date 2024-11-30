return {
  -- add night-owl
  { "oxfist/night-owl.nvim" },

  -- Configure LazyVim to load nightowl
  {
    "LazyVim/LazyVim",
    opts = {
      colorscheme = "night-owl",
      -- colorscheme = "tokyonight",
      -- colorscheme = "catppuccin-mocha",
    },
  },
}

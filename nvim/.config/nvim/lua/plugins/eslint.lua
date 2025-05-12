return {
  "neovim/nvim-lspconfig",
  opts = {
    servers = {
      eslint = {
        -- Custom root_dir logic to support both flat and classic ESLint config
        root_dir = function(fname)
          local util = require("lspconfig.util")
          -- Prefer flat config (TypeScript version)
          return util.root_pattern("eslint.config.ts")(fname)
            or util.root_pattern("eslint.config.js")(fname) -- fallback to JS flat config
            or util.root_pattern(".eslintrc.js", ".eslintrc.json", ".eslintrc")(fname)
        end,
        settings = {
          workingDirectory = { mode = "auto" },
        },
      },
    },
  },
}

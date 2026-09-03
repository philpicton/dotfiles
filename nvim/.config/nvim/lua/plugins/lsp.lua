return {
  -- use the eslint in the container for haysto stack.
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        eslint = {
          root_dir = function(bufnr, on_dir)
            local filename = vim.api.nvim_buf_get_name(bufnr)
            if filename:find(vim.fn.expand("~/code/haysto-v2"), 1, true) == 1 then
              return
            end

            -- not haysto specific...
            local root_markers = { "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "bun.lock" }
            root_markers = vim.fn.has("nvim-0.11.3") == 1 and { root_markers, { ".git" } }
              or vim.list_extend(root_markers, { ".git" })

            if vim.fs.root(bufnr, { "deno.json", "deno.jsonc", "deno.lock" }) then
              return
            end

            local project_root = vim.fs.root(bufnr, root_markers) or vim.fn.getcwd()
            local eslint_config_files = {
              ".eslintrc",
              ".eslintrc.js",
              ".eslintrc.cjs",
              ".eslintrc.yaml",
              ".eslintrc.yml",
              ".eslintrc.json",
              "eslint.config.js",
              "eslint.config.mjs",
              "eslint.config.cjs",
              "eslint.config.ts",
              "eslint.config.mts",
              "eslint.config.cts",
            }
            local config_files =
              require("lspconfig.util").insert_package_json(eslint_config_files, "eslintConfig", filename)
            local uses_eslint = vim.fs.find(config_files, {
              path = filename,
              type = "file",
              limit = 1,
              upward = true,
              stop = vim.fs.dirname(project_root),
            })[1]

            if uses_eslint then
              on_dir(project_root)
            end
          end,
        },
        cssls = {
          filetypes = { "css", "scss", "less" },
        },
        vue_ls = {
          -- vue_ls owns the embedded HTML/CSS sections for .vue buffers.
          settings = {
            css = {
              validate = true,
              lint = {
                unknownAtRules = "ignore",
              },
            },
            scss = {
              validate = true,
              lint = {
                unknownAtRules = "ignore",
              },
            },
            less = {
              validate = true,
              lint = {
                unknownAtRules = "ignore",
              },
            },
          },
        },
      },
    },
  },
}

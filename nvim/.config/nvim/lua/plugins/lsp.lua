return {
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        cssls = {
          filetypes = { "css", "scss", "less", "vue" },
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

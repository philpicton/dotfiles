-- This is to disable the ultra annoying line length markdownlint rule
-- which complains on every line in a md file longer than 80 chars
-- It looks for the file below, a yaml file which disables that rule
-- aaaah that's better!

local HOME = os.getenv("HOME")
return {
  "mfussenegger/nvim-lint",
  optional = true,
  opts = {
    linters = {
      ["markdownlint-cli2"] = {
        args = { "--config", HOME .. "/.config/nvim/.markdownlint-cli2.yaml", "--" },
      },
    },
  },
}

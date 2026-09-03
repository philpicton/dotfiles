local HOME = os.getenv("HOME")
local HAYSTO_ROOT = HOME .. "/code/haysto-v2"
local HAYSTO_APPS = {
  ["haysto-v2-create"] = "haysto-create",
  ["haysto-v2-collect"] = "haysto-collect",
  ["haysto-v2-collaborate"] = "haysto-collaborate",
}

local function haysto_app_for_file(filename)
  local relative = filename:sub(#HAYSTO_ROOT + 2)
  local app = relative:match("^([^/]+)/")

  return app and HAYSTO_APPS[app] or nil
end

local function haysto_container_filename(filename)
  local relative = filename:sub(#HAYSTO_ROOT + 2)
  local app, app_relative = relative:match("^([^/]+)/(.*)$")

  if not app then
    return filename
  end

  if HAYSTO_APPS[app] then
    return "/var/www/" .. app_relative
  end

  if relative:find("^lib/js/haysto%-v2%-lib_shared/") then
    return "/var/www/" .. relative
  end

  return filename
end

return {
  "mfussenegger/nvim-lint",
  optional = true,
  opts = {
    linters = {
      -- This is to disable the ultra annoying line length markdownlint rule
      -- which complains on every line in a md file longer than 80 chars
      -- It looks for the file below, a yaml file which disables that rule
      -- aaaah that's better!
      ["markdownlint-cli2"] = {
        args = { "--config", HOME .. "/.config/nvim/.markdownlint-cli2.yaml", "--" },
      },
      -- Haysto specific eslint linter that runs inside the haysto docker container.
      haysto_eslint = {
        condition = function(ctx)
          return ctx.filename:find(HAYSTO_ROOT, 1, true) == 1
        end,
        cmd = "docker",
        args = {
          "compose",
          "-f",
          "docker-compose.yml",
          "-f",
          "docker-compose.local.yml",
          "-f",
          "docker-compose.override.yml",
          "--profile",
          "local",
          "exec",
          "-T",
          function()
            return haysto_app_for_file(vim.api.nvim_buf_get_name(0)) or "haysto-create"
          end,
          "npx",
          "eslint",
          "--format",
          "json",
          "--stdin",
          "--stdin-filename",
          function()
            return haysto_container_filename(vim.api.nvim_buf_get_name(0))
          end,
        },
        cwd = HAYSTO_ROOT,
        stdin = true,
        stream = "stdout",
        ignore_exitcode = true,
        parser = function(output, bufnr)
          local diagnostics = require("lint.linters.eslint").parser(output, bufnr)
          for _, diagnostic in ipairs(diagnostics) do
            diagnostic.source = "haysto-eslint"
          end

          return diagnostics
        end,
      },
    },
    linters_by_ft = {
      javascript = { "haysto_eslint" },
      typescript = { "haysto_eslint" },
      vue = { "haysto_eslint" },
    },
  },
}

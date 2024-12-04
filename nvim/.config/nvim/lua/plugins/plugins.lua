return {
  -- move lines up and down
  { "fedepujol/move.nvim" },
  -- git commands, :Git whatever
  { "tpope/vim-fugitive" },
  -- git blame
  { "f-person/git-blame.nvim" },
  -- {
  --   "David-Kunz/gen.nvim",
  --   opts = {
  --     model = "qwen2.5-coder:14b", -- The default model to use.
  --     quit_map = "q", -- set keymap to close the response window
  --     retry_map = "<c-r>", -- set keymap to re-send the current prompt
  --     accept_map = "<c-cr>", -- set keymap to replace the previous selection with the last result
  --     host = "localhost", -- The host running the Ollama service.
  --     port = "11434", -- The port on which the Ollama service is listening.
  --     display_mode = "split", -- The display mode. Can be "float" or "split" or "horizontal-split".
  --     show_prompt = false, -- Shows the prompt submitted to Ollama.
  --     show_model = true, -- Displays which model you are using at the beginning of your chat session.
  --     no_auto_close = false, -- Never closes the window automatically.
  --     file = false, -- Write the payload to a temporary file to keep the command short.
  --     hidden = false, -- Hide the generation window (if true, will implicitly set `prompt.replace = true`), requires Neovim >= 0.10
  --     init = function(options)
  --       pcall(io.popen, "ollama serve > /dev/null 2>&1 &")
  --     end,
  --     -- Function to initialize Ollama
  --     command = function(options)
  --       local body = { model = options.model, stream = true }
  --       return "curl --silent --no-buffer -X POST http://"
  --         .. options.host
  --         .. ":"
  --         .. options.port
  --         .. "/api/chat -d $body"
  --     end,
  --     -- The command for the Ollama service. You can use placeholders $prompt, $model and $body (shellescaped).
  --     -- This can also be a command string.
  --     -- The executed command must return a JSON object with { response, context }
  --     -- (context property is optional).
  --     -- list_models = '<omitted lua function>', -- Retrieves a list of model names
  --     debug = false, -- Prints errors and the command which is run.
  --   },
  -- },
  {
    "hrsh7th/nvim-cmp",
    ---@param opts cmp.ConfigSchema
    opts = function(_, opts)
      local has_words_before = function()
        unpack = unpack or table.unpack
        local line, col = unpack(vim.api.nvim_win_get_cursor(0))
        return col ~= 0 and vim.api.nvim_buf_get_lines(0, line - 1, line, true)[1]:sub(col, col):match("%s") == nil
      end

      local cmp = require("cmp")

      opts.mapping = vim.tbl_extend("force", opts.mapping, {
        ["<Tab>"] = cmp.mapping(function(fallback)
          if cmp.visible() then
            -- You could replace select_next_item() with confirm({ select = true }) to get VS Code autocompletion behavior
            cmp.select_next_item()
          elseif vim.snippet.active({ direction = 1 }) then
            vim.schedule(function()
              vim.snippet.jump(1)
            end)
          elseif has_words_before() then
            cmp.complete()
          else
            fallback()
          end
        end, { "i", "s" }),
        ["<S-Tab>"] = cmp.mapping(function(fallback)
          if cmp.visible() then
            cmp.select_prev_item()
          elseif vim.snippet.active({ direction = -1 }) then
            vim.schedule(function()
              vim.snippet.jump(-1)
            end)
          else
            fallback()
          end
        end, { "i", "s" }),
        ["<CR>"] = cmp.mapping({
          i = function(fallback)
            if cmp.visible() and cmp.get_active_entry() then
              cmp.confirm({ behavior = cmp.ConfirmBehavior.Replace, select = false })
            else
              fallback()
            end
          end,
          s = cmp.mapping.confirm({ select = true }),
          c = cmp.mapping.confirm({ behavior = cmp.ConfirmBehavior.Replace, select = true }),
        }),
      })
    end,
  },
}

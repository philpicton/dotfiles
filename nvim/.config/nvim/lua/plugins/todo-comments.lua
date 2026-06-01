local pill = {
  left = "",
  right = "",
}

local function add_pill_edge(buf, ns, line, col, text, hl)
  vim.api.nvim_buf_set_extmark(buf, ns, line, col, {
    virt_text = { { text, hl } },
    virt_text_pos = "inline",
    priority = 501,
  })
end

local function pill_cols(line, start, finish)
  local left = start - 1
  local right = finish - 1

  local prev = start > 1 and line:sub(start - 1, start - 1) or nil

  if prev == "@" then
    left = left - 1
  end

  return math.max(left, 0), math.min(right, #line)
end

local function patch_todo_comments()
  local config = require("todo-comments.config")
  local highlight = require("todo-comments.highlight")

  if not highlight._pill_original_highlight then
    highlight._pill_original_highlight = highlight.highlight
  end

  if not highlight._pill_patched then
    highlight.highlight = function(buf, first, last, event)
      highlight._pill_original_highlight(buf, first, last, event)

      if not vim.api.nvim_buf_is_valid(buf) then
        return
      end

      local lines = vim.api.nvim_buf_get_lines(buf, first, last + 1, false)

      for line_nr, line in ipairs(lines) do
        local ok, start, finish, kw = pcall(highlight.match, line)
        local lnum = first + line_nr - 1

        if ok and start then
          if
            config.options.highlight.comments_only
            and not highlight.is_quickfix(buf)
            and not highlight.is_comment(buf, lnum, start - 1)
          then
            kw = nil
          end
        end

        if kw then
          kw = config.keywords[kw] or kw
        end

        if kw and config.options.keywords[kw] then
          local left, right = pill_cols(line, start, finish)
          local edge_hl = "TodoFg" .. kw

          add_pill_edge(buf, config.ns, lnum, left, pill.left, edge_hl)
          add_pill_edge(buf, config.ns, lnum, right, pill.right, edge_hl)
        end
      end
    end

    highlight._pill_patched = true
  end

  local function restart_highlighter()
    if not config.loaded then
      vim.defer_fn(restart_highlighter, 10)
      return
    end

    highlight.stop()
    highlight.start()
  end

  restart_highlighter()
end

return {
  "folke/todo-comments.nvim",
  dependencies = { "nvim-lua/plenary.nvim" },
  opts = {
    signs = true, -- show icons in the signs column
    sign_priority = 8, -- sign priority
    -- keywords recognized as todo comments
    keywords = {
      FIXME = {
        icon = " ", -- icon used for the sign, and in search results
        color = "error", -- can be a hex color, or a named color (see below)
        alt = { "fixme" }, -- a set of other keywords that all map to this FIXME keyword
        -- signs = false, -- configure signs for some keywords individually
      },
      TODO = { icon = "󰳤 ", color = "info", alt = { "todo" } },
      HACK = { icon = " ", color = "warning" },
      NOTE = { icon = " ", color = "test", alt = { "INFO" } },
    },
    gui_style = {
      fg = "NONE", -- The gui style to use for the fg highlight group.
      bg = "BOLD", -- The gui style to use for the bg highlight group.
    },
    merge_keywords = false, -- when true, custom keywords will be merged with the defaults
    -- highlighting of the line containing the todo comment
    -- * before: highlights before the keyword (typically comment characters)
    -- * keyword: highlights of the keyword
    -- * after: highlights after the keyword (todo text)
    highlight = {
      multiline = true, -- enable multine todo comments
      multiline_pattern = "^.", -- lua pattern to match the next multiline from the start of the matched keyword
      multiline_context = 10, -- extra lines that will be re-evaluated when changing a line
      before = "", -- "fg" or "bg" or empty
      keyword = "bg", -- keep the background tight to the tag so the pill doesn't extend as wide
      after = "fg", -- "fg" or "bg" or empty
      -- Support bare keywords, KEYWORD:, and @KEYWORD forms consistently.
      pattern = {
        [[.*(\@((KEYWORDS)):)]],
        [[.*(\@((KEYWORDS))>)]],
        [[.*<((KEYWORDS):)]],
        [[.*<((KEYWORDS))>]],
      }, -- pattern or table of patterns, used for highlighting (vim regex)
      comments_only = true, -- uses treesitter to match keywords in comments only
      max_line_len = 400, -- ignore lines longer than this
      exclude = {}, -- list of file types to exclude highlighting
    },
    -- list of named colors where we try to extract the guifg from the
    -- list of highlight groups or use the hex color if hl not found as a fallback
    colors = {
      error = { "DiagnosticError", "ErrorMsg", "#DC2626" },
      warning = { "DiagnosticWarn", "WarningMsg", "#FBBF24" },
      info = { "DiagnosticInfo", "#2563EB" },
      hint = { "DiagnosticHint", "#10B981" },
      default = { "Identifier", "#7C3AED" },
      test = { "Identifier", "#FF00FF" },
    },
    search = {
      command = "rg",
      args = {
        "--color=never",
        "--no-heading",
        "--with-filename",
        "--line-number",
        "--column",
      },
      -- regex that will be used to match keywords.
      -- don't replace the (KEYWORDS) placeholder
      pattern = [[\b(KEYWORDS):|\b(KEYWORDS)\b|@(KEYWORDS):|@(KEYWORDS)\b]], -- ripgrep regex
    },
  },
  config = function(_, opts)
    require("todo-comments").setup(opts)
    patch_todo_comments()
  end,
}

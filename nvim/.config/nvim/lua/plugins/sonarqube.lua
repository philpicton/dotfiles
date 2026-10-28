-- SonarQube for IDE (sonarlint-language-server) via sonarqube.nvim.
--
-- The server lives in ~/.local/share/nvim/sonarqube/extension, unpacked from the
-- *darwin-arm64* sonarlint-vscode vsix, which bundles its own JRE in extension/jre/
-- (so no system Java is needed). The generic vsix that :SonarQubeInstallLsp downloads
-- has no JRE, so don't use that command.
--
-- Updating:
--   Plugin:            :Lazy update sonarqube.nvim
--   Server + runtime:  download the latest darwin-arm64 vsix and replace the extension dir
--     (server, analyzers and JRE all come from the same release this way):
--
--     dir=~/.local/share/nvim/sonarqube
--     url=$(curl -sL https://api.github.com/repos/SonarSource/sonarlint-vscode/releases/latest \
--       | jq -r '.assets[] | select(.name | test("darwin-arm64")) | .browser_download_url')
--     curl -L -o /tmp/sonarlint.vsix "$url"
--     rm -rf "$dir/extension"
--     unzip -q /tmp/sonarlint.vsix 'extension/*' -d "$dir" && rm /tmp/sonarlint.vsix
--
--   Then restart nvim. If the server fails to start, check `:LspLog` and compare the
--   analyzer jars below against `ls ~/.local/share/nvim/sonarqube/extension/analyzers`.
return {
  "iamkarasik/sonarqube.nvim",
  config = function()
    local extension_dir = vim.fn.stdpath("data") .. "/sonarqube/extension"
    local analyzers_dir = extension_dir .. "/analyzers"

    -- Use the bundled JRE (globbed, so a new JRE version still matches), falling back to java on PATH.
    local java = vim.fn.glob(extension_dir .. "/jre/*/bin/java", false, true)[1] or vim.fn.exepath("java")

    -- Must be registered before setup(), which builds the FileType autocmd from this list.
    require("sonarqube.lsp.server").register_filetypes({ "vue" })

    require("sonarqube").setup({
      lsp = {
        cmd = {
          java,
          "-jar",
          extension_dir .. "/server/sonarlint-ls.jar",
          "-stdio",
          "-analyzers",
          analyzers_dir .. "/sonargo.jar",
          analyzers_dir .. "/sonarhtml.jar",
          analyzers_dir .. "/sonariac.jar",
          analyzers_dir .. "/sonarjava.jar",
          analyzers_dir .. "/sonarjavasymbolicexecution.jar",
          analyzers_dir .. "/sonarjs.jar",
          analyzers_dir .. "/sonarphp.jar",
          analyzers_dir .. "/sonarpython.jar",
          analyzers_dir .. "/sonartext.jar",
          analyzers_dir .. "/sonarxml.jar",
        },
      },
    })
  end,
}

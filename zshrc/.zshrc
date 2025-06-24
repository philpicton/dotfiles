# Phil's zsh config for work 
#

# The tool of the righteous
export EDITOR="nvim"
export SUDO_EDITOR="$EDITOR"

# Keep the zsh history so the auto suggest can work
HISTSIZE=10000
SAVEHIST=10000
HISTFILE=~/.cache/zshhistory
setopt appendhistory

# loads NVM
# export NVM_DIR="$HOME/.nvm"
# [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh" 

# Go development
export PATH="$HOME/go/bin:$PATH"

eval "$(starship init zsh)"

function say_done() {
cat << "EOF" 
                 .-'''-.                                     ✨
_______         '   _    \                                           
\  ___ `'.    /   /` '.   \    _..._         __.....__               
 ' |--.\  \  .   |     \  '  .'     '.   .-''         '.             
 | |    \  ' |   '      |  '.   .-.   . /     .-''"'-.  `.           
 | |     |  '\    \     / / |  '   '  |/     /________\   \          
 | |     |  | `.   ` ..' /  |  |   |  ||                  |          
 | |     ' .'    '-...-'`   |  |   |  |\    .-------------'          
 | |___.' /'                |  |   |  | \    '-.____...---.          
/_______.'/                 |  |   |  |  `.             .'           
\_______|/                  |  |   |  |    `''-...... -'             
                            |  |   |  |                              
                            '--'   '--'                              
EOF
}

# Opens yazi file explorer, and CDs into the chosen folder or opens the selected file.
function y() {
	local tmp="$(mktemp -t "yazi-cwd.XXXXXX")" cwd
	yazi "$@" --cwd-file="$tmp"
	if cwd="$(command cat -- "$tmp")" && [ -n "$cwd" ] && [ "$cwd" != "$PWD" ]; then
		builtin cd -- "$cwd"
	fi
	rm -f -- "$tmp"
}

# Open all git branches in fuzzy finder then checkout the selected one
function gch() {
    local branches branch
    branches=$(git branch --all | grep -v HEAD) &&
    branch=$(echo "$branches" |
           fzf-tmux -d $(( 2 + $(wc -l <<< "$branches") )) +m) &&
    git checkout $(echo "$branch" | sed "s/.* //" | sed "s#remotes/[^/]*/##")
}

# Fuzzy search a cheat sheet of keyboard shortcuts/scripts etc 
function sc() {
  local file="$HOME/.config/shortcuts/shortcuts.txt"
  if [[ ! -f "$file" ]]; then
    echo "❌ Shortcuts file not found: $file"
    return 1
  fi

  local selected
  selected=$(cat "$file" | fzf \
    --height=40% \
    --reverse \
    --preview='echo {} | awk -F "|" "{ gsub(/^[ \t]+|[ \t]+$/, \"\", \$2); print \"\033[33m\"\$2\"\033[0m\" }"' \
    --preview-window=right:70%:wrap \
    --prompt="🔍 Search Shortcuts: " \
    --header="Enter to copy shortcut (after |) to clipboard" \
    --border=sharp \
  )

  if [[ -n "$selected" ]]; then
    local shortcut
    shortcut=$(echo "$selected" | awk -F '|' '{ gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2 }')

    if [[ -n "$shortcut" ]]; then
      if command -v pbcopy &>/dev/null; then
        echo "$shortcut" | pbcopy
      elif command -v xclip &>/dev/null; then
        echo "$shortcut" | xclip -selection clipboard
      elif command -v wl-copy &>/dev/null; then
        echo "$shortcut" | wl-copy
      else
        echo "⚠️ No clipboard tool found (pbcopy, xclip, wl-copy)"
        return 1
      fi

      echo "📋 Copied to clipboard:"
      echo "$shortcut"
    else
      echo "⚠️ Could not extract shortcut from selection."
    fi
  fi
}

# fetch and checkout
function gfc() {
  local confetty_flag=false
  local branch=""

  # Parse arguments
  for arg in "$@"; do
    if [[ "$arg" == "-c" ]]; then
      confetty_flag=true
    else
      branch="$arg"
    fi
  done

  if [[ -z "$branch" ]]; then
    echo "Usage: gfc [-c] <branch>"
    return 1
  fi
  echo "fetching..." &&
  git fetch &&
  echo "checkout..." &&
  git checkout "$branch" &&
  echo "pulling..." &&
  git pull &&
  say_done

  if $confetty_flag; then
    confetty
  fi
}

# fetch
alias gf="git fetch"

# app
alias app="cd ~/dt/app"

# vue3
alias vv="cd ~/dt/app/ui/backoffice-vue3"

# neovim
alias n="nvim"

# dont use yarn anymore
alias yarn="npm run"

# watch generator 
alias wg="cd ~/dt/app/ui/backoffice-vue3 && npm run watch-generator"

# reset all
function rst() {
    cd ~/dt/app &&
        npm run turbo-reset &&
        say_done
}

# Opens git branches in fuzzy finder and shows a list of the commits
# which are different from HEAD (your current checkout)
function gchp() {
    local tags branches target
    branches=$(
    git --no-pager branch --all \
        --format="%(if)%(HEAD)%(then)%(else)%(if:equals=HEAD)%(refname:strip=3)%(then)%(else)%1B[0;34;1mbranch%09%1B[m%(refname:short)%(end)%(end)" \
    | sed '/^$/d') || return
    tags=$(
    git --no-pager tag | awk '{print "\x1b[35;1mtag\x1b[m\t" $1}') || return
    target=$(
    (echo "$branches"; echo "$tags") |
    fzf --no-hscroll --no-multi -n 2 \
        --ansi --preview="git --no-pager log -150 --pretty=format:%s '..{2}'") || return
    git checkout $(awk '{print $2}' <<<"$target" )
}

# zsh plugins
source $(brew --prefix)/share/zsh-autocomplete/zsh-autocomplete.plugin.zsh
source $(brew --prefix)/share/zsh-autosuggestions/zsh-autosuggestions.zsh
source $(brew --prefix)/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh

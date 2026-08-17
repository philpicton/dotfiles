# Phil's zsh config for work 
#

# The tool of the righteous
export EDITOR="nvim"
export SUDO_EDITOR="$EDITOR"

# Keep the zsh history so the auto suggest can work
HISTSIZE=10000
SAVEHIST=10000
HISTFILE=~/.cache/zshhistory
mkdir -p ~/.cache
setopt appendhistory

# Go development
# export PATH="$HOME/go/bin:$PATH"

eval "$(starship init zsh)"

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
           fzf -d $(( 2 + $(wc -l <<< "$branches") )) +m) &&
    git checkout $(echo "$branch" | sed "s/.* //" | sed "s#remotes/[^/]*/##")
}

# fetch and checkout 
function gfc() {
    git fetch && git checkout $1 
}

# git aliases
alias gf="git fetch"
alias gp="git pull"
alias gpf="git push --force-with-lease"

# neovim
alias n="nvim"

# haya repo man
alias hh="python3 ~/code/scripts/repo-man.py"

# haya branch checkout
alias bco="~/code/scripts/branch-checkout/branch-checkout"

if (( ! ${+HAYA_REPOS} )); then
    typeset -ra HAYA_REPOS=(
        "$HOME/code/haysto-v2"
        "$HOME/code/haysto-v2/haysto-v2-api"
        "$HOME/code/haysto-v2/haysto-v2-collect"
        "$HOME/code/haysto-v2/haysto-v2-create"
        "$HOME/code/haysto-v2/lib/js/haysto-v2-lib_shared"
    )
fi

# Open the primary Haya repositories in separate Kitty tabs running Neovim.
function jj() {
    local repo

    if ! command -v kitty > /dev/null; then
        print -u2 'kitty is required to open Haya repositories.'
        return 1
    fi

    for repo in "${HAYA_REPOS[@]}"; do
        if [[ ! -d "$repo" ]]; then
            print -u2 "Repository not found: $repo"
            return 1
        fi
    done

    for repo in "${HAYA_REPOS[@]}"; do
        kitty @ launch \
            --type=tab \
            --cwd="$repo" \
            --tab-title="🧡 ${repo:t}" \
            --copy-env \
            --dont-take-focus \
            --add-to-session \
            ! nvim
    done
}

# Show the current branch and working-tree status for the primary Haya repositories.
function ss() {
    local repo branch git_status

    for repo in "${HAYA_REPOS[@]}"; do
        print -P "\n%F{208}${repo:t}%f"
        print -- '------------------------------------------------------------'

        if [[ ! -d "$repo" ]]; then
            print -P '  %F{red}Repository not found%f'
            continue
        fi

        branch=$(git -C "$repo" branch --show-current) || {
            print -P '  %F{red}Unable to determine branch%f'
            continue
        }
        printf '  Branch: \033[3m%s\033[23m\n' "$branch"
        print

        git_status=$(git -C "$repo" status --short) || {
            print -P '  %F{red}Unable to get status%f'
            continue
        }
        if [[ -n "$git_status" ]]; then
            print -P "%F{yellow}🟡  ${git_status}%f" | sed 's/^/  /'
        else
            print -P '  %F{green}🧼 Clean working directory%f'
        fi
    done
}

# List the aliases and functions defined in this configuration.
function list() {
    printf '%s\n' \
        'Functions:' \
        '  y           Open yazi and change to the directory selected when it exits.' \
        '  gch         Select a local or remote Git branch with fzf and check it out.' \
        '  gfc         Fetch from Git, then check out the branch supplied as its argument.' \
        '  jj          Open Haya repositories in Kitty tabs running Neovim.' \
        '  ss          Show Git status for the primary Haya repositories.' \
        '  gchp        Select a Git branch or tag with an fzf commit-log preview and check it out.' \
        '  list        Print this list of aliases and functions.' \
        '  ctrl-r      Search zsh history' \
        '' \
        'Aliases:' \
        '  gf          git fetch' \
        '  gp          git pull' \
        '  gpf         git push --force-with-lease' \
        '  n           nvim' \
        '  hh          Run the Haya repository manager.' \
        '  bco         Run the Haya branch checkout helper.'
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

# bun completions (only if bun is installed)
[ -s "$HOME/.bun/_bun" ] && source "$HOME/.bun/_bun"

# bun (only if bun is installed)
if [ -d "$HOME/.bun" ]; then
    export BUN_INSTALL="$HOME/.bun"
    export PATH="$BUN_INSTALL/bin:$PATH"
fi

# fuzzy search zsh history
# use ctrl-r 
if command -v fzf &> /dev/null; then
    source <(fzf --zsh)
fi

# Docker CLI completions (only if docker completions exist)
if [ -d "$HOME/.docker/completions" ]; then
    fpath=($HOME/.docker/completions $fpath)
fi

export NVM_DIR="$HOME/.nvm"
[ -s "/opt/homebrew/opt/nvm/nvm.sh" ] && \. "/opt/homebrew/opt/nvm/nvm.sh"  # This loads nvm
[ -s "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm" ] && \. "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm"  # This loads nvm bash_completion

# Homebrew prefix (hardcoded for performance)
# Intel Mac: /usr/local | Apple Silicon: /opt/homebrew
if [[ -d "/opt/homebrew" ]]; then
    BREW_PREFIX="/opt/homebrew"
elif [[ -d "/usr/local/Homebrew" ]]; then
    BREW_PREFIX="/usr/local"
fi

# zsh-z plugin for quickly navigating to frequently used directories
source ~/.config/zsh-z/zsh-z.plugin.zsh

# Initialize completion system
autoload -Uz compinit
# Reuse a cached completion dump on later shells to speed up startup.
ZCOMPDUMP="${XDG_CACHE_HOME:-$HOME/.cache}/zcompdump-$ZSH_VERSION"
if [[ -f "$ZCOMPDUMP" ]]; then
    compinit -C -d "$ZCOMPDUMP"
else
    compinit -d "$ZCOMPDUMP"
fi

export YAZI_IMAGE_ADAPTER="kitty"

# oh-my-posh WIP 
# if [ "$TERM_PROGRAM" != "Apple_Terminal" ]; then
#   eval "$(oh-my-posh init zsh)"
# eval "$(oh-my-posh init zsh --config ~/.config/omp/config.omp.json)"
# fi

# zsh plugins
if [[ -n "$BREW_PREFIX" ]]; then
    [ -f "$BREW_PREFIX/share/zsh-autosuggestions/zsh-autosuggestions.zsh" ] && \
        source "$BREW_PREFIX/share/zsh-autosuggestions/zsh-autosuggestions.zsh"
    
    [ -f "$BREW_PREFIX/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh" ] && \
        source "$BREW_PREFIX/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh"
fi

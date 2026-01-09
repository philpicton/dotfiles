# Phil's zsh config for personal 
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

# fetch
alias gf="git fetch"

# neovim
alias n="nvim"

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

# Initialize completion system
autoload -Uz compinit
compinit

# zsh plugins
if [[ -n "$BREW_PREFIX" ]]; then
    [ -f "$BREW_PREFIX/share/zsh-autosuggestions/zsh-autosuggestions.zsh" ] && \
        source "$BREW_PREFIX/share/zsh-autosuggestions/zsh-autosuggestions.zsh"
    
    [ -f "$BREW_PREFIX/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh" ] && \
        source "$BREW_PREFIX/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh"
fi

export PATH="/opt/homebrew/opt/php@8.3/bin:$PATH"
export PATH="/opt/homebrew/opt/php@8.3/sbin:$PATH"

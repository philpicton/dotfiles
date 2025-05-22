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
# export PATH="$HOME/go/bin:$PATH"

# zsh plugins
source $(brew --prefix)/share/zsh-autocomplete/zsh-autocomplete.plugin.zsh
source $(brew --prefix)/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
source $(brew --prefix)/share/zsh-autosuggestions/zsh-autosuggestions.zsh

# This line adds about 2 seconds to the terminal's startup time but i don't care.
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
           fzf-tmux -d $(( 2 + $(wc -l <<< "$branches") )) +m) &&
    git checkout $(echo "$branch" | sed "s/.* //" | sed "s#remotes/[^/]*/##")
}

# fetch and checkout 
function gfc() {
    git fetch && git checkout $1 &&
        Say "Checked that out for you successfully Phil"
}

# fetch
alias gf="git fetch"

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
        Say "Done your excellency" &&
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

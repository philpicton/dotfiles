export EDITOR="nvim"
export SUDO_EDITOR="$EDITOR"

HISTFILE=~/.history
HISTSIZE=10000
SAVEHIST=50000

source /usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
source /usr/share/zsh/plugins/zsh-autocomplete/zsh-autocomplete.plugin.zsh

eval "$(starship init zsh)"

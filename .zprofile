# Amazon Q pre block. Keep at the top of this file.
[[ -f "${HOME}/.local/share/amazon-q/shell/zprofile.pre.zsh" ]] && builtin source "${HOME}/.local/share/amazon-q/shell/zprofile.pre.zsh"
# this file is installed as ~/.zprofile for newly created users

# prepend ~/.local/bin and ~/bin to $PATH unless it is already there
if ! [[ "$PATH" =~ "$HOME/bin" ]]
then
    PATH="$HOME/bin:$PATH"
fi
if ! [[ "$PATH" =~ "$HOME/.local/bin:" ]]
then
    PATH="$HOME/.local/bin:$PATH"
fi
export PATH

# Amazon Q post block. Keep at the bottom of this file.
[[ -f "${HOME}/.local/share/amazon-q/shell/zprofile.post.zsh" ]] && builtin source "${HOME}/.local/share/amazon-q/shell/zprofile.post.zsh"

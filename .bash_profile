# Amazon Q pre block. Keep at the top of this file.
[[ -f "${HOME}/.local/share/amazon-q/shell/bash_profile.pre.bash" ]] && builtin source "${HOME}/.local/share/amazon-q/shell/bash_profile.pre.bash"
# .bash_profile

# Get the aliases and functions
if [ -f ~/.bashrc ]; then
	. ~/.bashrc
fi

# User specific environment and startup programs

# Amazon Q post block. Keep at the bottom of this file.
[[ -f "${HOME}/.local/share/amazon-q/shell/bash_profile.post.bash" ]] && builtin source "${HOME}/.local/share/amazon-q/shell/bash_profile.post.bash"

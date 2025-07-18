# Amazon Q pre block. Keep at the top of this file.
[[ -f "${HOME}/.local/share/amazon-q/shell/bashrc.pre.bash" ]] && builtin source "${HOME}/.local/share/amazon-q/shell/bashrc.pre.bash"
# .bashrc

# Source global definitions
if [ -f /etc/bashrc ]; then
	. /etc/bashrc
fi

# User specific environment
if ! [[ "$PATH" =~ "$HOME/.local/bin:$HOME/bin:" ]]
then
    PATH="$HOME/.local/bin:$HOME/bin:$PATH"
fi
export PATH

# Uncomment the following line if you don't like systemctl's auto-paging feature:
# export SYSTEMD_PAGER=

# User specific aliases and functions
if [ -d ~/.bashrc.d ]; then
	for rc in ~/.bashrc.d/*; do
		if [ -f "$rc" ]; then
			. "$rc"
		fi
	done
fi

unset rc
complete -C '/usr/local/bin/aws_completer' aws
export PS1='\W $ '
alias dynamodb-local='java -jar /opt/dynamodb-local/DynamoDBLocal.jar'

# Amazon Q post block. Keep at the bottom of this file.
[[ -f "${HOME}/.local/share/amazon-q/shell/bashrc.post.bash" ]] && builtin source "${HOME}/.local/share/amazon-q/shell/bashrc.post.bash"
alias ghost-update="/home/cloudshell-user/lambda-projects/ghost-automation/scripts/update-prompt-layer.sh"

# === Ghost Automation 別名 ===
alias ghost-update='/home/cloudshell-user/lambda-projects/ghost-automation/scripts/update-prompt-layer.sh'
alias ghost-cd='cd /home/cloudshell-user/lambda-projects/ghost-automation'
alias ghost-logs='ls -la /home/cloudshell-user/lambda-projects/ghost-automation/logs/'
export PATH=$PATH:/usr/local/go/bin

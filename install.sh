#!/bin/bash
INSTALL_DIR=$HOME/bin
BASH_ALIAS_FILE=$HOME/.bashrc

Usage(){
	echo "Usage: $(basename $0) [options]"
	echo
	echo "Options:"
	echo -e " -h, --help\tdisplays this message and exits"
	echo -e " --install-dir=/path/to/dir [Default: $INSTALL_DIR]
		Uses path provided as home directory for todo.py"
	echo -e " --alias-file=/path/to/file [Default: $BASH_ALIAS_FILE]
		Uses file to store alias for \$INSTALL_DIR/todo.py"
	exit
}

set -- $(getopt -l "help,install-dir::,alias-file::" "h" "$@")

while [[ $# -gt 0 ]] ; do 
	case "$1" in
		"-h" | "--help" ) Usage
			;;
		"--install-dir" ) shift; INSTALL_DIR=$1
			;;
		"--alias-file" ) shift; BASH_ALIAS_FILE=${1:1:${#1}-2} #[1]
			;;
		"--" ) break
			;;
		* ) shift
	esac
done

prog="[""$(basename $0)""] "

[[ -d $INSTALL_DIR ]] || mkdir -p $INSTALL_DIR
echo $prog"$INSTALL_DIR check passed."

[[ -s $BASH_ALIAS_FILE ]] || echo "# Bash RC File" #>> $BASH_ALIAS_FILE
echo $prog"$BASH_ALIAS_FILE check passed."
## Believe it or not, >> is faster than >.

echo $prog"Copying todo.py to $INSTALL_DIR/todo.py"
cp ./todo.py $INSTALL_DIR

## Establish alias
pre="\n\n#Alias for todo.py\n"
if grep -q "todo.sh" "$BASH_ALIAS_FILE" ; then
	alias=$pre"alias tpy='$INSTALL_DIR/todo.py'\n"
else
	alias=$pre"alias t='$INSTALL_DIR/todo.py'\n"
fi

echo -e $alias >> $BASH_ALIAS_FILE

### Footnote(s)
#[1] the argument is actually passed as "'/path/to/file'" so that instead of
#	- checking /path/to/file or using that, it uses '/path/to/file' (with the
#	- apostrophes). So to remove then you need to start at index 1 take a
#	- substring up until length - 2

#!/bin/bash
if which apt-get &>/dev/null
then
	echo "Bootstrapping for Linux / apt-get"
	echo "sudo required"
	sudo $(dirname "$0")/linux_bootstrap.sh
elif which pacman &>/dev/null
then
	echo "Bootstrapping for Arch Linux / pacman"
	echo "sudo required"
	sudo $(dirname "$0")/arch_bootstrap.sh
elif which brew &>/dev/null
then
	echo "Bootstrapping for Mac OS X / Homebrew"
	$(dirname "$0")/osx_bootstrap.sh
else
	echo "ERROR: can't provide automatic bootstrapping"
	exit 5
fi

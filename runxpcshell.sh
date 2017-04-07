#!/bin/bash
APP=/Applications/Firefox.app
FIREFOX=$APP/Contents/MacOS/firefox
GREDIR=$APP/Contents/Resources
BROWSERDIR=$APP/Contents/Resources/browser
$FIREFOX -xpcshell -g "$GREDIR" -a "$BROWSERDIR" "$@"

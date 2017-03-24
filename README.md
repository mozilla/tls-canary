# TLS Canary version 3
Automated testing of Firefox for TLS/SSL web compatibility

Results live here:
http://tlscanary.mozilla.org

## This project
* Downloads a branch build and a release build of Firefox.
* Automatically runs thousands of secure sites on those builds.
* Diffs the results and presents potentially broken sites in an HTML page for further diagnosis.

## Requirements
* Python 2.7
* virtualenv (highly recommended)
* 7zip
* git
* Go compiler

The script ```linux_bootstrap.sh``` provides bootstrapping for an Ubuntu-based EC2 instance.

## Usage
* cd tls-canary
* virtualenv .
* source bin/activate
* pip install -e .
* tls_canary --help
* tls_canary --reportdir=/tmp/test --debug debug

## Testing
* nosetests -s


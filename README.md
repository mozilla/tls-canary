# TLS Canary version 3
Automated testing of Firefox for TLS/SSL web compatibility

Results live here:
http://tlscanary.mozilla.org

## This project
* Downloads a branch build and a release build of Firefox.
* Automatically runs thousands of secure sites on those builds.
* Diffs the results and presents potentially broken sites in an HTML page for further diagnosis.

## Usage
* virtualenv .
* source bin/activate
* pip install -e .
* tls_canary --help

## Testing
* nosetests -s


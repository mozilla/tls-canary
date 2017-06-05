# TLS Canary version 3
Automated testing of Firefox for TLS/SSL web compatibility

Results live here:
http://tlscanary.mozilla.org

## This project
* Downloads a branch build and a release build of Firefox.
* Automatically runs thousands of secure sites on those builds.
* Diffs the results and presents potential regressions in an HTML page for further diagnosis.

## Requirements
* Python 2.7
* virtualenv (highly recommended)
* 7zip
* git
* Go compiler
* OpenSSL-dev
* libffi-dev

The script ```linux_bootstrap.sh``` provides bootstrapping for an Ubuntu-based EC2 instance.

## Usage
* cd tls-canary
* virtualenv .
* source bin/activate
* pip install -e .
* tls_canary --help
* tls_canary --reportdir=/tmp/test --debug debug

### Command line arguments
Long argument | Short | Choices / **default** | Description
----------|----------|----------|----------
--help | -h | | Longer usage information
--version | | | Prints version string
--workdir | -w | **~/.tlscanary** | Directory where cached files and other state is stored
--reportdir | -r | **$PWD** | Directory for report output. Default is the current directory. Each report is written to a subdirectory there by date and time. Writing to TLS Canary's Python module directory is prohibited.
--parallel | -j | 4 | Number of parallel firefox worker instances the host set will be distributed among
--requestsperworker | -n | 50 | Chunk size of hosts that a worker will query in parallel.
--timeout | -m | 10 | Request timeout in seconds. Running more requests in parallel increases network latency and results in more timeouts.
--test | -t | release, **nightly**, beta, aurora, esr | Test candidate. Any error that it produces that do not occur in baseline are reported.
--base | -b | **release**, nightly, beta, aurora, esr | Baseline to test against. No error that appears in baseline can make it to the report.
--onecrl | -o | **production**, stage, custom | OneCRL revocation list to install to the test profiles. `custom` uses a pre-configured, static list.
--ipython | -i | | Drops into an IPython shell
--limit | -l | | The number of hosts in the test set is limited to the given number. The default is to scan all the hosts in the set.
--filter | -f | 0, **1** | The default filter level 1 removes network timeouts from the report which may appear spuriously. Filter level 0 applies no filtering.
TESTSET | | **top**, list, ... | Set of hosts to test against. Pass `list` to get info on available test sets.


## Testing
* nosetests -sv

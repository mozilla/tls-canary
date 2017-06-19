# TLS Canary

[![PyPI Package version](https://badge.fury.io/py/tlscanary.svg)](https://pypi.python.org/pypi/tlscanary)

TLS Canary is a [TLS/SSL](https://en.wikipedia.org/wiki/Transport_Layer_Security) testing framework for the
[Mozilla Firefox](https://www.mozilla.org/firefox) web browser. It is used by developers to run regression and
performance tests against a large number of HTTPS-enabled hosts on the Internet.

Results of the regression scans are published in HTML format here:
* http://tlscanary.mozilla.org

## This project
* Downloads a test build and a base build of Firefox for comparison.
* Automatically queries thousands of secure sites with those builds.
* Diffs the results and presents potential regressions in an report for further diagnosis.
* Does performance regression testing.
* Extracts SSL state information.
* Can maintain an updated list of HTTPS-enabled top sites.
* Requires a highly reliable network link. **WiFi will give unstable results.**

## Requirements
* Python 2.7
* 7zip
* Go compiler
* OpenSSL-dev
* libffi-dev

### Dependencies for Debian and Ubuntu users
Assuming that you run TLS Canary on a regular graphical desktop machine, these are the packages it requires:
```
sudo apt-get install python python-dev gcc golang-go p7zip-full libssl-dev libffi-dev
```

The script [linux_bootstrap.sh](bootstrap/linux_bootstrap.sh) provides bootstrapping for a headless Ubuntu-based EC2
instance which requires installation of a few standard GUI libraries for running Firefox.
The script may or may not work for your other favourite Debian-based distribution.

### Dependencies for Mac users
Assuming that your're using [Homebrew](https://brew.sh/) for package management, this should set you up:
```
brew install python p7zip go openssl libffi
```

### Dependencies for Windows users
Windows support targets **PowerShell 5.1** on **Windows 10**. Windows 7 and 8 are generally able to run TLS Canary,
but expect minor unicode encoding issues in terminal logging output.

First, [install Chocolatey](https://chocolatey.org/install), then run the following command in an admin PowerShell
to install the dependencies:
```
choco install 7zip.commandline git golang openssh python2
```

## For end users
TLS Canary can be installed as a stable package from PyPI and as experimental package directly from GitHub.
The following command will install the latest stable release of TLS Canary to your current Python environment:
```
pip install [--user] --upgrade tlscanary
```

Whether or not you require the `--user` flag depends on how your Python environment is set up. Most Linux distributions
require it when not installing Python packages as root.

If you prefer the bleeding-edge developer version with the latest features and added instability, you can run
```
pip install [--user] --upgrade git+git://github.com/mozilla/tls-canary.git
```

Once it finishes the `tlscanary` binary is available in your Python environment:
```
tlscanary --help
```

## Usage examples
```bash
# Run a quick regression test against the first 50000 hosts in the default `top` database
tlscanary -r /tmp/reports -l 50000 regression

# Compile a fresh 'top 1000' host database called `mini`
tlscanary -s mini -l 1000 -x1 srcupdate

# Show a list of available host databases
tlscanary -s list

# Use your fresh `mini` database for a quick regession test and see lots of things happening
tlscanary -s mini -r /tmp/report regression --debug
```

Please refer to the complete argument and mode references below.

## For developers
For development you will additionally need to install:

* git
* virtualenv (highly recommended)

*git* can be installed with your favourite package manager. *virtualenv* comes with a simple
`pip install [--user] virtualenv`.

### Developing on Linux or Mac
These are the commands that set you up for TLS Canary development work:
```
git clone https://github.com/mozilla/tls-canary
cd tls-canary
virtualenv -p python2.7 venv
source venv/bin/activate
pip install -e .[dev]
```

The latter command should be used regularly to install new Python dependencies that a TLS Canary update might require.

### Developing on Windows
Developing TLS Canary on Windows is not something we practice regularly. If you encounter quirks along the way,
please do not hesitate to open an issue here on GitHub. The following commands, executed in a PowerShell session
with user privileges, should set you up for TLS Canary development:
```
git clone https://github.com/mozilla/tls-canary
cd tls-canary
virtualenv -p c:\python27\python.exe venv
venv\Scripts\activate
pip install -e .[dev]
```

### Running tests
There are two ways to run the test suite:
```
python setup.py test
nosetests -sv
```

They are largely equivalent, but the former takes care of missing test dependencies, while running `nosetests`
directly offers more control.

### Installing the pre-commit hook for git
There's a pre-commit hook for git that you can use for automated [PEP 8](https://www.python.org/dev/peps/pep-0008/)
violations checking. You can install it by running
```
ln -sf ../../hooks/pre-commit .git/hooks/
```
in the top-level project directory. By using a symbolic link, you will automatically get updates once the hook
in the repo changes. This is highly recommended. You can also copy the script manually, but then you have to
take care of updates yourself.

### Command line arguments
Argument | Choices / **default** | Description
----------|----------|----------
-b --base | **release**, nightly, beta, aurora, esr | Baseline test candidate to test against. Only used by comparative test modes.
-d --debug | | Enable verbose debug logging to the terminal
-f --filter | 0, **1** | The default filter level 1 removes network timeouts from reports which may appear spuriously. Filter level 0 applies no filtering.
-h --help | | Longer usage information
-j --parallel | 4 | Number of parallel firefox worker instances the host set will be distributed among
-l --limit | | The number of hosts in the test set is limited to the given number. The default is to scan all the hosts in the set.
-m --timeout | 10 | Request timeout in seconds. Running more requests in parallel increases network latency and results in more timeouts.
-n --requestsperworker | 50 | Chunk size of hosts that a worker will query in parallel.
-o --onecrl | **production**, stage, custom | OneCRL revocation list to install to the test profiles. `custom` uses a pre-configured, static list.
-r --reportdir | **$PWD** | Directory for report output. Default is the current directory. Each report is written to a subdirectory there by date and time. Writing to TLS Canary's Python module directory is prohibited.
-s --source | **top**, list, ... | Set of hosts to run the test against. Pass `list` to get info on available test sets.
-t --test | release, **nightly**, beta, aurora, esr | Specify the main test candidate. Used by every run mode.
-w --workdir | **~/.tlscanary** | Directory where cached files and other state is stored
-x --scans | 3 | Number of scans to run against each host during performance mode. Currently limited to 20.
MODE | performance, regression, scan, srcupdate | Test mode to run, given as positional parameter. This is a mandatory argument.

### Test modes

Test modes are specified via the mandatory positional `mode` parameter.

Mode | Description
-----|-----
performance | Runs a performance analysis against the hosts in the test set. Use `--scans` to specify how often each host is tested.
regression | Runs a TLS regression test, comparing the 'test' candidate against the 'baseline' candidate. Only reports errors that are new to the test candiate. No error generated by baseline can make it to the report.
scan | This mode only collects connection state information for every host in the test set.
srcupdate | Compile a fresh set of TLS-enabled 'top' sites from the *Umbrella Top 1M* list. Use `-l` to override the default target size of 500k hosts. Use `-x` to adjust the number of passes for errors. Use `-x1` for a factor two speed improvement with slightly less stable results. Use `-b` to change the Firefox version used for filtering. You can use `-s` to create a new database, but you can't make it the default. Databases are written to `~/.tlscanary/sources/`.

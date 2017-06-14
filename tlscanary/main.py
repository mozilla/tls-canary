# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import logging
import coloredlogs
import os
import pkg_resources
import shutil
import sys
import tempfile

import cleanup
import firefox_downloader as fd
import loader
import modes
import sources_db as sdb


# Initialize coloredlogs
logger = logging.getLogger(__name__)
coloredlogs.DEFAULT_LOG_FORMAT = "%(asctime)s %(levelname)s %(threadName)s %(name)s %(message)s"
coloredlogs.install(level='INFO')


def get_argparser():
    """
    Argument parsing
    :return: Parsed arguments object
    """
    pkg_version = pkg_resources.require("tlscanary")[0].version
    home = os.path.expanduser('~')
    # By nature of workdir being undetermined at this point, user-defined test sets in
    # the override directory can not override the default test set. The defaulting logic
    # needs to move behind the argument parser for that to happen.
    src = sdb.SourcesDB()
    testset_default = src.default
    release_choice, _, test_default, base_default = fd.FirefoxDownloader.list()

    parser = argparse.ArgumentParser(prog="tlscanary")
    parser.add_argument('--version', action='version', version='%(prog)s ' + pkg_version)
    parser.add_argument('-b', '--base',
                        help='Firefox base version to compare against (default: `%s`)' % base_default,
                        choices=release_choice,
                        action='store',
                        default=base_default)
    parser.add_argument('-d', '--debug',
                        help='Enable debug',
                        action='store_true',
                        default=False)
    parser.add_argument('-f', '--filter',
                        help='Filter level for results 0:none 1:timeouts (default: 1)',
                        type=int,
                        choices=[0, 1],
                        action='store',
                        default=1)
    parser.add_argument('-i', '--ipython',
                        help='Drop into ipython shell after test run',
                        action='store_true',
                        default=False)
    parser.add_argument('-j', '--parallel',
                        help='Number of parallel worker instances (default: 4)',
                        type=int,
                        action='store',
                        default=4)
    parser.add_argument('-l', '--limit',
                        help='Limit for number of hosts to test (default: no limit)',
                        type=int,
                        action='store',
                        default=None)
    parser.add_argument('-m', '--timeout',
                        help='Timeout for worker requests (default: 10)',
                        type=float,
                        action='store',
                        default=10)
    parser.add_argument('-n', '--requestsperworker',
                        help='Number of requests per worker (default: 50)',
                        type=int,
                        action='store',
                        default=50)
    parser.add_argument('-o', '--onecrl',
                        help='OneCRL set to test (default: production)',
                        type=str.lower,
                        choices=["production", "stage", "custom"],
                        action='store',
                        default='production')
    parser.add_argument('-p', '--prefs',
                        help='Prefs to apply to all builds',
                        type=str,
                        action='append',
                        default=None)
    parser.add_argument('-p1', '--prefs_test',
                        help='Prefs to apply to test build',
                        type=str,
                        action='append',
                        default=None)
    parser.add_argument('-p2', '--prefs_base',
                        help='Prefs to apply to base build',
                        type=str,
                        action='append',
                        default=None)
    parser.add_argument('-r', '--reportdir',
                        help='Path to report output directory (default: cwd)',
                        type=os.path.abspath,
                        action='store',
                        default=os.getcwd())
    parser.add_argument('-s', '--source',
                        help='Test set to run. Use `list` for info. (default: `%s`)' % testset_default,
                        action='store',
                        default=testset_default)
    parser.add_argument('-t', '--test',
                        help='Firefox version to test (default: `%s`)' % test_default,
                        choices=release_choice,
                        action='store',
                        default=test_default)
    parser.add_argument('-w', '--workdir',
                        help='Path to working directory',
                        type=os.path.abspath,
                        action='store',
                        default='%s/.tlscanary' % home)
    parser.add_argument('-x', '--scans',
                        help='Number of scans per host (default: 3)',
                        type=int,
                        action='store',
                        default=3)
    parser.add_argument('mode',
                        help='Test mode to run. (default: `%s`)' % modes.default_mode,
                        choices=modes.all_mode_names,
                        action='store',
                        nargs='?',
                        default=modes.default_mode)
    return parser


tmp_dir = None
module_dir = None


def __create_tempdir():
    """
    Helper function for creating the temporary directory.
    Writes to the global variable tmp_dir
    :return: Path of temporary directory
    """
    temp_dir = tempfile.mkdtemp(prefix='tlscanary_')
    logger.debug('Created temp dir `%s`' % temp_dir)
    return temp_dir


class RemoveTempDir(cleanup.CleanUp):
    """
    Class definition for cleanup helper responsible
    for deleting the temporary directory prior to exit.
    """
    @staticmethod
    def at_exit():
        global tmp_dir
        if tmp_dir is not None:
            logger.debug('Removing temp dir `%s`' % tmp_dir)
            shutil.rmtree(tmp_dir, ignore_errors=True)


restore_terminal_encoding = None


def get_terminal_encoding():
    """
    Helper function to get current terminal encoding
    """
    global logger
    if sys.platform.startswith("win"):
        logger.debug("Running `chcp` shell command")
        chcp_output = os.popen("chcp").read().strip()
        logger.debug("chcp output: `%s`" % chcp_output)
        if chcp_output.startswith("Active code page:"):
            codepage = chcp_output.split(": ")[1]
            logger.debug("Active codepage is `%s`" % codepage)
            return codepage
        else:
            logger.warning("There was an error detecting the active codepage")
            return None
    else:
        logger.debug("Platform does not require switching terminal encoding")
        return None


def set_terminal_encoding(encoding):
    """
    Helper function to set terminal encoding.
    """
    global logger
    if sys.platform.startswith("win"):
        logger.debug("Running `chcp` shell command, setting codepage to `%s`", encoding)
        chcp_output = os.popen("chcp %s" % encoding).read().strip()
        logger.debug("chcp output: `%s`" % chcp_output)
        if chcp_output == "Active code page: %s" % encoding:
            logger.debug("Successfully set codepage to `%s`" % encoding)
        else:
            logger.warning("Can't set codepage for terminal")


def fix_terminal_encoding():
    """
    Helper function to set terminal to platform-specific UTF encoding
    """
    global restore_terminal_encoding
    restore_terminal_encoding = get_terminal_encoding()
    if restore_terminal_encoding is None:
        return
    if sys.platform.startswith("win"):
        platform_utf_encoding = "65001"
    else:
        platform_utf_encoding = None
    if restore_terminal_encoding != platform_utf_encoding:
        set_terminal_encoding(platform_utf_encoding)


class ResetTerminalEncoding(cleanup.CleanUp):
    """
    Class for restoring original terminal encoding at exit.
    """
    @staticmethod
    def at_exit():
        global restore_terminal_encoding
        if restore_terminal_encoding is not None:
            set_terminal_encoding(restore_terminal_encoding)


# This is the entry point used in setup.py
def main():
    global logger, tmp_dir, module_dir

    module_dir = os.path.split(__file__)[0]

    parser = get_argparser()
    args = parser.parse_args()

    if args.debug:
        coloredlogs.install(level='DEBUG')

    logger.debug("Command arguments: %s" % args)

    cleanup.init()
    fix_terminal_encoding()
    tmp_dir = __create_tempdir()

    # If 'list' is specified as test, list available test sets, builds, and platforms
    if args.source == "list":
        coloredlogs.install(level='ERROR')
        db = sdb.SourcesDB(args)
        build_list, platform_list, _, _ = fd.FirefoxDownloader.list()
        print "Available builds: %s" % ' '.join(build_list)
        print "Available platforms: %s" % ' '.join(platform_list)
        print "Available test sets:"
        for handle in db.list():
            test_set = db.read(handle)
            if handle == db.default:
                default = " (default)"
            else:
                default = ""
            print "  - %s [%d hosts]%s" % (handle, len(test_set), default)
        sys.exit(1)

    # Create workdir (usually ~/.tlscanary, used for caching etc.)
    # Assumes that no previous code must write to it.
    if not os.path.exists(args.workdir):
        logger.debug('Creating working directory %s' % args.workdir)
        os.makedirs(args.workdir)

    # Load the specified test mode
    try:
        loader.run(args, module_dir, tmp_dir)

    except KeyboardInterrupt:
        logger.critical("\nUser interrupt. Quitting...")
        return False

    if args.ipython:
        from IPython import embed
        embed()

    return True

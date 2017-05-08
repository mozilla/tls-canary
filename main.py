#!/usr/bin/env python2

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import datetime
from distutils import dir_util
import logging
from math import ceil
import coloredlogs
import os
import shutil
import stat
import sys
import tempfile

import cleanup
import firefox_downloader as fd
import firefox_extractor as fe
import one_crl_downloader as one_crl
import report
import url_store as us
import worker_pool as wp
import xpcshell_worker as xw


# Initialize coloredlogs
logger = logging.getLogger(__name__)
coloredlogs.DEFAULT_LOG_FORMAT = "%(asctime)s %(levelname)s %(threadName)s %(name)s %(message)s"
coloredlogs.install(level='INFO')


def get_argparser():
    """
    Argument parsing
    :return: Parsed arguments object
    """
    home = os.path.expanduser('~')
    testset_choice, testset_default = us.URLStore.list()
    testset_choice.append('list')
    release_choice, _, test_default, base_default = fd.FirefoxDownloader.list()

    parser = argparse.ArgumentParser(prog="tls_canary")
    parser.add_argument('--version', action='version', version='%(prog)s 3.0.0')
    parser.add_argument('-d', '--debug',
                        help='Enable debug',
                        action='store_true',
                        default=False)
    parser.add_argument('-w', '--workdir',
                        help='Path to working directory',
                        type=os.path.abspath,
                        action='store',
                        default='%s/.tlscanary' % home)
    parser.add_argument('-r', '--reportdir',
                        help='Path to report output directory (default: cwd)',
                        type=os.path.abspath,
                        action='store',
                        default=os.getcwd())
    parser.add_argument('-j', '--parallel',
                        help='Number of parallel worker instances (default: 4)',
                        type=int,
                        action='store',
                        default=4)
    parser.add_argument('-n', '--requestsperworker',
                        help='Number of requests per worker (default: 50)',
                        type=int,
                        action='store',
                        default=50)
    parser.add_argument('-m', '--timeout',
                        help='Timeout for worker requests (default: 10)',
                        type=float,
                        action='store',
                        default=10)
    parser.add_argument('-t', '--test',
                        help='Firefox version to test (default: `%s`)' % test_default,
                        choices=release_choice,
                        action='store',
                        default=test_default)
    parser.add_argument('-b', '--base',
                        help='Firefox base version to test against (default: `%s`)' % base_default,
                        choices=release_choice,
                        action='store',
                        default=base_default)
    parser.add_argument('-o', '--onecrl',
                        help='OneCRL set to test (default: prod)',
                        type=str.lower,
                        choices=["prod", "stage", "custom"],
                        action='store',
                        default='prod')
    parser.add_argument('-i', '--ipython',
                        help='Drop into ipython shell after test run',
                        action='store_true',
                        default=False)
    parser.add_argument('-l', '--limit',
                        help='Limit for number of URLs to test (default: unlimited)',
                        type=int,
                        action='store',
                        default=0)
    parser.add_argument('-f', '--filter',
                        help='Filter level for results 0:none 1:timeouts (default: 1)',
                        type=int,
                        choices=[0, 1],
                        action='store',
                        default=1)
    parser.add_argument('-s', '--source',
                        metavar='TESTSET',
                        help='Test set to run. Use `list` for info. (default: `%s`)' % testset_default,
                        choices=testset_choice,
                        action='store',
                        default=testset_default)
    # TODO: create separate python file or class to handle new test type metadata
    parser.add_argument('mode',
                        help='Test mode to run. (default: `%s`)' % 'regression',
                        choices=['regression', 'info'],
                        action='store',
                        nargs='?',
                        default='regression')
    return parser

"""
    parser.add_argument('testset',
                        metavar='TESTSET',
                        help='Test set to run. Use `list` for info. (default: `%s`)' % testset_default,
                        choices=testset_choice,
                        action='store',
                        nargs='?',
                        default=testset_default)
"""



tmp_dir = None
module_dir = None


def __create_tempdir():
    """
    Helper function for creating the temporary directory.
    Writes to the global variable tmp_dir
    :return: Path of temporary directory
    """
    tmp_dir = tempfile.mkdtemp(prefix='tlscanary_')
    logger.debug('Creating temp dir `%s`' % tmp_dir)
    return tmp_dir


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


def get_test_candidate(args, build):
    """
    Download and extract a build candidate
    :param args: command line arguments object
    :return: two FirefoxApp objects for test and base candidate
    """
    global logger, tmp_dir

    if sys.platform == 'darwin':
        platform = 'osx'
    elif 'linux' in sys.platform:
        if sys.maxsize == 2147483647:
            platform = 'linux32'
        else:
            platform = 'linux'
    elif sys.platform == 'win32':
        if sys.maxsize == 2147483647:
            platform = 'win32'
        else:
            platform = 'win'
    else:
        logger.error('Unsupported platform: %s' % sys.platform)
        sys.exit(5)  

    logger.debug('Detected platform: %s' % platform)

    # Download and extract Firefox archives
    fdl = fd.FirefoxDownloader(args.workdir, cache_timeout=1*60*60)

    # Download candidate
    build_archive_file = fdl.download(build, platform)
    if build_archive_file is None:
        sys.exit(-1)
    # Extract candidate archive
    candidate_app = fe.extract(build_archive_file, args.workdir, cache_timeout=1*60*60)
    logger.debug("Build candidate executable is `%s`" % candidate_app.exe)

    return candidate_app


def collect_worker_info(app):
    worker = xw.XPCShellWorker(app)
    worker.spawn()
    worker.send(xw.Command("info"))
    result = worker.wait().result
    worker.terminate()
    return result


def run_test(app, url_list, args, profile=None, num_workers=None, n_per_worker=None, timeout=None,
             get_info=False, get_certs=False, progress=False, return_only_errors=True):
    global logger, tmp_dir, module_dir

    # Default to values from args
    if num_workers is None:
        num_workers = args.parallel
    if n_per_worker is None:
        n_per_worker = args.requestsperworker
    if timeout is None:
        timeout = args.timeout

    try:
        results = wp.run_scans(app, list(url_list), profile=profile, num_workers=num_workers,
                               targets_per_worker=n_per_worker, timeout=timeout,
                               progress=progress, get_certs=get_certs)

    except KeyboardInterrupt:
        logger.critical('User abort')
        wp.stop()
        sys.exit(1)

    run_results = set()

    for host in results:
        if return_only_errors:
            if not results[host].success:
                if get_info:
                    run_results.add((results[host].rank, host, results[host]))
                else:
                    run_results.add((results[host].rank, host))
        else:
            if get_info:
                run_results.add((results[host].rank, host, results[host]))
            else:
                run_results.add((results[host].rank, host))

    return run_results


def run_regression_passes(args, test_app, base_app):
    global logger, tmp_dir, module_dir
    sources_dir = os.path.join(module_dir, 'sources')

    # Compile the set of URLs to test
    urldb = us.URLStore(sources_dir, limit=args.limit)
    urldb.load(args.source)
    url_set = set(urldb)
    logger.info("%d URLs in test set" % len(url_set))

    # Setup custom profiles
    #test_profile, base_profile, _ = make_profiles(args)
    test_profile = make_profile(args, "test_profile")
    base_profile = make_profile(args, "release_profile")

    # Compile set of error URLs in three passes
    # First pass:
    # - Run full test set against the test candidate
    # - Run new error set against baseline candidate
    # - Filter for errors from test candidate but not baseline
    logger.info("Starting first pass with %d URLs" % len(url_set))

    test_error_set = run_test(test_app, url_set, args, profile=test_profile, progress=True)
    logger.info("First test candidate pass yielded %d error URLs" % len(test_error_set))
    logger.debug("First test candidate pass errors: %s" % ' '.join(["%d,%s" % (r, u) for r, u in test_error_set]))

    base_error_set = run_test(base_app, test_error_set, args, profile=base_profile, progress=True)
    logger.info("First baseline candidate pass yielded %d error URLs" % len(base_error_set))
    logger.debug("First baseline candidate pass errors: %s" % ' '.join(["%d,%s" % (r, u) for r, u in base_error_set]))

    error_set = test_error_set.difference(base_error_set)

    # Second pass:
    # - Run error set from first pass against the test candidate
    # - Run new error set against baseline candidate, slower with higher timeout
    # - Filter for errors from test candidate but not baseline
    logger.info("Starting second pass with %d URLs" % len(error_set))

    test_error_set = run_test(test_app, error_set, args, profile=test_profile,
                              num_workers=int(ceil(args.parallel/1.414)),
                              n_per_worker=int(ceil(args.requestsperworker/1.414)))
    logger.info("Second test candidate pass yielded %d error URLs" % len(test_error_set))
    logger.debug("Second test candidate pass errors: %s" % ' '.join(["%d,%s" % (r, u) for r, u in test_error_set]))

    base_error_set = run_test(base_app, test_error_set, args, profile=base_profile)
    logger.info("Second baseline candidate pass yielded %d error URLs" % len(base_error_set))
    logger.debug("Second baseline candidate pass errors: %s" % ' '.join(["%d,%s" % (r, u) for r, u in base_error_set]))

    error_set = test_error_set.difference(base_error_set)

    # Third pass:
    # - Run error set from first pass against the test candidate with less workers
    # - Run new error set against baseline candidate with less workers
    # - Filter for errors from test candidate but not baseline
    logger.info("Starting third pass with %d URLs" % len(error_set))

    test_error_set = run_test(test_app, error_set, args, profile=test_profile, num_workers=2, n_per_worker=10)
    logger.info("Third test candidate pass yielded %d error URLs" % len(test_error_set))
    logger.debug("Third test candidate pass errors: %s" % ' '.join(["%d,%s" % (r, u) for r, u in test_error_set]))

    base_error_set = run_test(base_app, test_error_set, args, profile=base_profile, num_workers=2, n_per_worker=10)
    logger.info("Third baseline candidate pass yielded %d error URLs" % len(base_error_set))
    logger.debug("Third baseline candidate pass errors: %s" % ' '.join(["%d,%s" % (r, u) for r, u in base_error_set]))

    error_set = test_error_set.difference(base_error_set)

    logger.info("Error set is %d URLs: %s" % (len(error_set), ' '.join(["%d,%s" % (r, u) for r, u in error_set])))

    # Fourth pass, information extraction:
    # - Run error set from third pass against the test candidate with less workers
    # - Have workers return extra runtime information, including certificates
    logger.info("Extracting runtime information from %d URLs" % (len(error_set)))
    final_error_set = run_test(test_app, error_set, args, profile=test_profile, num_workers=1,
                               n_per_worker=10, get_info=True, get_certs=True)

    # Final set includes additional result data, so filter that out before comparison
    stripped_final_set = set()
    for rank, host, data in final_error_set:
        stripped_final_set.add((rank, host))

    if stripped_final_set != error_set:
        diff_set = error_set.difference(stripped_final_set)
        logger.warning("Domains dropped out of final error set: %s" % diff_set)

    return final_error_set


def make_profile(args, profile_name):
    global logger, module_dir, tmp_dir

    # create directories for profiles
    default_profile_dir = os.path.join(module_dir, "default_profile")
    new_profile_dir = os.path.join(tmp_dir, profile_name)

    if not os.path.exists(new_profile_dir):
        os.makedirs(new_profile_dir)

    # copy contents of default profile to new profiles
    dir_util.copy_tree(default_profile_dir, new_profile_dir)

    logger.info("Updating OneCRL revocation data")
    if args.onecrl == "prod" or args.onecrl == "stage":
        # overwrite revocations file in test profile with live OneCRL entries from requested environment
        revocations_file = one_crl.get_list(args.onecrl, args.workdir)
        profile_file = os.path.join(new_profile_dir, "revocations.txt")
        logger.debug("Writing OneCRL revocations data to `%s`" % profile_file)
        shutil.copyfile(revocations_file, profile_file)
    else:
        # leave the existing revocations file alone
        logger.info("Testing with custom OneCRL entries from default profile")

    # make all files in profiles read-only to prevent caching
    for root, dirs, files in os.walk(new_profile_dir, topdown=False):
        for name in files:
            os.chmod(os.path.join(root, name), stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

    return new_profile_dir


def save_profile(args, profile_name, start_time):
    global logger, tmp_dir

    timestamp = start_time.strftime("%Y-%m-%d-%H-%M-%S")
    run_dir = os.path.join(args.reportdir, "runs", timestamp)

    logger.debug("Saving profile to `%s`" % run_dir)
    dir_util.copy_tree(os.path.join(tmp_dir, profile_name), os.path.join(run_dir, profile_name))


def run_regression_test(args):
    global logger

    # TODO: argument validation logic to make sure user has specified both test and base build
    test_app = get_test_candidate(args, args.test)
    base_app = get_test_candidate(args, args.base)

    test_metadata = collect_worker_info(test_app)
    base_metadata = collect_worker_info(base_app)

    logger.info("Testing Firefox %s %s against Firefox %s %s" %
                (test_metadata["appVersion"], test_metadata["branch"],
                 base_metadata["appVersion"], base_metadata["branch"]))

    start_time = datetime.datetime.now()
    error_set = run_regression_passes(args, test_app, base_app)

    header = {
        "timestamp": start_time.strftime("%Y-%m-%d-%H-%M-%S"),
        "branch": test_metadata["branch"].capitalize(),
        "description": "Fx%s %s vs Fx%s %s" % (test_metadata["appVersion"], test_metadata["branch"],
                                               base_metadata["appVersion"], base_metadata["branch"]),
        "source": args.source,
        "test build url": fd.FirefoxDownloader.get_download_url(args.test, test_app.platform),
        "release build url": fd.FirefoxDownloader.get_download_url(args.base, base_app.platform),
        "test build metadata": "%s, %s" % (test_metadata["nssVersion"], test_metadata["nsprVersion"]),
        "release build metadata": "%s, %s" % (base_metadata["nssVersion"], base_metadata["nsprVersion"]),
        "Total time": "%d minutes" % int(round((datetime.datetime.now() - start_time).total_seconds() / 60))
    }

    report.generate(args, header, error_set, start_time)

    save_profile(args, "test_profile", start_time)
    save_profile(args, "release_profile", start_time)


def run_info_test(args):
    global logger, tmp_dir, module_dir

    # TODO: argument validation logic to make sure user has specified only test build

    # Compile the set of URLs to test
    sources_dir = os.path.join(module_dir, 'sources')
    urldb = us.URLStore(sources_dir, limit=args.limit)
    urldb.load(args.source)
    url_set = set(urldb)
    logger.info("%d URLs in test set" % len(url_set))

    # Create custom profile
    test_profile=make_profile(args, "test_profile")

    logger.info("Starting pass with %d URLs" % len(url_set))
    test_app = get_test_candidate(args, args.test)
    test_metadata = collect_worker_info(test_app)

    logger.info("Testing Firefox %s %s info run" %
                (test_metadata["appVersion"], test_metadata["branch"]))

    start_time = datetime.datetime.now()

    info_uri_set = run_test(test_app, url_set, args, profile=test_profile, get_info=True, get_certs=True, progress=True, return_only_errors=False)

    header = {
        "timestamp": start_time.strftime("%Y-%m-%d-%H-%M-%S"),
        "branch": test_metadata["branch"].capitalize(),
        "description": "Fx%s %s info run" % (test_metadata["appVersion"], test_metadata["branch"]),
        "source": args.source,
        "test build url": fd.FirefoxDownloader.get_download_url(args.test, test_app.platform),
        "test build metadata": "%s, %s" % (test_metadata["nssVersion"], test_metadata["nsprVersion"]),
        "Total time": "%d minutes" % int(round((datetime.datetime.now() - start_time).total_seconds() / 60))
    }

    report.generate(args, header, info_uri_set, start_time, False)
    save_profile(args, "test_profile", start_time)


# This is the entry point used in setup.py
def main():
    global logger, tmp_dir, module_dir

    module_dir = os.path.split(__file__)[0]

    parser = get_argparser()
    args = parser.parse_args()

    if args.debug:
        coloredlogs.install(level='DEBUG')

    logger.debug("Command arguments: %s" % args)

    # If 'list' is specified as test, list available test sets, builds, and platforms
    if args.source == "list":
        testset_list, testset_default = us.URLStore.list()
        build_list, platform_list, _, _ = fd.FirefoxDownloader.list()
        urldb = us.URLStore(os.path.join(module_dir, "sources"))
        print "Available builds: %s" % ' '.join(build_list)
        print "Available platforms: %s" % ' '.join(platform_list)
        print "Available test sets:"
        for testset in testset_list:
            urldb.clear()
            urldb.load(testset)
            if testset == testset_default:
                default = "(default)"
            else:
                default = ""
            print "  - %s [%d] %s" % (testset, len(urldb), default)
        sys.exit(1)

    # Create workdir (usually ~/.tlscanary, used for caching etc.)
    # Assumes that no previous code must write to it.
    if not os.path.exists(args.workdir):
        logger.debug('Creating working directory %s' % args.workdir)
        os.makedirs(args.workdir)

    # All code paths after this will generate a report, so check
    # whether the report dir is a valid target. Specifically, prevent
    # writing to the module directory.
    if args.reportdir == module_dir:
        logger.critical("Refusing to write report to module directory. Please set --reportdir")
        sys.exit(1)

    cleanup.init()
    tmp_dir = __create_tempdir()

    try:
        # determine which test to run
        if args.mode == 'regression':
            run_regression_test(args)
        elif args.mode == 'info':
            run_info_test(args)
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        logger.critical("\nUser interrupt. Quitting...")
        return False

    if args.ipython:
        from IPython import embed
        embed()

    return True

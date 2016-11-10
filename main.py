#!/usr/bin/env python2

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import logging
import coloredlogs
import os
import shutil
import sys
import tempfile
import time

import cleanup
import firefox_downloader as fd
import firefox_extractor as fe
import firefox_runner as fr
import url_store as us


# Initialize coloredlogs
logger = logging.getLogger(__name__)
coloredlogs.DEFAULT_LOG_FORMAT = "%(asctime)s %(levelname)s %(threadName)s %(name)s %(message)s"
coloredlogs.install(level='INFO')


def get_argparser():
    home = os.path.expanduser('~')
    testset_choice, testset_default = us.URLStore.list()
    testset_choice.append('list')
    release_choice, _, test_default, base_default = fd.FirefoxDownloader.list()

    parser = argparse.ArgumentParser(prog="tls_canary")
    parser.add_argument('--version', action = 'version', version = '%(prog)s 0.1')
    parser.add_argument('-d', '--debug',
                        help='Enable debug',
                        action='store_true',
                        default=False)
    parser.add_argument('-w', '--workdir',
                        help='Path to working directory',
                        type=os.path.abspath,
                        action='store',
                        default='%s/.tlscanary' % home)
    parser.add_argument('-j', '--parallel',
                        help='Number of parallel worker instances (default: 25)',
                        type=int,
                        action='store',
                        default=25)
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
    parser.add_argument('testset',
                        metavar='TESTSET',
                        help='Test set to run. Use `list` for info. (default: `%s`)' % testset_default,
                        choices=testset_choice,
                        action='store',
                        nargs='?',
                        default=testset_default)
    return parser


tmp_dir = None
module_dir = None


def create_tempdir():
    tmp_dir = tempfile.mkdtemp(prefix='tlscanary_')
    logger.debug('Creating temp dir `%s`' % tmp_dir)
    return tmp_dir


class RemoveTempDir(cleanup.CleanUp):
    @staticmethod
    def at_exit():
        global tmp_dir
        if tmp_dir is not None:
            logger.debug('Removing temp dir `%s`' % tmp_dir)
            shutil.rmtree(tmp_dir, ignore_errors=True)


def run_test(exe_file, url_list, work_dir, module_dir, num_workers, info=False, cert_dir=None):
    runner = fr.FirefoxRunner(exe_file, url_list, work_dir, module_dir, num_workers, info, cert_dir)
    run_errors = set()
    try:
        while True:
            # Spawn new workers if necessary
            runner.maintain_worker_queue()
            # Check result queue
            while True:
                result = runner.get_result()
                if result is None:
                    break
                logger.info("Test result: %s" % result)
                if "error" in result and result["error"]:
                    run_errors.add((int(result["rank"]), result["url"]))
            # Break if all urls have been worked
            if runner.is_done():
                break

            time.sleep(0.05)

    except KeyboardInterrupt:
        logger.critical('User abort')
        runner.terminate_workers()
        sys.exit(1)

    return run_errors


def get_test_candidates(args):
    global logger, tmp_dir

    if sys.platform == 'darwin':
        platform = 'osx'
    else:
        logger.error('Unsupported platform: %s' % sys.platform)
        sys.exit(5)
    logger.info('Detected platform: %s' % platform)

    # Download and extract Firefox archives
    fdl = fd.FirefoxDownloader(args.workdir, cache_timeout=1*60*60)

    # Download test candidate
    test_archive_file = fdl.download(args.test, platform)
    if test_archive_file is None:
        sys.exit(-1)
    # Extract test candidate archive
    test_extract_dir, test_exe_file = fe.extract(platform, test_archive_file, tmp_dir)
    if test_exe_file is None:
        sys.exit(-1)
    logger.debug("Test candidate executable is `%s`" % test_exe_file)

    # Download baseline candidate
    base_archive_file = fdl.download(args.base, platform)
    if base_archive_file is None:
        sys.exit(-1)
    # Extract baseline candidate archive
    base_extract_dir, base_exe_file = fe.extract(platform, base_archive_file, tmp_dir)
    if base_exe_file is None:
        sys.exit(-1)
    logger.debug("Baseline candidate executable is `%s`" % base_exe_file)

    return test_extract_dir, test_exe_file, base_extract_dir, base_exe_file


def run_tests(args, test_exe_file, base_exe_file):
    global logger, tmp_dir, module_dir
    sources_dir = os.path.join(module_dir, 'sources')

    # Compile the set of URLs to test
    urldb = us.URLStore(sources_dir)
    urldb.load(args.testset)
    url_set = set(urldb)
    logger.info("%d URLs in test set" % len(url_set))

    # Compile set of error URLs in three passes
    # First pass:
    # - Run full test set against the test candidate
    # - Run new error set against baseline candidate
    # - Filter for errors from test candidate but not baseline
    logger.info("Starting first pass with %d URLs" % len(url_set))

    test_error_set = run_test(test_exe_file, url_set, args.workdir, module_dir, args.parallel)
    logger.info("First test candidate pass yielded %d error URLs" % len(test_error_set))
    logger.debug("First test candidate pass errors: %s" % ' '.join(["%d,%s" % (r, u) for r, u in test_error_set]))

    base_error_set = run_test(base_exe_file, test_error_set, args.workdir, module_dir, args.parallel)
    logger.info("First baseline candidate pass yielded %d error URLs" % len(base_error_set))
    logger.debug("First baseline candidate pass errors: %s" % ' '.join(["%d,%s" % (r, u) for r, u in base_error_set]))

    error_set = test_error_set.difference(base_error_set)

    # Second pass:
    # - Run error set from first pass against the test candidate
    # - Run new error set against baseline candidate
    # - Filter for errors from test candidate but not baseline
    logger.info("Starting second pass with %d URLs" % len(error_set))

    test_error_set = run_test(test_exe_file, error_set, args.workdir, module_dir, args.parallel)
    logger.info("Second test candidate pass yielded %d error URLs" % len(test_error_set))
    logger.debug("Second test candidate pass errors: %s" % ' '.join(["%d,%s" % (r, u) for r, u in test_error_set]))

    base_error_set = run_test(base_exe_file, test_error_set, args.workdir, module_dir, args.parallel)
    logger.info("Second baseline candidate pass yielded %d error URLs" % len(base_error_set))
    logger.debug("Second baseline candidate pass errors: %s" % ' '.join(["%d,%s" % (r, u) for r, u in base_error_set]))

    error_set = test_error_set.difference(base_error_set)

    # Third pass:
    # - Run error set from first pass against the test candidate with less workers
    # - Run new error set against baseline candidate with less workers
    # - Filter for errors from test candidate but not baseline
    logger.info("Starting third pass with %d URLs" % len(error_set))

    test_error_set = run_test(test_exe_file, error_set, args.workdir, module_dir, min(args.parallel, 10))
    logger.info("Third test candidate pass yielded %d error URLs" % len(test_error_set))
    logger.debug("Third test candidate pass errors: %s" % ' '.join(["%d,%s" % (r, u) for r, u in test_error_set]))

    base_error_set = run_test(base_exe_file, test_error_set, args.workdir, module_dir, min(args.parallel, 10))
    logger.info("Third baseline candidate pass yielded %d error URLs" % len(base_error_set))
    logger.debug("Third baseline candidate pass errors: %s" % ' '.join(["%d,%s" % (r, u) for r, u in base_error_set]))

    error_set = test_error_set.difference(base_error_set)

    logger.info("Final error set is %d URLs: %s" % (len(error_set), ' '.join(["%d,%s" % (r, u) for r, u in error_set])))

    # Extract JSON info for error set
    logger.info("Extracting certificates for %d error URLs" % len(error_set))
    final_error_set = run_test(test_exe_file, error_set, args.workdir, module_dir, min(args.parallel, 10), True)

    return final_error_set


def extract_certificates(args, error_set, test_exe_file):
    global logger, tmp_dir, module_dir
    tmp_cert_dir = os.path.join(tmp_dir, "certs")
    os.mkdir(tmp_cert_dir)

    logger.info("Extracting certificates from %d URLs to `%s`" % (len(error_set), tmp_cert_dir))
    final_error_set = run_test(test_exe_file, error_set, args.workdir, module_dir,
                               min(args.parallel, 10), False, tmp_cert_dir)

    if final_error_set != error_set:
        diff_set = error_set.difference(final_error_set)
        logger.warning("Domains dropped out of error set: %s" % diff_set)

    return tmp_cert_dir


def create_report(args, error_set, cert_dir):
    # timestamp : 2016-11-09-16-26-08
    # branch : Nightly
    # description : Fx52.0a1 nightly vs Fx49.0.2 release
    # source : Custom list
    # test build url : https://download.mozilla.org/?product=firefox-nightly-latest&os=osx&lang=en-US
    # release build url : https://download.mozilla.org/?product=firefox-latest&os=osx&lang=en-US
    # test build metadata : NSS 3.28 Beta, NSPR 4.13.1
    # release build metadata : NSS 3.25, NSPR 4.12
    # Total time : 3 minutes
    # ++++++++++
    logger.error("Reporting not implemented. Args: %s, %s, %s" % (error_set, cert_dir, args))


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
    if args.testset == "list":
        testset_list, testset_default = us.URLStore.list()
        testset_list[testset_list.index(testset_default)] = testset_default + "(default)"
        build_list, platform_list, _, _ = fd.FirefoxDownloader.list()
        print "Available test sets: %s" % ' '.join(testset_list)
        print "Available builds: %s" % ' '.join(build_list)
        print "Available platforms: %s" % ' '.join(platform_list)
        sys.exit(1)

    cleanup.init()
    tmp_dir = create_tempdir()

    try:
        test_extract_dir, test_exe_file, base_extract_dir, \
            base_exe_file = get_test_candidates(args)
        error_set = run_tests(args, test_exe_file, base_exe_file)
        cert_dir = extract_certificates(args, error_set, test_exe_file)
        create_report(args, error_set, cert_dir)

    except KeyboardInterrupt:
        logger.critical("\nUser interrupt. Quitting...")
        return False

    return True

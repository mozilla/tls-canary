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
    global tmp_dir
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


def run_test(exe_file, url_list, work_dir, module_dir, num_workers, get_certs=False):
    runner = fr.FirefoxRunner(exe_file, url_list, work_dir, module_dir, num_workers, get_certs)
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


def run_tests(args):
    global logger, tmp_dir, module_dir
    create_tempdir()
    module_dir = os.path.split(__file__)[0]
    sources_dir = os.path.join(module_dir, 'sources')

    logger.debug("Command arguments: %s" % args)

    if sys.platform == 'darwin':
        platform = 'osx'
    else:
        logger.error('Unsupported platform: %s' % sys.platform)
        sys.exit(5)
    logger.info('Detected platform: %s' % platform)


    # Download Firefox archives
    fdl = fd.FirefoxDownloader(args.workdir, cache_timeout=1*60*60)
    base_archive_file = fdl.download(args.base, platform)
    if base_archive_file is None:
        sys.exit(-1)
    test_archive_file = fdl.download(args.test, platform)
    if test_archive_file is None:
        sys.exit(-1)

    # Extract firefox archives
    base_extract_dir, base_exe_file = fe.extract(platform, base_archive_file, tmp_dir)
    if base_exe_file is None:
        sys.exit(-1)
    logger.debug("Testing candidate executable is `%s`" % base_exe_file)
    test_extract_dir, test_exe_file = fe.extract(platform, test_archive_file, tmp_dir)
    if test_exe_file is None:
        sys.exit(-1)
    logger.debug("Baseline candidate executable is `%s`" % test_exe_file)

    # Compile the set of URLs to test
    urldb = us.URLStore(sources_dir)
    urldb.load(args.testset)
    url_set = set(urldb)
    logger.info("%d URLs in test set" % len(url_set))

    logger.debug("Testing `%s` against baseline `%s`" % (base_exe_file, test_exe_file))

    # Run two passes against the test candidate
    logger.info("Starting first test candidate pass against %d URLs" % len(url_set))
    test_run_errors = run_test(test_exe_file, url_set, args.workdir, module_dir, args.parallel)
    # Second pass slower, to weed out spurious errors
    logger.info("Starting second test candidate pass against %d error URLs" % len(test_run_errors))
    test_run_errors = run_test(test_exe_file, test_run_errors, args.workdir, module_dir, min(args.parallel, 10))
    logger.info("Second test candidate pass yielded %d error URLs" % len(test_run_errors))
    logger.debug("Test candidate errors: %s" % ' '.join(["%d,%s" % (r,u) for r,u in test_run_errors]))

    # Run two passes against the baseline candidate
    logger.info("Starting first baseline candidate pass against %d URLs" % len(url_set))
    base_run_errors = run_test(base_exe_file, url_set, args.workdir, module_dir, args.parallel)
    # Second pass slower, to weed out spurious errors
    logger.info("Starting second baseline candidate pass against %d error URLs" % len(base_run_errors))
    base_run_errors = run_test(base_exe_file, base_run_errors, args.workdir, module_dir, min(args.parallel, 10))
    logger.info("Second baseline candidate pass yielded %d error URLs" % len(base_run_errors))
    logger.debug("Baseline candidate errors: %s" % ' '.join(["%d,%s" % (r,u) for r,u in base_run_errors]))

    # We're interested in those errors from the test candidate run
    # that are not present in the baseline candidate run.
    new_errors = test_run_errors.difference(base_run_errors)
    logger.info("New errors: %s" % ' '.join(["%d,%s" % (r,u) for r,u in new_errors]))


    return True


# This is the entry point used in setup.py
def main():

    cleanup.init()

    parser = get_argparser()
    args = parser.parse_args()

    if args.debug:
        coloredlogs.install(level='DEBUG')

    # If 'list' is specified as test, list available test sets, builds, and platforms
    if args.testset == "list":
        testset_list, testset_default = us.URLStore.list()
        testset_list[testset_list.index(testset_default)] = testset_default + "(default)"
        build_list, platform_list, _, _ = fd.FirefoxDownloader.list()
        print "Available test sets: %s" % ' '.join(testset_list)
        print "Available builds: %s" % ' '.join(build_list)
        print "Available platforms: %s" % ' '.join(platform_list)
        sys.exit(1)

    try:
        result = run_tests(args)
    except KeyboardInterrupt:
        logger.critical("\nUser interrupt. Quitting...")

    return result

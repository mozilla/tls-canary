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


def get_test_candidates(args):
    """
    Download and extract the test candidates
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

    # Download test candidate
    test_archive_file = fdl.download(args.test, platform)
    if test_archive_file is None:
        sys.exit(-1)
    # Extract test candidate archive
    test_app = fe.extract(test_archive_file, args.workdir, cache_timeout=1*60*60)
    logger.debug("Test candidate executable is `%s`" % test_app.exe)

    # Download baseline candidate
    base_archive_file = fdl.download(args.base, platform)
    if base_archive_file is None:
        sys.exit(-1)
    # Extract baseline candidate archive
    base_app = fe.extract(base_archive_file, args.workdir, cache_timeout=1*60*60)
    logger.debug("Baseline candidate executable is `%s`" % base_app.exe)

    return test_app, base_app


def collect_worker_info(app):
    worker = xw.XPCShellWorker(app)
    worker.spawn()
    worker.send(xw.Command("info"))
    result = worker.wait().result
    worker.terminate()
    return result


def build_data_logs(test_app, base_app):
    """
    Gather info on the test candidates.
    :param test_app:
    :param base_app:
    :return: test_metadata, base_metadata
    """
    global logger

    test_metadata = collect_worker_info(test_app)
    base_metadata = collect_worker_info(base_app)

    logger.info("Testing Firefox %s %s against Firefox %s %s" %
                (test_metadata["appVersion"], test_metadata["branch"],
                 base_metadata["appVersion"], base_metadata["branch"]))

    return test_metadata, base_metadata


def run_test(app, url_list, args, profile=None, num_workers=None, n_per_worker=None, timeout=None,
             get_info=False, get_certs=False, progress=False):
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

    run_errors = set()

    for host in results:
        if not results[host].success:
            if get_info:
                run_errors.add((results[host].rank, host, results[host]))
            else:
                run_errors.add((results[host].rank, host))

    return run_errors


def run_tests(args, test_app, base_app):
    global logger, tmp_dir, module_dir
    sources_dir = os.path.join(module_dir, 'sources')

    # Compile the set of URLs to test
    urldb = us.URLStore(sources_dir, limit=args.limit)
    urldb.load(args.testset)
    url_set = set(urldb)
    logger.info("%d URLs in test set" % len(url_set))

    # Setup custom profiles
    test_profile, base_profile, _ = make_profiles(args)

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

    # Sample data for development and debugging purposes
    # logger.critical("FIXME: Working with static test set")
    # error_set = set([(49182, u'psarips.com'), (257666, u'www.obsidiana.com'), (120451, u'yugiohcardmarket.eu'),
    #                  (9901, u'englishforums.com'), (43694, u'www.csajokespasik.hu'), (157298, u'futuramo.com'),
    #                  (1377, u'www.onlinecreditcenter6.com'), (15752, u'www.jcpcreditcard.com'), (137890, u'my.jobs'),
    #                  (31862, u'samsungcsportal.com'), (40034, u'uob.com.my'), (255349, u'censusmapper.ca'),
    #                  (89913, u'hslda.org'), (64349, u'www.chevrontexacocards.com'),
    #                  (69037, u'www.onlinecreditcenter4.com'), (3128, u'www.synchronycredit.com'),
    #                  (84681, u'ruscreditcard.com'), (241254, u'www.steinmartcredit.com'), (123888, u'saveful.com'),
    #                  (230374, u'sirdatainitiative.com'), (135435, u'gearheads.in'), (97220, u'gira.de'),
    #                  (85697, u'magickartenmarkt.de'), (29458, u'cxem.net'), (62059, u'www.awardslinq.com'),
    #                  (32146, u'www.onlinecreditcenter2.com'), (247769, u'gmprograminfo.com'),
    #                  (265649, u'piratenpartei.de'), (23525, u'vesti.lv'), (192596, u'robots-and-dragons.de'),
    #                  (212740, u'www.chs.hu'), (68345, u'bandzone.cz'), (104674, u'incontrion.com'),
    #                  (174612, u'patschool.com'), (80121, u'27399.com'), (114128, u'universoracionalista.org'),
    #                  (100333, u'toccata.ru'), (222646, u'futuramo.net'), (14624, u'reviewmyaccount.com'),
    #                  (147865, u'sherdle.com'), (40192, u'www.belkcredit.com'), (47428, u'www.wangfujing.com'),
    #                  (162199, u'hikvision.ru'), (74032, u'cardoverview.com'), (22279, u'prospero.ru'),
    #                  (143928, u'www.e-financas.gov.pt'), (130883, u'favoritsport.com.ua')])

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


def make_profiles(args):
    global logger, module_dir, tmp_dir

    # create directories for profiles
    default_profile_dir = os.path.join(module_dir, "default_profile")
    test_profile_dir = os.path.join(tmp_dir, "test_profile")
    release_profile_dir = os.path.join(tmp_dir, "release_profile")

    if not os.path.exists(test_profile_dir):
        os.makedirs(test_profile_dir)
    if not os.path.exists(release_profile_dir):
        os.makedirs(release_profile_dir)

    # copy contents of default profile to new profiles
    dir_util.copy_tree(default_profile_dir, test_profile_dir)
    dir_util.copy_tree(default_profile_dir, release_profile_dir)

    logger.info("Updating OneCRL revocation data")
    if args.onecrl == "prod" or args.onecrl == "stage":
        # overwrite revocations file in test profile with live OneCRL entries from requested environment
        revocations_file = one_crl.get_list(args.onecrl, args.workdir)
        profile_file = os.path.join(test_profile_dir, "revocations.txt")
        logger.debug("Writing OneCRL revocations data to `%s`" % profile_file)
        shutil.copyfile(revocations_file, profile_file)
    else:
        # leave the existing revocations file alone
        logger.info("Testing with custom OneCRL entries from default profile")

    # get live OneCRL entries from production for release profile
    revocations_file = one_crl.get_list("prod", args.workdir)
    profile_file = os.path.join(release_profile_dir, "revocations.txt")
    logger.debug("Writing OneCRL revocations data to `%s`" % profile_file)
    shutil.copyfile(revocations_file, profile_file)

    # make all files in profiles read-only to prevent caching
    for root, dirs, files in os.walk(test_profile_dir, topdown=False):
        for name in files:
            os.chmod(os.path.join(root, name), stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

    for root, dirs, files in os.walk(release_profile_dir, topdown=False):
        for name in files:
            os.chmod(os.path.join(root, name), stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

    return test_profile_dir, release_profile_dir, default_profile_dir


def save_profiles(args, start_time):
    global logger, tmp_dir

    timestamp = start_time.strftime("%Y-%m-%d-%H-%M-%S")
    run_dir = os.path.join(args.reportdir, "runs", timestamp)

    logger.debug("Saving profiles to `%s`" % run_dir)
    dir_util.copy_tree(os.path.join(tmp_dir, "test_profile"), os.path.join(run_dir, "test_profile"))
    dir_util.copy_tree(os.path.join(tmp_dir, "release_profile"), os.path.join(run_dir, "release_profile"))


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
        test_app, base_app = get_test_candidates(args)
        test_metadata_log, base_metadata_log = build_data_logs(test_app, base_app)
        start_time = datetime.datetime.now()
        error_set = run_tests(args, test_app, base_app)
        report.generate(args, start_time, test_metadata_log, base_metadata_log, error_set, test_app, base_app)
        save_profiles(args, start_time)

    except KeyboardInterrupt:
        logger.critical("\nUser interrupt. Quitting...")
        return False

    if args.ipython:
        from IPython import embed
        embed()

    return True

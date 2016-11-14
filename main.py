#!/usr/bin/env python2

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import datetime
from distutils import dir_util
import json
import logging
import coloredlogs
import os
import shutil
import subprocess
import sys
import tempfile
import time

import cleanup
import firefox_downloader as fd
import firefox_extractor as fe
import firefox_runner as fr
import progress_bar
import url_store as us


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
    parser.add_argument('--version', action = 'version', version = '%(prog)s 3.0.0a')
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
    parser.add_argument('-i', '--ipython',
                        help='Drop into ipython shell after test run',
                        action='store_true',
                        default=False)
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
    :return: Paths to extracted directories and files
    """
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


def build_data_logs(test_exe_file, base_exe_file, data_dir):
    """
    Gather info on the test candidates.
    :param test_exe_file:
    :param base_exe_file:
    :param data_dir:
    :return:
    """
    global logger
    # TODO: This should be using an abstract firefox_runner

    logger.info("Building build metadata logs")

    cmd = [test_exe_file, "-xpcshell", os.path.join(data_dir, "js", "build_data.js")]
    logger.debug("Executing shell command `%s`" % ' '.join(cmd))
    result = subprocess.check_output(cmd, cwd=data_dir, stderr=subprocess.STDOUT)
    logger.debug("Command returned %s" % result.strip().replace('\n', ' '))
    try:
        test_metadata = json.loads(result)
    except ValueError, error:
        logger.error("Building test build data log failed")
        raise error

    cmd = [base_exe_file, "-xpcshell", os.path.join(data_dir, "js", "build_data.js")]
    logger.debug("Executing shell command `%s`" % ' '.join(cmd))
    result = subprocess.check_output(cmd, cwd=data_dir, stderr=subprocess.STDOUT)
    logger.debug("Command returned %s" % result.strip().replace('\n', ' '))
    try:
        base_metadata = json.loads(result)
    except ValueError, error:
        logger.error("Building base build data log failed")
        raise error

    return test_metadata, base_metadata


def run_test(exe_file, url_list, work_dir, module_dir, num_workers, info=False, cert_dir=None, progress=False):
    global logger

    number_of_urls = len(url_list)
    urls_done = 0
    runner = fr.FirefoxRunner(exe_file, url_list, work_dir, module_dir, num_workers, info, cert_dir)
    run_errors = set()

    if progress:
        progress = progress_bar.ProgressBar(0, number_of_urls, show_percent=True,
                                            show_boundary=True, stats_window=60)
        next_log_update = datetime.datetime.now() + datetime.timedelta(seconds=5)
        next_internal_update = datetime.datetime.now()
    else:
        progress = None
        next_log_update = datetime.datetime.now() + datetime.timedelta(days=1000)
        next_internal_update = datetime.datetime.now() + datetime.timedelta(days=1000)

    try:
        while True:
            # Spawn new workers if necessary
            runner.maintain_worker_queue()

            # Check result queue
            while True:
                result = runner.get_result()
                if result is None:
                    break
                urls_done += 1
                logger.debug("Test result: %s" % result)
                # TODO: It is bad design to not add/return the whole result objects here
                if "error" in result and result["error"]:
                    if "test_obj" in result:
                        # This is the case for runs with "info=True"
                        run_errors.add((int(result["rank"]), result["url"], json.dumps(result["test_obj"])))
                    else:
                        run_errors.add((int(result["rank"]), result["url"]))

            # Update progress
            if progress is not None:
                now = datetime.datetime.now()
                if now >= next_internal_update:
                    progress.set(urls_done)
                    next_internal_update = now + datetime.timedelta(seconds=1)
                if now >= next_log_update:
                    overall_rate, overall_rest_time, overall_eta, \
                        current_rate, current_rest_time, current_eta = progress.stats()

                    if sys.stdout.isatty() and False:
                        # Printing progress to terminal is currently disabled
                        next_log_update = now + datetime.timedelta(seconds=0.5)
                    else:
                        logger.info("%d URLs to go. Current rate %d URLs/minute, rest time %d minutes, ETA %s" % (
                            number_of_urls - urls_done,
                            round(current_rate*60.0),
                            round(current_rest_time.seconds / 60.0),
                            current_eta.isoformat()))
                        next_log_update = now + datetime.timedelta(seconds=60)

            # Break if all urls have been worked
            if runner.is_done():
                break

            time.sleep(0.05)

    except KeyboardInterrupt:
        logger.critical('User abort')
        runner.terminate_workers()
        sys.exit(1)

    return run_errors


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

    test_error_set = run_test(test_exe_file, url_set, args.workdir, module_dir, args.parallel, progress=True)
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

    logger.info("Error set is %d URLs: %s" % (len(error_set), ' '.join(["%d,%s" % (r, u) for r, u in error_set])))

    return error_set


def extract_certificates(args, error_set, test_exe_file):
    global logger, tmp_dir, module_dir
    tmp_cert_dir = os.path.join(tmp_dir, "certs")
    os.mkdir(tmp_cert_dir)

    logger.info("Extracting certificates from %d URLs to `%s`" % (len(error_set), tmp_cert_dir))
    final_error_set = run_test(test_exe_file, error_set, args.workdir, module_dir,
                               min(args.parallel, 10), info=True, cert_dir=tmp_cert_dir)

    # Final set includes additional json data, so filter that out before comparison
    stripped_final_set = set()
    for rank, url, _ in final_error_set:
        stripped_final_set.add((rank, url))
    if stripped_final_set != error_set:
        diff_set = error_set.difference(stripped_final_set)
        logger.warning("Domains dropped out of error set: %s" % diff_set)

    return tmp_cert_dir, final_error_set


def create_report(args, start_time, test_metadata, base_metadata, error_set, cert_dir):
    global logger, module_dir

    timestamp = start_time.strftime("%F-%H-%M-%S")
    run_dir = os.path.join(args.reportdir, "runs", timestamp)
    logger.info("Writing report to `%s`" % run_dir)

    header = {
        "timestamp": timestamp,
        "branch": test_metadata["branch"].capitalize(),
        "description": "Fx%s %s vs Fx%s %s" % (test_metadata["appVersion"], test_metadata["branch"],
                                               base_metadata["appVersion"], base_metadata["branch"]),
        "source": args.testset,
        "test build url": fd.FirefoxDownloader.build_urls[args.test],
        "release build url": fd.FirefoxDownloader.build_urls[args.base],
        "test build metadata": "%s, %s" % (test_metadata["nssVersion"], test_metadata["nsprVersion"]),
        "release build metadata": "%s, %s" % (base_metadata["nssVersion"], base_metadata["nsprVersion"]),
        "Total time": "%d minutes" % int(round((datetime.datetime.now() - start_time).total_seconds() / 60))
    }
    # TODO: Replace {platform} in build URLs

    log_lines = ["%s : %s" % (k, header[k]) for k in header]
    log_lines.append("++++++++++")
    log_lines.append("")

    for rank, url, data in error_set:
        log_lines.append("%d,%s %s" % (rank, url, data))

    # Install static template files in report directory
    template_dir = os.path.join(module_dir, "template")
    if not os.path.isdir(args.reportdir):
        os.makedirs(args.reportdir)
    dir_util.copy_tree(os.path.join(template_dir, "js"),
                       os.path.join(args.reportdir, "js"))
    dir_util.copy_tree(os.path.join(template_dir, "css"),
                       os.path.join(args.reportdir, "css"))
    shutil.copyfile(os.path.join(template_dir, "index.htm"),
                    os.path.join(args.reportdir, "index.htm"))

    # Create per-run directory for report output
    if not os.path.isdir(run_dir):
        os.makedirs(run_dir)
    dir_util.copy_tree(cert_dir, os.path.join(run_dir, "certs"))
    shutil.copyfile(os.path.join(template_dir, "report_template.htm"),
                    os.path.join(run_dir, "index.htm"))

    # Write the final log file
    with open(os.path.join(run_dir, "log.txt"), "w") as log:
        log.write('\n'.join(log_lines))

    # Append to runs.log
    run_log = {
        "run": header["timestamp"],
        "branch": header["branch"],
        "errors": len(error_set),
        "description": header["description"]
    }
    with open(os.path.join(args.reportdir, "runs", "runs.txt"), "a") as log:
        log.write(json.dumps(run_log) + '\n')


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

    if args.reportdir == module_dir:
        logger.critical("Refusing to write report to module directory. Please set --reportdir")
        sys.exit(1)

    cleanup.init()
    tmp_dir = __create_tempdir()

    try:
        test_extract_dir, test_exe_file, base_extract_dir, \
            base_exe_file = get_test_candidates(args)
        test_metadata_log, base_metadata_log = \
            build_data_logs(test_exe_file, base_exe_file, module_dir)

        start_time = datetime.datetime.now()
        error_set = run_tests(args, test_exe_file, base_exe_file)
        # logger.critical("FIXME: Working with static test set")
        # error_set = set([(49182, u'psarips.com'), (257666, u'www.obsidiana.com'), (120451, u'yugiohcardmarket.eu'), (9901, u'englishforums.com'), (43694, u'www.csajokespasik.hu'), (157298, u'futuramo.com'), (1377, u'www.onlinecreditcenter6.com'), (15752, u'www.jcpcreditcard.com'), (137890, u'my.jobs'), (31862, u'samsungcsportal.com'), (40034, u'uob.com.my'), (255349, u'censusmapper.ca'), (89913, u'hslda.org'), (64349, u'www.chevrontexacocards.com'), (69037, u'www.onlinecreditcenter4.com'), (3128, u'www.synchronycredit.com'), (84681, u'ruscreditcard.com'), (241254, u'www.steinmartcredit.com'), (123888, u'saveful.com'), (230374, u'sirdatainitiative.com'), (135435, u'gearheads.in'), (97220, u'gira.de'), (85697, u'magickartenmarkt.de'), (29458, u'cxem.net'), (62059, u'www.awardslinq.com'), (32146, u'www.onlinecreditcenter2.com'), (247769, u'gmprograminfo.com'), (265649, u'piratenpartei.de'), (23525, u'vesti.lv'), (192596, u'robots-and-dragons.de'), (212740, u'www.chs.hu'), (68345, u'bandzone.cz'), (104674, u'incontrion.com'), (174612, u'patschool.com'), (80121, u'27399.com'), (114128, u'universoracionalista.org'), (100333, u'toccata.ru'), (222646, u'futuramo.net'), (14624, u'reviewmyaccount.com'), (147865, u'sherdle.com'), (40192, u'www.belkcredit.com'), (47428, u'www.wangfujing.com'), (162199, u'hikvision.ru'), (74032, u'cardoverview.com'), (22279, u'prospero.ru'), (143928, u'www.e-financas.gov.pt'), (130883, u'favoritsport.com.ua')])

        cert_dir, final_error_set = extract_certificates(args, error_set, test_exe_file)

        create_report(args, start_time, test_metadata_log, base_metadata_log, final_error_set, cert_dir)

    except KeyboardInterrupt:
        logger.critical("\nUser interrupt. Quitting...")
        return False

    if args.ipython:
        from IPython import embed
        embed()

    return True

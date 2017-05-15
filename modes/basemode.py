# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.


import datetime
from distutils import dir_util
import logging
from math import ceil
import cert
import coloredlogs
import json
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



logger = logging.getLogger(__name__)


class BaseMode(object):
    """
    Generic Test Mode
    Base functionality for all tests
    """
    def __init__(self, args, module_dir, tmp_dir):
        global logger
        self.__mode = args.mode
        self.module_dir = module_dir
        self.tmp_dir = tmp_dir


    def generate(self):
        with open(self.__target, "w") as f:
            json.dump({"result": self.__result, "metadata": self.__metadata}, f, sort_keys=True, indent=4)


    def get_test_candidate(self, args, build):
        """
        Download and extract a build candidate
        :param args: command line arguments object
        :return: two FirefoxApp objects for test and base candidate
        """
        global logger

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
        self.fdl = fd.FirefoxDownloader(args.workdir, cache_timeout=1*60*60)

        # Download candidate
        build_archive_file = self.fdl.download(build, platform)
        if build_archive_file is None:
            sys.exit(-1)
        # Extract candidate archive
        candidate_app = fe.extract(build_archive_file, args.workdir, cache_timeout=1*60*60)
        logger.debug("Build candidate executable is `%s`" % candidate_app.exe)

        return candidate_app


    def collect_worker_info(self, app):
        worker = xw.XPCShellWorker(app)
        worker.spawn()
        worker.send(xw.Command("info"))
        result = worker.wait().result
        worker.terminate()
        return result


    def make_profile(self, args, profile_name):
        global logger

        # create directories for profiles
        default_profile_dir = os.path.join(self.module_dir, "default_profile")
        new_profile_dir = os.path.join(self.tmp_dir, profile_name)

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


    def save_profile(self, args, profile_name, start_time):
        global logger

        timestamp = start_time.strftime("%Y-%m-%d-%H-%M-%S")
        run_dir = os.path.join(args.reportdir, "runs", timestamp)

        logger.debug("Saving profile to `%s`" % run_dir)
        dir_util.copy_tree(os.path.join(self.tmp_dir, profile_name), os.path.join(run_dir, profile_name))


    def run_test(self, app, url_list, args, profile=None, num_workers=None, n_per_worker=None, timeout=None,
             get_info=False, get_certs=False, progress=False, return_only_errors=True):

        global logger

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

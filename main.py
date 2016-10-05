#!/usr/bin/env python2

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import os
import random
import shutil
import sys
import tempfile
import time

import cleanup
import firefox_downloader as fd
import firefox_extractor as fe
import firefox_runner as fr
import url_store as us


def get_argparser():
    home = os.path.expanduser('~')
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug',
                        help='Enable debug',
                        action='store_true',
                        default=False)
    parser.add_argument('-w', '--workdir',
                        help='Path to working directory',
                        type=os.path.abspath,
                        action='store',
                        default=home+"/.tlscanary")
    parser.add_argument('-s', '--source',
                        help='URL test set directory',
                        action='store',
                        default='alexa')
    parser.add_argument('-t', '--test',
                        help='Firefox version to test',
                        action='store',
                        default='nightly')
    parser.add_argument('-b', '--base',
                        help='Firefox version to test against',
                        action='store',
                        default='release')
    parser.add_argument('tests',
                        metavar='TEST',
                        help='Tests to run',
                        nargs='*')
    return parser


tmp_dir = None
module_dir = None

def create_tempdir():
    global tmp_dir
    tmp_dir = tempfile.mkdtemp(prefix='tlscanary_')
    print 'Creating temp dir `%s`' % tmp_dir
    return tmp_dir


class RemoveTempDir(cleanup.CleanUp):
    @staticmethod
    def at_exit():
        global tmp_dir
        if tmp_dir is not None:
            print 'Removing temp dir `%s`' % tmp_dir
            shutil.rmtree(tmp_dir, ignore_errors=True)


def run_tests(args):
    global tmp_dir, module_dir
    create_tempdir()
    module_dir = os.path.split(__file__)[0]
    data_dir = os.path.join(module_dir, 'data')

    print args
    print os.path.split(__file__)
    
    if sys.platform == 'darwin':
        platform = 'osx'
    else:
        print 'Unsupported platform: %s' % sys.platform
        sys.exit(5)
    print 'Detected platform: %s' % platform

    urldb = us.URLStore(data_dir)
    print 'Available URL databases: %s' % ', '.join(urldb.list())

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
    test_extract_dir, test_exe_file = fe.extract(platform, test_archive_file, tmp_dir)
    if test_exe_file is None:
        sys.exit(-1)

    print 'Testing `%s` against baseline `%s`' % (base_exe_file, test_exe_file)

    test_runner = fr.FirefoxRunner(test_exe_file, 10)

    run_until = time.time() + 10
    idn = 0
    try:
        while time.time() < run_until:
            test_runner.maintain_worker_queue()

            for worker in test_runner.workers:
                task = '%d:%d+%d\n' % (idn, random.randint(1, 100),
                                       random.randint(1, 100))
                worker.stdin.write(task)
                idn += 1
                print worker, 'task:', task,

            while True:
                result = test_runner.get_result()
                if result is None:
                    break
                print "Result in main:", result

            time.sleep(0.05)
    except KeyboardInterrupt:
        print 'User abort'

    test_runner.terminate_workers()

    return True


# This is the entry point used in setup.py

def main():
    cleanup.init()

    parser = get_argparser()
    args = parser.parse_args()

    return run_tests(args)

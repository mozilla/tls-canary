# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import shutil
import tempfile

import firefox_downloader as fd
import firefox_extractor as fe

# Global variables for all tests
# CAVE: Must be accessed as tests.var to get the dynamic results written by setup_package().
#      `from test import var` on the module level always yields the default values, because
#      the import happens before setup is run.
test_app = None
test_archive = None
test_dir = os.path.split(__file__)[0]
tmp_dir = None


def setup_package():
    """Set up shared test fixtures"""
    global test_app, test_archive, tmp_dir

    # Create a tmp dir
    tmp_dir = tempfile.mkdtemp(prefix="tlscanarytest_")

    # Get ourselves a Firefox app for the local platform.
    fdl = fd.FirefoxDownloader(tmp_dir)
    test_archive = fdl.download("nightly", use_cache=True)
    test_app = fe.extract(test_archive, tmp_dir)


def teardown_package():
    """Tear down shared test fixtures"""
    global tmp_dir
    if tmp_dir is not None:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        tmp_dir = None

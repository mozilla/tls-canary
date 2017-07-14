# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import mock
from nose.plugins import capture
from nose.tools import *
import os
import StringIO

from tlscanary import main
import tests


def test_tlscanary_regression_and_log():
    """TLS Canary can make regression runs"""
    work_dir = os.path.join(tests.tmp_dir, "workdir")

    # Run a quick regression scan, simulating error conditions by -p1
    argv = [
        "--workdir", work_dir,
        "regression",
        "-t", tests.test_archive,
        "-b", tests.test_archive,
        "-l", "9",
        "-p1", "security.tls.version.min;4"
    ]
    ret = main.main(argv)
    assert_equal(ret, 0, "regression run finished without error")

    # Check log
    argv = [
        "--workdir", work_dir,
        "log",
        "-a", "json",
        "-i", "1"
    ]
    with mock.patch('sys.stdout', new=StringIO.StringIO()) as mock_stdout:
        ret = main.main(argv)
        stdout = mock_stdout.getvalue()
    assert_equal(ret, 0, "regression log dump finished without error")
    assert_true(len(stdout) > 0, "regression log dump is not empty")
    log = json.loads(stdout)
    assert_true(type(log) is list, "regression JSON log is list")
    assert_equal(len(log), 1, "there is one log in the dump")
    assert_true("meta" in log[0] and "data" in log[0], "log has meta and data")
    assert_equal(len(log[0]["data"]), 9, "log has correct number of lines")


def test_tlscanary_srcupdate_and_scan_and_log():
    """TLS Canary can update source DBs"""
    work_dir = os.path.join(tests.tmp_dir, "workdir")

    # Compile a fresh `nosetest` host db
    argv = [
        "--workdir", work_dir,
        "srcupdate",
        "-b", tests.test_archive,
        "-l", "5",
        "-s", "nosetest"
    ]
    ret = main.main(argv)
    assert_equal(ret, 0, "srcupdate run finished without error")

    # Run a scan against `nosetest` host db
    argv = [
        "--workdir", work_dir,
        "scan",
        "-t", tests.test_archive,
        "-s", "nosetest",
    ]
    ret = main.main(argv)
    assert_equal(ret, 0, "scan run finished without error")

    # Check logs
    argv = [
        "--workdir", work_dir,
        "log",
        "-a", "json",
        "-i", "1"
    ]
    with mock.patch('sys.stdout', new=StringIO.StringIO()) as mock_stdout:
        ret = main.main(argv)
        stdout = mock_stdout.getvalue()
    assert_equal(ret, 0, "scan log dump finished without error")
    log = json.loads(stdout)
    assert_true(type(log) is list, "scan JSON log is list")
    assert_equal(len(log), 1, "there is one log in the dump")
    assert_true("meta" in log[0] and "data" in log[0], "log has meta and data")
    assert_equal(len(log[0]["data"]), 5, "log has correct number of lines")

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from distutils.spawn import find_executable
from nose import SkipTest
from nose.tools import *
import os
import shutil
import subprocess
import tempfile

import firefox_extractor as fe
import firefox_app as fa


test_dir = os.path.split(__file__)[0]
tmp_dir = None


def test_setup():
    """set up test fixtures"""
    global tmp_dir
    tmp_dir = tempfile.mkdtemp(prefix="tlscanarytest_")


def test_teardown():
    """tear down test fixtures"""
    global tmp_dir
    if tmp_dir is not None:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        tmp_dir = None


@with_setup(test_setup, test_teardown)
def test_osx_extractor():
    """Extractor can extract a OS X Nightly archive"""
    global test_dir, tmp_dir

    sz_out = subprocess.check_output("7z")
    assert_true(sz_out is not None)
    sz_version = float(sz_out.splitlines()[1].split()[2])
    if sz_version < 16:
        raise SkipTest('7-zip version 16 required to extract DMG images')

    test_archive = os.path.join(test_dir, "files", "firefox-nightly_osx-dummy.dmg")
    assert_true(os.path.isfile(test_archive))

    app = fe.extract(test_archive, tmp_dir)

    assert_true(type(app) is fa.FirefoxApp, "return value is correct")
    assert_true(os.path.isdir(app.app_dir), "app dir is extracted")
    assert_true(os.path.isfile(app.app_ini), "app ini is extracted")
    assert_true(os.path.isdir(app.browser), "browser dir is extracted")
    assert_true(os.path.isfile(app.exe), "exe file is extracted")
    assert_true(app.exe.startswith(tmp_dir), "archive is extracted to specified directory")
    assert_equal(app.platform, "osx", "platform is detected correctly")
    assert_equal(app.release, "Nightly", "release branch is detected correctly")
    assert_equal(app.version, "53.0a1", "version is detected correctly")


@with_setup(test_setup, test_teardown)
def test_linux_extractor():
    """Extractor can extract a Linux Nightly archive"""
    global test_dir, tmp_dir

    test_archive = os.path.join(test_dir, "files", "firefox-nightly_linux-dummy.tar.bz2")
    assert_true(os.path.isfile(test_archive))

    app = fe.extract(test_archive, tmp_dir)

    assert_true(type(app) is fa.FirefoxApp, "return value is correct")
    assert_true(os.path.isdir(app.app_dir), "app dir is extracted")
    assert_true(os.path.isfile(app.app_ini), "app ini is extracted")
    assert_true(os.path.isdir(app.browser), "browser dir is extracted")
    assert_true(os.path.isfile(app.exe), "exe file is extracted")
    assert_true(app.exe.startswith(tmp_dir), "archive is extracted to specified directory")
    assert_equal(app.platform, "linux", "platform is detected correctly")
    assert_equal(app.release, "Nightly", "release branch is detected correctly")
    assert_equal(app.version, "53.0a1", "version is detected correctly")


@with_setup(test_setup, test_teardown)
def test_win_extractor():
    """Extractor can extract a Windows Nightly archive"""
    global test_dir, tmp_dir

    test_archive = os.path.join(test_dir, "files", "firefox-nightly_win-dummy.exe")
    assert_true(os.path.isfile(test_archive))

    app = fe.extract(test_archive, tmp_dir)

    assert_true(type(app) is fa.FirefoxApp, "return value is correct")
    assert_true(os.path.isdir(app.app_dir), "app dir is extracted")
    assert_true(os.path.isfile(app.app_ini), "app ini is extracted")
    assert_true(os.path.isdir(app.browser), "browser dir is extracted")
    assert_true(os.path.isfile(app.exe), "exe file is extracted")
    assert_true(app.exe.startswith(tmp_dir), "archive is extracted to specified directory")
    assert_equal(app.platform, "win32", "platform is detected correctly")
    assert_equal(app.release, "Nightly", "release branch is detected correctly")
    assert_equal(app.version, "55.0a1", "version is detected correctly")


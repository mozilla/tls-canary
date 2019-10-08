# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import pkg_resources as pkgr
import pytest
import subprocess


import tlscanary.tools.firefox_extractor as fe
import tlscanary.tools.firefox_app as fa


def test_osx_extractor(tmpdir):
    """Extractor can extract a OS X Nightly archive"""

    sz_out = subprocess.check_output("7z")
    assert sz_out is not None
    sz_version = float(sz_out.splitlines()[1].split()[2])
    if sz_version < 16:
        pytest.skip("7-zip version 16+ required to extract DMG images")

    test_archive = pkgr.resource_filename(__name__, "files/firefox-nightly_osx-dummy.dmg")
    assert os.path.isfile(test_archive)

    app = fe.extract(test_archive, tmpdir)

    assert type(app) is fa.FirefoxApp, "return value is correct"
    assert os.path.isdir(app.app_dir), "app dir is extracted"
    assert os.path.isfile(app.app_ini), "app ini is extracted"
    assert os.path.isdir(app.browser), "browser dir is extracted"
    assert os.path.isfile(app.exe), "exe file is extracted"
    assert app.exe.startswith(str(tmpdir)), "archive is extracted to specified directory"
    assert app.platform == "osx", "platform is detected correctly"
    assert app.release == "Nightly", "release branch is detected correctly"
    assert app.version == "53.0a1", "version is detected correctly"


def test_linux_extractor(tmpdir):
    """Extractor can extract a Linux Nightly archive"""

    test_archive = pkgr.resource_filename(__name__, "files/firefox-nightly_linux-dummy.tar.bz2")
    assert os.path.isfile(test_archive)

    app = fe.extract(test_archive, tmpdir)

    assert type(app) is fa.FirefoxApp, "return value is correct"
    assert os.path.isdir(app.app_dir), "app dir is extracted"
    assert os.path.isfile(app.app_ini), "app ini is extracted"
    assert os.path.isdir(app.browser), "browser dir is extracted"
    assert os.path.isfile(app.exe), "exe file is extracted"
    assert app.exe.startswith(str(tmpdir)), "archive is extracted to specified directory"
    assert app.platform == "linux", "platform is detected correctly"
    assert app.release == "Nightly", "release branch is detected correctly"
    assert app.version == "53.0a1", "version is detected correctly"


def test_win_extractor(tmpdir):
    """Extractor can extract a Windows Nightly archive"""

    test_archive = pkgr.resource_filename(__name__, "files/firefox-nightly_win-dummy.exe")
    assert os.path.isfile(test_archive)

    app = fe.extract(test_archive, tmpdir)

    assert type(app) is fa.FirefoxApp, "return value is correct"
    assert os.path.isdir(app.app_dir), "app dir is extracted"
    assert os.path.isfile(app.app_ini), "app ini is extracted"
    assert os.path.isdir(app.browser), "browser dir is extracted"
    assert os.path.isfile(app.exe), "exe file is extracted"
    assert app.exe.startswith(str(tmpdir)), "archive is extracted to specified directory"
    assert app.platform == "win32", "platform is detected correctly"
    assert app.release == "Nightly", "release branch is detected correctly"
    assert app.version == "55.0a1", "version is detected correctly"

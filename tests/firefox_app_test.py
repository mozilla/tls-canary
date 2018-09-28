# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import pytest
import subprocess

import tlscanary.firefox_app as fa


def __check_app(app):
    assert type(app) is fa.FirefoxApp, "App has right type"
    assert os.path.isdir(app.app_dir), "App dir exists"
    assert os.path.isfile(app.exe) and os.access(app.exe, os.X_OK), "App binary is executable"


def __run_app(app):
    cmd = [app.exe, '-xpcshell', "-g", app.gredir, "-a", app.browser]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    p.communicate(b"quit();\n")
    ret = p.wait(timeout=1)  # Throws TimeoutExpired on timeout
    assert ret == 0, "Firefox app runs XPCShell without error"


def __check_and_run_app(app):
    """Check Firefox App and try to run it"""
    __check_app(app)
    __run_app(app)


def test_nightly_app(nightly_app):
    """Test Firefox Nightly app on local platform"""
    __check_and_run_app(nightly_app)


@pytest.mark.slow
def test_beta_app(beta_app):
    """Test Firefox Beta app on local platform"""
    __check_and_run_app(beta_app)


@pytest.mark.slow
def test_release_app(release_app):
    """Test Firefox Release app on local platform"""
    __check_and_run_app(release_app)


@pytest.mark.slow
def test_esr_app(esr_app):
    """Test Firefox ESR app on local platform"""
    __check_and_run_app(esr_app)


@pytest.mark.slow
def test_nightly_win_app(nightly_win_app):
    """Test Firefox Nightly app for Windows"""
    __check_app(nightly_win_app)


@pytest.mark.slow
def test_nightly_osx_app(nightly_osx_app):
    """Test Firefox Nightly app for Mac OS X"""
    __check_app(nightly_osx_app)


@pytest.mark.slow
def test_nightly_linux_app(nightly_linux_app):
    """Test Firefox Nightly app for Mac Linux"""
    __check_app(nightly_linux_app)


@pytest.mark.slow
def test_beta_win_app(beta_win_app):
    """Test Firefox Beta app for Windows"""
    __check_app(beta_win_app)


@pytest.mark.slow
def test_beta_osx_app(beta_osx_app):
    """Test Firefox Beta app for Mac OS X"""
    __check_app(beta_osx_app)


@pytest.mark.slow
def test_beta_linux_app(beta_linux_app):
    """Test Firefox Beta app for Mac Linux"""
    __check_app(beta_linux_app)


@pytest.mark.slow
def test_release_win_app(release_win_app):
    """Test Firefox Release app for Windows"""
    __check_app(release_win_app)


@pytest.mark.slow
def test_release_osx_app(release_osx_app):
    """Test Firefox Release app for Mac OS X"""
    __check_app(release_osx_app)


@pytest.mark.slow
def test_release_linux_app(release_linux_app):
    """Test Firefox Release app for Mac Linux"""
    __check_app(release_linux_app)


@pytest.mark.slow
def test_esr_win_app(esr_win_app):
    """Test Firefox ESR app for Windows"""
    __check_app(esr_win_app)


@pytest.mark.slow
def test_esr_osx_app(esr_osx_app):
    """Test Firefox ESR app for Mac OS X"""
    __check_app(esr_osx_app)


@pytest.mark.slow
def test_esr_linux_app(esr_linux_app):
    """Test Firefox ESR app for Mac Linux"""
    __check_app(esr_linux_app)

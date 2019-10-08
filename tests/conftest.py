# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import pytest
from subprocess import check_output

import tlscanary.tools.firefox_downloader as fd
import tlscanary.tools.firefox_extractor as fe


@pytest.fixture(scope="session")
def caching_firefox_downloader(tmpdir_factory):
    return fd.FirefoxDownloader(tmpdir_factory.mktemp("caching_downloader"))


@pytest.fixture(scope="session")
def nightly_archive(caching_firefox_downloader):
    """A Firefox Nightly archive downloaded from the Web"""
    return caching_firefox_downloader.download("nightly", use_cache=True)


@pytest.fixture(scope="session")
def nightly_win_archive(caching_firefox_downloader):
    """A Firefox Nightly archive for Windows downloaded from the Web"""
    return caching_firefox_downloader.download("nightly", platform="win", use_cache=True)


@pytest.fixture(scope="session")
def nightly_osx_archive(caching_firefox_downloader):
    """A Firefox Nightly archive for Mac OS X downloaded from the Web"""
    return caching_firefox_downloader.download("nightly", platform="osx", use_cache=True)


@pytest.fixture(scope="session")
def nightly_linux_archive(caching_firefox_downloader):
    """A Firefox Nightly archive for Linux downloaded from the Web"""
    return caching_firefox_downloader.download("nightly", platform="linux", use_cache=True)


@pytest.fixture(scope="session")
def beta_archive(caching_firefox_downloader):
    """A Firefox Beta archive downloaded from the Web"""
    return caching_firefox_downloader.download("beta", use_cache=True)


@pytest.fixture(scope="session")
def beta_win_archive(caching_firefox_downloader):
    """A Firefox Beta archive for Windows downloaded from the Web"""
    return caching_firefox_downloader.download("beta", platform="win", use_cache=True)


@pytest.fixture(scope="session")
def beta_osx_archive(caching_firefox_downloader):
    """A Firefox Beta archive for Mac OS X downloaded from the Web"""
    return caching_firefox_downloader.download("beta", platform="osx", use_cache=True)


@pytest.fixture(scope="session")
def beta_linux_archive(caching_firefox_downloader):
    """A Firefox Beta archive for Linux downloaded from the Web"""
    return caching_firefox_downloader.download("beta", platform="linux", use_cache=True)


@pytest.fixture(scope="session")
def release_archive(caching_firefox_downloader):
    """A Firefox Release archive downloaded from the Web"""
    return caching_firefox_downloader.download("release", use_cache=True)


@pytest.fixture(scope="session")
def release_win_archive(caching_firefox_downloader):
    """A Firefox Release archive for Windows downloaded from the Web"""
    return caching_firefox_downloader.download("release", platform="win", use_cache=True)


@pytest.fixture(scope="session")
def release_osx_archive(caching_firefox_downloader):
    """A Firefox Release archive for Mac OS X downloaded from the Web"""
    return caching_firefox_downloader.download("release", platform="osx", use_cache=True)


@pytest.fixture(scope="session")
def release_linux_archive(caching_firefox_downloader):
    """A Firefox Release archive for Linux downloaded from the Web"""
    return caching_firefox_downloader.download("release", platform="linux", use_cache=True)


@pytest.fixture(scope="session")
def esr_archive(caching_firefox_downloader):
    """A Firefox ESR archive downloaded from the Web"""
    return caching_firefox_downloader.download("esr", use_cache=True)


@pytest.fixture(scope="session")
def esr_win_archive(caching_firefox_downloader):
    """A Firefox ESR archive for Windows downloaded from the Web"""
    return caching_firefox_downloader.download("esr", platform="win", use_cache=True)


@pytest.fixture(scope="session")
def esr_osx_archive(caching_firefox_downloader):
    """A Firefox ESR archive for Mac OS X downloaded from the Web"""
    return caching_firefox_downloader.download("esr", platform="osx", use_cache=True)


@pytest.fixture(scope="session")
def esr_linux_archive(caching_firefox_downloader):
    """A Firefox ESR archive for Linux downloaded from the Web"""
    return caching_firefox_downloader.download("esr", platform="linux", use_cache=True)


@pytest.fixture(scope="session")
def nightly_app(tmpdir_factory, nightly_archive):
    """A Firefox Nightly app fixture"""
    return fe.extract(nightly_archive, tmpdir_factory.mktemp("nightly_app"))


@pytest.fixture(scope="session")
def beta_app(tmpdir_factory, beta_archive):
    """A Firefox Beta app fixture"""
    return fe.extract(beta_archive, tmpdir_factory.mktemp("beta_app"))


@pytest.fixture(scope="session")
def release_app(tmpdir_factory, release_archive):
    """A Firefox Release app fixture"""
    return fe.extract(release_archive, tmpdir_factory.mktemp("release_app"))


@pytest.fixture(scope="session")
def esr_app(tmpdir_factory, esr_archive):
    """A Firefox ESR app fixture"""
    return fe.extract(esr_archive, tmpdir_factory.mktemp("esr_app"))


@pytest.fixture(scope="session")
def nightly_win_app(tmpdir_factory, nightly_win_archive):
    """A Firefox Nightly app for Windows fixture"""
    return fe.extract(nightly_win_archive, tmpdir_factory.mktemp("nightly_win_app"))


@pytest.fixture(scope="session")
def beta_win_app(tmpdir_factory, beta_win_archive):
    """A Firefox Beta app for Windows fixture"""
    return fe.extract(beta_win_archive, tmpdir_factory.mktemp("beta_win_app"))


@pytest.fixture(scope="session")
def release_win_app(tmpdir_factory, release_win_archive):
    """A Firefox Release app for Windows fixture"""
    return fe.extract(release_win_archive, tmpdir_factory.mktemp("release_win_app"))


@pytest.fixture(scope="session")
def esr_win_app(tmpdir_factory, esr_win_archive):
    """A Firefox ESR app for Windows fixture"""
    return fe.extract(esr_win_archive, tmpdir_factory.mktemp("esr_win_app"))


def __check_7z_version():
    sz_out = check_output("7z")
    assert sz_out is not None
    sz_version = float(sz_out.splitlines()[1].split()[2])
    if sz_version < 16:
        pytest.skip("7-zip version 16+ required to extract DMG images for Mac OS X")


@pytest.fixture(scope="session")
def nightly_osx_app(tmpdir_factory, nightly_osx_archive):
    """A Firefox Nightly app for Mac OS X fixture"""
    __check_7z_version()
    return fe.extract(nightly_osx_archive, tmpdir_factory.mktemp("nightly_osx_app"))


@pytest.fixture(scope="session")
def beta_osx_app(tmpdir_factory, beta_osx_archive):
    """A Firefox Beta app for Mac OS X fixture"""
    __check_7z_version()
    return fe.extract(beta_osx_archive, tmpdir_factory.mktemp("beta_osx_app"))


@pytest.fixture(scope="session")
def release_osx_app(tmpdir_factory, release_osx_archive):
    """A Firefox Release app for Mac OS X fixture"""
    __check_7z_version()
    return fe.extract(release_osx_archive, tmpdir_factory.mktemp("release_osx_app"))


@pytest.fixture(scope="session")
def esr_osx_app(tmpdir_factory, esr_osx_archive):
    """A Firefox ESR app for Mac OS X fixture"""
    __check_7z_version()
    return fe.extract(esr_osx_archive, tmpdir_factory.mktemp("esr_osx_app"))


@pytest.fixture(scope="session")
def nightly_linux_app(tmpdir_factory, nightly_linux_archive):
    """A Firefox Nightly app for Linux fixture"""
    return fe.extract(nightly_linux_archive, tmpdir_factory.mktemp("nightly_linux_app"))


@pytest.fixture(scope="session")
def beta_linux_app(tmpdir_factory, beta_linux_archive):
    """A Firefox Beta app for Linux fixture"""
    return fe.extract(beta_linux_archive, tmpdir_factory.mktemp("beta_linux_app"))


@pytest.fixture(scope="session")
def release_linux_app(tmpdir_factory, release_linux_archive):
    """A Firefox Release app for Linux fixture"""
    return fe.extract(release_linux_archive, tmpdir_factory.mktemp("release_linux_app"))


@pytest.fixture(scope="session")
def esr_linux_app(tmpdir_factory, esr_linux_archive):
    """A Firefox ESR app for Linux fixture"""
    return fe.extract(esr_linux_archive, tmpdir_factory.mktemp("esr_linux_app"))

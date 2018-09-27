# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import pytest

import tlscanary.firefox_downloader as fd
import tlscanary.firefox_extractor as fe


@pytest.fixture(scope="session")
def nightly_archive(tmpdir_factory):
    """A Firefox Nightly archive downloaded from the Web"""
    fdl = fd.FirefoxDownloader(tmpdir_factory.mktemp("nightly_archive"))
    return fdl.download("nightly", use_cache=False)


@pytest.fixture(scope="session")
def beta_archive(tmpdir_factory):
    """A Firefox Beta archive downloaded from the Web"""
    fdl = fd.FirefoxDownloader(tmpdir_factory.mktemp("beta_archive"))
    return fdl.download("beta", use_cache=False)


@pytest.fixture(scope="session")
def release_archive(tmpdir_factory):
    """A Firefox Release archive downloaded from the Web"""
    fdl = fd.FirefoxDownloader(tmpdir_factory.mktemp("release_archive"))
    return fdl.download("release", use_cache=False)


@pytest.fixture(scope="session")
def esr_archive(tmpdir_factory):
    """A Firefox ESR archive downloaded from the Web"""
    fdl = fd.FirefoxDownloader(tmpdir_factory.mktemp("esr_archive"))
    return fdl.download("esr", use_cache=False)


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
    return fe.extract(esr_archive, tmpdir_factory.mktemp(esr_app))

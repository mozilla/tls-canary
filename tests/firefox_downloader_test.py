# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import pytest
from time import sleep
import unittest.mock as mock

import tlscanary.firefox_downloader as fd


def test_firefox_downloader_instance(tmpdir):
    """FirefoxDownloader instances sanity check"""

    fdl = fd.FirefoxDownloader(tmpdir)

    build_list, platform_list, test_default, base_default = fdl.list()
    assert "nightly" in build_list and "release" in build_list, "build list looks sane"
    assert "linux" in platform_list and "osx" in platform_list, "platform list looks sane"
    assert test_default in build_list and base_default in build_list, "defaults are valid builds"


def test_firefox_downloader_exceptions(tmpdir):
    """Test handling of invalid parameters"""

    fdl = fd.FirefoxDownloader(tmpdir)
    build_list, platform_list, test_default, base_default = fdl.list()

    assert "foobar" not in build_list and "foobar" not in platform_list

    with pytest.raises(Exception):
        fdl.download("foobar", platform_list[0])

    with pytest.raises(Exception):
        fdl.download(test_default, "foobar")


@mock.patch('urllib.request.urlopen')
@mock.patch('sys.stdout')  # to silence progress bar
def test_firefox_downloader_downloading(mock_stdout, mock_urlopen, tmpdir):
    """Test the download function"""
    del mock_stdout

    # This test is checking caching behavior, hence:
    # Using a test-specific test directory to not wipe regular cache.
    test_tmp_dir = str(tmpdir.join("download_test"))

    fdl = fd.FirefoxDownloader(test_tmp_dir, cache_timeout=1)

    mock_req = mock.Mock()
    mock_read = mock.Mock(side_effect=(b"foo", b"bar", None))
    mock_info = mock.Mock()
    mock_get = mock.Mock(return_value="6")
    mock_info.return_value = mock.Mock(get=mock_get)
    mock_req.info = mock_info
    mock_req.read = mock_read
    mock_urlopen.return_value = mock_req

    output_file_name = fdl.download("nightly", "linux", use_cache=True)
    assert mock_get.call_args_list == [(("Content-Length",),)],\
        "only checks content length (assumed by test mock)"
    expected_url = """https://download.mozilla.org/?product=firefox-nightly-latest&os=linux64&lang=en-US"""
    assert mock_urlopen.call_args_list == [((expected_url,),)], "downloads the expected URL"
    assert len(mock_read.call_args_list) == 3, "properly calls read()"
    assert output_file_name.endswith("firefox-nightly_linux.tar.bz2"), "uses expected file name"
    assert output_file_name.startswith(test_tmp_dir), "writes file to expected directory"
    assert os.path.isfile(output_file_name), "creates proper file"
    with open(output_file_name, "rb") as f:
        content = f.read()
    assert content == b"foobar", "downloads expected content"

    # Test caching by re-downloading
    mock_read.reset_mock()
    mock_read.side_effect = (b"foo", b"bar", None)
    second_output_file_name = fdl.download("nightly", "linux", use_cache=True)
    assert not mock_read.called, "does not re-download"
    assert output_file_name == second_output_file_name, "uses cached file"

    # Test purging on obsolete cache. Cache is purged on fdl init.
    sleep(1.1)
    mock_read.reset_mock()
    mock_read.side_effect = (b"foo", b"bar", None)
    fdl = fd.FirefoxDownloader(test_tmp_dir, cache_timeout=1)
    fdl.download("nightly", "linux", use_cache=True)
    assert mock_read.called, "re-downloads when cache is stale"

    # Test caching when file changes upstream (checks file size).
    mock_get.reset_mock()
    mock_get.return_value = "7"
    mock_read.reset_mock()
    mock_read.side_effect = (b"foo", b"barr", None)
    fdl.download("nightly", "linux", use_cache=True)
    assert mock_read.called, "re-downloads when upstream changes"

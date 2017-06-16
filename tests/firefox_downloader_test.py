# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import mock
from nose.tools import *
import os
from time import sleep

import tlscanary.firefox_downloader as fd
import tests


def test_firefox_downloader_instance():
    """FirefoxDownloader instances sanity check"""

    # This test is checking caching behavior, hence:
    # Using a test-specific test directory to not wipe regular cache.
    test_tmp_dir = os.path.join(tests.tmp_dir, "download_test")

    fdl = fd.FirefoxDownloader(test_tmp_dir)

    build_list, platform_list, test_default, base_default = fdl.list()
    assert_true("nightly" in build_list and "release" in build_list, "build list looks sane")
    assert_true("linux" in platform_list and "osx" in platform_list, "platform list looks sane")
    assert_true(test_default in build_list and base_default in build_list, "defaults are valid builds")


def test_firefox_downloader_exceptions():
    """Test handling of invalid parameters"""

    # This test is checking caching behavior, hence:
    # Using a test-specific test directory to not wipe regular cache.
    test_tmp_dir = os.path.join(tests.tmp_dir, "download_test")

    fdl = fd.FirefoxDownloader(test_tmp_dir, cache_timeout=1)
    build_list, platform_list, test_default, base_default = fdl.list()

    assert_true("foobar" not in build_list and "foobar" not in platform_list)
    assert_raises(Exception, fdl.download, "foobar", platform_list[0])
    assert_raises(Exception, fdl.download, test_default, "foobar")


@mock.patch('urllib2.urlopen')
@mock.patch('sys.stdout')  # to silence progress bar
def test_firefox_downloader_downloading(mock_stdout, mock_urlopen):
    """Test the download function"""
    del mock_stdout

    # This test is checking caching behavior, hence:
    # Using a test-specific test directory to not wipe regular cache.
    test_tmp_dir = os.path.join(tests.tmp_dir, "download_test")

    fdl = fd.FirefoxDownloader(test_tmp_dir, cache_timeout=1)

    mock_req = mock.Mock()
    mock_read = mock.Mock(side_effect=("foo", "bar", None))
    mock_info = mock.Mock()
    mock_get = mock.Mock(return_value="6")
    mock_info.return_value = mock.Mock(get=mock_get)
    mock_req.info = mock_info
    mock_req.read = mock_read
    mock_urlopen.return_value = mock_req

    output_file_name = fdl.download("nightly", "linux", use_cache=True)
    assert_equal(mock_get.call_args_list, [(("Content-Length",),)],
                 "only checks content length (assumed by test mock)")
    expected_url = """https://download.mozilla.org/?product=firefox-nightly-latest&os=linux64&lang=en-US"""
    assert_true(mock_urlopen.call_args_list == [((expected_url,),)], "downloads the expected URL")
    assert_equal(len(mock_read.call_args_list), 3, "properly calls read()")
    assert_true(output_file_name.endswith("firefox-nightly_linux.tar.bz2"), "uses expected file name")
    assert_true(output_file_name.startswith(test_tmp_dir), "writes file to expected directory")
    assert_true(os.path.isfile(output_file_name), "creates proper file")
    with open(output_file_name, "r") as f:
        content = f.read()
    assert_equal(content, "foobar", "downloads expected content")

    # Test caching by re-downloading
    mock_read.reset_mock()
    mock_read.side_effect = ("foo", "bar", None)
    second_output_file_name = fdl.download("nightly", "linux", use_cache=True)
    assert_false(mock_read.called, "does not re-download")
    assert_equal(output_file_name, second_output_file_name, "uses cached file")

    # Test purging on obsolete cache. Cache is purged on fdl init.
    sleep(1.1)
    mock_read.reset_mock()
    mock_read.side_effect = ("foo", "bar", None)
    fdl = fd.FirefoxDownloader(test_tmp_dir, cache_timeout=1)
    fdl.download("nightly", "linux", use_cache=True)
    assert_true(mock_read.called, "re-downloads when cache is stale")

    # Test caching when file changes upstream (checks file size).
    mock_get.reset_mock()
    mock_get.return_value = "7"
    mock_read.reset_mock()
    mock_read.side_effect = ("foo", "barr", None)
    fdl.download("nightly", "linux", use_cache=True)
    assert_true(mock_read.called, "re-downloads when upstream changes")

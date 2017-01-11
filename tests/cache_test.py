# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from math import floor
from nose.tools import *
import os
import shutil
import tempfile
from time import sleep, time

import cache


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
def test_cache_instance():
    """Comprehensive cache test suite"""
    global tmp_dir

    # CAVE: Some file systems (HFS+, ext3, ...) only provide timestamps with 1.0 second resolution.
    # This affects testing accuracy when working with `maximum_age` in the range of a second.
    # Wait until we're within 10ms past a full second to keep jitter low and this test stable.
    t = time()
    while t - floor(t) >= 0.01:
        t = time()

    cache_root_dir = os.path.join(tmp_dir, "test_cache")
    dc = cache.DiskCache(cache_root_dir, maximum_age=1, purge=False)

    assert_true(os.path.isdir(cache_root_dir), "cache creates directory")
    assert_equal(len(dc.list()), 0, "cache is initially empty")

    # Create a test entry in the cache
    test_file = dc["foo"]
    with open(test_file, "w") as f:
        f.write("foo")

    assert_true(test_file.startswith(cache_root_dir), "cache entries are located in cache directory")
    assert_true("foo" in dc, "cache accepts new file entries")
    assert_false("baz" in dc, "cache does not obviously phantasize about its content")

    # Create a slightly newer cache entry
    # Ensure that it's regarded to be one second younger even with 1s mtime resolution
    sleep(1.01)
    newer_test_file = dc["bar"]
    with open(newer_test_file, "w") as f:
        f.write("bar")

    assert_true("foo" in dc and "bar" in dc and len(dc.list()) == 2, "cache accepts more new file entries")

    # At this point, "foo" is considered to be at least 1s old, "bar" just a few ms.
    assert_true("foo" in dc and "bar" in dc, "purge only happens when explicitly called")
    dc.purge(maximum_age=10)
    assert_true("foo" in dc and "bar" in dc, "purge only affects stale files")
    dc.purge()  # uses `maximum_age` value from init, 1
    assert_true("foo" not in dc, "purge actually purges")
    assert_true("bar" in dc, "purge does not overly purge")

    dc.delete()
    assert_true("bar" not in dc and len(dc.list()) == 0, "cache can be fully emptied")

    # Deleting unknown cache entries should not lead to an error
    dc.delete("foofoo")

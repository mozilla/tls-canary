# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from nose.tools import *
import os

import tlscanary.sources_db as sdb
import tests


def test_sources_db_instance():
    """SourcesDB can list database handles"""

    test_tmp_dir = os.path.join(tests.tmp_dir, "sources_db_test")
    db = sdb.SourcesDB(tests.ArgsMock(workdir=test_tmp_dir))
    handle_list = db.list()
    assert_true(type(handle_list) is list, "handle listing is an actual list")
    assert_true(len(handle_list) > 0, "handle listing is not empty")
    assert_true(db.default in handle_list, "default handle appears in listing")
    assert_true("list" not in handle_list, "`list` must not be an existing handle")
    assert_true("debug" in handle_list, "`debug` handle is required for testing")


def test_sources_db_read():
    """SourcesDB can read databases"""

    test_tmp_dir = os.path.join(tests.tmp_dir, "sources_db_test")
    db = sdb.SourcesDB(tests.ArgsMock(workdir=test_tmp_dir))
    src = db.read("debug")
    assert_true(type(src) is sdb.Sources, "reading yields a Sources object")
    assert_equal(len(src), len(src.rows), "length seems to be correct")
    assert_true("hostname" in list(src[0].keys()), "`hostname` is amongst keys")
    assert_true("rank" in list(src[0].keys()), "`rank` is amongst keys")
    rows = [row for row in src]
    assert_equal(len(rows), len(src), "yields expected number of iterable rows")


def test_sources_db_write_and_override():
    """SourcesDB databases can be written and overridden"""

    test_tmp_dir = os.path.join(tests.tmp_dir, "sources_db_test")

    db = sdb.SourcesDB(tests.ArgsMock(workdir=test_tmp_dir))
    old = db.read("debug")
    old_default = db.default
    override = sdb.Sources("debug", True)
    row_one = {"foo": "bar", "baz": "bang", "boom": "bang"}
    row_two = {"foo": "bar2", "baz": "bang2", "boom": "bang2"}
    override.append(row_one)
    override.append(row_two)
    db.write(override)

    # New SourcesDB instance required to detect overrides
    db = sdb.SourcesDB(tests.ArgsMock(workdir=test_tmp_dir))
    assert_true(os.path.exists(os.path.join(test_tmp_dir, "sources", "debug.csv")), "override file is written")
    assert_equal(db.default, "debug", "overriding the default works")
    assert_not_equal(old_default, db.default, "overridden default actually changes")
    new = db.read("debug")
    assert_equal(len(new), 2, "number of overridden rows is correct")
    assert_true(new[0] == row_one and new[1] == row_two, "new rows are written as expected")
    assert_not_equal(old[0], new[0], "overridden rows actually change")


def test_sources_set_interface():
    """Sources object can be created from and yield sets"""

    # Sets are assumed to contain (rank, hostname) pairs
    src_set = {(1, "mozilla.org"), (2, "mozilla.com"), (3, "addons.mozilla.org")}
    src = sdb.Sources("foo")
    src.from_set(src_set)
    assert_equal(len(src), 3, "database from set has correct length")
    assert_equal(src_set, src.as_set(), "yielded set is identical to the original")
    assert_equal(len(src.as_set(1, 2)), 1, "yielded subset has expected length")


def test_sources_sorting():
    """Sources object can sort its rows by rank"""

    src_set = {(1, "mozilla.org"), (2, "mozilla.com"), (3, "addons.mozilla.org")}
    src = sdb.Sources("foo")
    src.from_set(src_set)
    # Definitely "unsort"
    if int(src.rows[0]["rank"]) < int(src.rows[1]["rank"]):
        src.rows[0], src.rows[1] = src.rows[1], src.rows[0]
    assert_false(int(src.rows[0]["rank"]) < int(src.rows[1]["rank"]) < int(src.rows[2]["rank"]), "list is scrambled")
    src.sort()
    assert_true(int(src.rows[0]["rank"]) < int(src.rows[1]["rank"]) < int(src.rows[2]["rank"]), "sorting works")


def test_sources_chunking():
    """Sources object can be iterated in chunks"""

    src_set = {(1, "mozilla.org"), (2, "mozilla.com"), (3, "addons.mozilla.org"),
               (4, "irc.mozilla.org"), (5, "firefox.com")}
    assert_equal(len(src_set), 5, "hardcoded test set has expected length")
    src = sdb.Sources("foo")
    src.from_set(src_set)
    next_chunk = src.iter_chunks(chunk_start=1, chunk_stop=20, chunk_size=2, min_chunk_size=100)
    assert_equal(src.chunk_size, 100, "chunking respects minimum size setting")
    assert_equal(src.chunk_start, 1, "chunking respects chunk start setting")
    chunk = next_chunk(20)
    assert_equal(len(chunk), 4, "chunks are not larger than remaining data")

    read_set = set()
    next_chunk = src.iter_chunks(chunk_size=2)
    lengths = list()
    for _ in range(10):
        chunk = next_chunk(as_set=True)
        if chunk is None:
            break
        lengths.append(len(chunk))
        read_set.update(chunk)
    assert_equal(lengths, [2, 2, 1], "chunks have expected lengths")
    assert_equal(src_set, read_set, "chunks cover full set")

    next_chunk = src.iter_chunks(chunk_size=10)
    lengths = list()
    lengths.append(len(next_chunk(1)))
    lengths.append(len(next_chunk(2)))
    lengths.append(len(next_chunk(3)))
    assert_true(next_chunk() is None, "after last chunk comes None")
    assert_true(next_chunk() is None, "after last chunk comes None again")
    assert_equal(lengths, [1, 2, 2], "chunks size can be varied on-the-fly")

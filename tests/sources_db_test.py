# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import pytest

import tlscanary.sources_db as sdb
from tests import ArgsMock


@pytest.fixture
def sources_db(tmpdir):
    """A SourcesDB fixture"""
    return sdb.SourcesDB(ArgsMock(workdir=tmpdir))


def test_sources_db_instance(sources_db):
    """SourcesDB can list database handles"""

    handle_list = sources_db.list()
    assert type(handle_list) is list, "handle listing is an actual list"
    assert len(handle_list) > 0, "handle listing is not empty"
    assert sources_db.default in handle_list, "default handle appears in listing"
    assert "list" not in handle_list, "`list` must not be an existing handle"
    assert "debug" in handle_list, "`debug` handle is required for testing"


def test_sources_db_read(sources_db):
    """SourcesDB can read databases"""

    src = sources_db.read("debug")
    assert type(src) is sdb.Sources, "reading yields a Sources object"
    assert len(src) == len(src.rows), "length seems to be correct"
    assert "hostname" in list(src[0].keys()), "`hostname` is amongst keys"
    assert "rank" in list(src[0].keys()), "`rank` is amongst keys"
    rows = [row for row in src]
    assert len(rows) == len(src), "yields expected number of iterable rows"


def test_sources_db_write_and_override(tmpdir):
    """SourcesDB databases can be written and overridden"""

    db = sdb.SourcesDB(ArgsMock(workdir=tmpdir))
    old = db.read("debug")
    old_default = db.default
    override = sdb.Sources("debug", True)
    row_one = {"foo": "bar", "baz": "bang", "boom": "bang"}
    row_two = {"foo": "bar2", "baz": "bang2", "boom": "bang2"}
    override.append(row_one)
    override.append(row_two)
    db.write(override)

    # New SourcesDB instance required to detect overrides
    db = sdb.SourcesDB(ArgsMock(workdir=tmpdir))
    assert os.path.exists(tmpdir.join("sources", "debug.csv")), "override file is written"
    assert db.default == "debug", "overriding the default works"
    assert old_default != db.default, "overridden default actually changes"
    new = db.read("debug")
    assert len(new) == 2, "number of overridden rows is correct"
    assert new[0] == row_one and new[1] == row_two, "new rows are written as expected"
    assert old[0] != new[0], "overridden rows actually change"


def test_sources_set_interface():
    """Sources object can be created from and yield sets"""

    # Sets are assumed to contain (rank, hostname) pairs
    src_set = {(1, "mozilla.org"), (2, "mozilla.com"), (3, "addons.mozilla.org")}
    src = sdb.Sources("foo")
    src.from_set(src_set)
    assert len(src) == 3, "database from set has correct length"
    assert src_set == src.as_set(), "yielded set is identical to the original"
    assert len(src.as_set(1, 2)) == 1, "yielded subset has expected length"


def test_sources_sorting():
    """Sources object can sort its rows by rank"""

    src_set = {(1, "mozilla.org"), (2, "mozilla.com"), (3, "addons.mozilla.org")}
    src = sdb.Sources("foo")
    src.from_set(src_set)
    # Definitely "unsort"
    if int(src.rows[0]["rank"]) < int(src.rows[1]["rank"]):
        src.rows[0], src.rows[1] = src.rows[1], src.rows[0]
    assert not int(src.rows[0]["rank"]) < int(src.rows[1]["rank"]) < int(src.rows[2]["rank"]), "list is scrambled"
    src.sort()
    assert int(src.rows[0]["rank"]) < int(src.rows[1]["rank"]) < int(src.rows[2]["rank"]), "sorting works"


def test_sources_chunking():
    """Sources object can be iterated in chunks"""

    src_set = {(1, "mozilla.org"), (2, "mozilla.com"), (3, "addons.mozilla.org"),
               (4, "irc.mozilla.org"), (5, "firefox.com")}
    assert len(src_set) == 5, "hardcoded test set has expected length"
    src = sdb.Sources("foo")
    src.from_set(src_set)
    next_chunk = src.iter_chunks(chunk_start=1, chunk_stop=20, chunk_size=2, min_chunk_size=100)
    assert src.chunk_size == 100, "chunking respects minimum size setting"
    assert src.chunk_start == 1, "chunking respects chunk start setting"
    chunk = next_chunk(20)
    assert len(chunk) == 4, "chunks are not larger than remaining data"

    read_set = set()
    next_chunk = src.iter_chunks(chunk_size=2)
    lengths = list()
    for _ in range(10):
        chunk = next_chunk(as_set=True)
        if chunk is None:
            break
        lengths.append(len(chunk))
        read_set.update(chunk)
    assert lengths == [2, 2, 1], "chunks have expected lengths"
    assert src_set == read_set, "chunks cover full set"

    next_chunk = src.iter_chunks(chunk_size=10)
    lengths = list()
    lengths.append(len(next_chunk(1)))
    lengths.append(len(next_chunk(2)))
    lengths.append(len(next_chunk(3)))
    assert next_chunk() is None, "after last chunk comes None"
    assert next_chunk() is None, "after last chunk comes None again"
    assert lengths == [1, 2, 2], "chunks size can be varied on-the-fly"

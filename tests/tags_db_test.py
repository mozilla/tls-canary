# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import pytest

import tlscanary.tags_db as tdb
from tests import ArgsMock


@pytest.fixture
def tags_db(tmpdir):
    """A TagsDB fixture"""
    return tdb.TagsDB(ArgsMock(workdir=tmpdir))


def test_tags_db_instance(tags_db):
    """TagsDB can list database handles"""

    assert type(tags_db) is tdb.TagsDB, "TagsDB object fixture has correct type"
    assert len(tags_db.list()) == 0, "Empty TagsDB has no tags"
    assert "notatag" not in tags_db, "TagsDB does not pretend to contain non-existent tag"

    # Test the dict-style interface
    assert type(tags_db["notatag"]) is set and len(tags_db["notatag"]) == 0, "non-existent tag yields empty set"

    assert "newhandleA" not in tags_db["newtag"], "unknown handle is not associated with unknown tag"
    tags_db["newtag"] = "newhandleA"
    assert "newtag" in tags_db, "new tag is added"
    assert "newhandleA" in tags_db["newtag"], "new handle is associated with new tag"
    assert "newhandleB" not in tags_db["newtag"], "unknown handle is not associated with new tag"
    tags_db["newtag"] = "newhandleB"
    assert "newhandleA" in tags_db["newtag"], "old handle is still associated with new tag"
    assert "newhandleB" in tags_db["newtag"], "second handle is associated with existing tag"

    tags_db.remove("newtag", "newhandleB")
    assert "newhandleB" not in tags_db["newtag"], "handle can be disassociated from tag"
    assert "newhandleA" in tags_db["newtag"], "other handles are not affected by disassociation"
    tags_db.remove("newtag", "newhandleA")
    assert "newhandleA" not in tags_db["newtag"], "first handle can be disassociated from tag as well"
    assert "newtag" not in tags_db, "tag that lost all handles is forgotten"

    tags_db["droptag"] = "drophandleA"
    tags_db["droptag"] = "drophandleB"
    tags_db.drop("droptag")
    assert "droptag" not in tags_db, "tags can be dropped entirely"
    assert "drophandleA" not in tags_db["droptag"] and "drophandleB" not in tags_db["droptag"], \
        "associated handles are dropped along tags"


def test_tags_db_persistence(tmpdir):
    """TagsDB databases are persistent on disk"""

    db = tdb.TagsDB(ArgsMock(workdir=tmpdir))
    db["newnewtag"] = "newnewhandleA"  # Any modification should save the DB to disk
    db["newnewtag"] = "newnewhandleB"
    db["newnewtag"] = "newnewhandleC"
    db.remove("newnewtag", "newnewhandleC")

    del db
    assert tmpdir.join("tags.json").exists(), "TaskDB is written to disk"

    db = tdb.TagsDB(ArgsMock(workdir=tmpdir))
    assert "newnewtag" in db, "a TaskDB does not forget about tags"
    assert "newnewhandleA" in db["newnewtag"] and "newnewhandleB" in db["newnewtag"], "a TaskDB does not forget handles"
    assert "newnewhandleC" not in db["newnewtag"], "a TaskDB does not dream about deleted handles"

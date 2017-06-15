# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
from nose.tools import *
import os

import tlscanary.runlog as rl
import tests


def test_runlog_db_instance():
    """RunLogDB can list log handles"""

    test_tmp_dir = os.path.join(tests.tmp_dir, "runlog_instance_test")
    db = rl.RunLogDB(tests.ArgsMock(workdir=test_tmp_dir))
    handle_list = db.list()
    dir_list = db.list_logs()
    assert_true(type(handle_list) is list, "handle listing is a python list")
    assert_true(type(dir_list) is list, "dir listing is a python list")
    assert_equal(len(handle_list), 0, "empty db yields empty handle list")
    assert_equal(len(dir_list), 0, "empty db yields empty dir list")


def test_runlog_db_file_handling():
    """RunLogDB associates handles and directories"""

    test_tmp_dir = os.path.abspath(os.path.join(tests.tmp_dir, "runlog_test"))
    db = rl.RunLogDB(tests.ArgsMock(workdir=test_tmp_dir))

    now = datetime.datetime.utcnow().strftime("%Y-%m-%dZ%H-%M-%S")
    dir_name = os.path.abspath(db.handle_to_dir_name(now))
    assert_true(dir_name.startswith(test_tmp_dir), "log files are stored in the right location")
    handle_name = db.dir_name_to_handle(dir_name)
    assert_equal(now, handle_name, "converting between handles and file names works")


def test_runlog_db_rw():
    """RunlogDB can read and write"""

    test_tmp_dir = os.path.join(tests.tmp_dir, "runlog_db_rw_test")
    db = rl.RunLogDB(tests.ArgsMock(workdir=test_tmp_dir))

    in_db_before = db.list()
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dZ%H-%M-%S")
    assert_true(now not in in_db_before, "database is not cluttered")
    test_data = "hello,test"
    db.write(now, "test", test_data)
    in_db_after = db.list()
    assert_true(now in in_db_after, "written log appears in db listing")
    read_test_data = db.read(now, "test")
    assert_equal(test_data, read_test_data, "read data is same as data")


def test_runlog_rw():
    """RunLog objects can write and read"""

    test_tmp_dir = os.path.join(tests.tmp_dir, "runlog_rw_test")
    db = rl.RunLogDB(tests.ArgsMock(workdir=test_tmp_dir))
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dZ%H-%M-%S")
    log = rl.RunLog(now, "w", db)

    # Write something to log
    log.start(meta={"first_meta": "one"})
    log.log([{"foo": 1}, {"foo": 2}])
    log.log({"foo": 3})
    assert_false(log.has_finished(), "log is not marked `finished` while logging")
    log.stop(meta={"last_meta": "two"})
    assert_true(log.has_finished(), "log is marked `finished` after logging")

    test_log_dir = db.handle_to_dir_name(now)
    assert_true(os.path.isdir(test_log_dir), "log directory is created")

    assert_equal(len(os.listdir(test_log_dir)), 2, "log and meta files are written to disk")

    # Read from log
    log = rl.RunLog(now, "r", db)
    assert_true(log.has_finished(), "completed log is marked as `finished`")
    meta = log.get_meta()
    # Metadata always has "format_revision", "log_lines" and "run_completed" keys
    assert_equal(len(meta.keys()), 5, "log has correct number of meta data")
    log_lines = [line for line in log]
    assert_equal(len(log_lines), 3, "log has correct number of lines")


def test_runlog_integration():
    """RunLog system works as intended"""

    test_tmp_dir = os.path.join(tests.tmp_dir, "runlog_integration_test")
    db = rl.RunLogDB(tests.ArgsMock(workdir=test_tmp_dir))
    log_handles_before = db.list()

    start_meta = {"begin": True}
    stop_meta = {"end": True}
    combined_meta = start_meta
    combined_meta.update(stop_meta)
    log_lines = [{"foo": 1}, {"foo": 2}, {"foo": 3, "nolog": True}]
    log = db.new_log()
    log.start(meta=start_meta, log_filter=lambda x: None if "nolog" in x else x)
    log.log(log_lines)
    log.stop(meta=stop_meta)

    log_handles_after = db.list()
    assert_equal(len(log_handles_after), len(log_handles_before) + 1, "new log is listed")
    log = db.read_log(log_handles_after[-1])
    read_meta = log.get_meta()
    assert_true("log_lines" in read_meta and read_meta["log_lines"] == 2, "has number of lines in metadata")
    has_meta = True
    for k in combined_meta:
        if k not in read_meta or read_meta[k] != combined_meta[k]:
            has_meta = False
            break
    assert_true(has_meta, "log metadata is correct")
    read_lines = [line for line in log]
    assert_equal(len(read_lines), 2, "log has correct number of lines")
    assert_equal(read_lines, log_lines[:2], "log lines have correct content")

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import mock
from nose import SkipTest
from nose.tools import *
from time import sleep

import tests
import tlscanary.xpcshell_worker as xw


@mock.patch('sys.stdout')  # to silence progress bar
def test_xpcshell_worker(mock_sys):
    """XPCShell worker runs and is responsive"""

    # Skip test if there is no app for this platform
    if tests.test_app is None:
        raise SkipTest("XPCShell worker can not be tested on this platform")

    # Spawn a worker.
    w = xw.XPCShellWorker(tests.test_app)
    w.spawn()
    assert_true(w.is_running())

    # Send commands
    w.send(xw.Command("info", id=1))
    w.send(xw.Command("quit", id=2))

    # We need to wait until the reader thread is guaranteed to have run.
    sleep(1)

    # Unfetched results should stay queued even after the worker terminated.
    w.terminate()

    # Get the results
    responses = w.receive()

    assert_equal(len(responses), 2, "XPCShell worker delivers expected number of responses")
    assert_true(type(responses[0]) is xw.Response, "XPCShell worker delivers valid 1st response")
    assert_true(type(responses[1]) is xw.Response, "XPCShell worker delivers valid 2nd response")

    info_response, quit_response = responses

    assert_equal(info_response.id, 1, "Info response has expected ID")
    assert_true(info_response.success, "Info command was successful")
    assert_true("branch" in info_response.result, "Info response contains expected 2nd field")
    assert_equal(info_response.result["branch"], "nightly", "Info response has expected value")

    assert_equal(quit_response.id, 2, "Quit response has expected ID")
    assert_true(info_response.success, "Quit command was successful")

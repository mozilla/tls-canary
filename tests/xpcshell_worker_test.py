# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import pytest
from time import sleep

import tlscanary.tools.xpcshell_worker as xw


def test_xpcshell_worker(nightly_app):
    """XPCShell worker runs and is responsive"""

    # Skip test if there is no app for this platform
    if nightly_app is None:
        pytest.skip("XPCShell worker can not be tested on this platform")

    # Spawn a worker.
    w = xw.XPCShellWorker(nightly_app)
    w.spawn()
    assert w.is_running(), "XPCShell worker is starting"

    # Send commands
    w.send(xw.Command("info", id=1))
    w.send(xw.Command("quit", id=2))

    # We need to wait until the reader thread is guaranteed to have run.
    sleep(1)

    # Unfetched results should stay queued even after the worker terminated.
    w.terminate()

    # Get the results
    responses = w.receive()

    assert len(responses) == 2, "XPCShell worker delivers expected number of responses"
    assert type(responses[0]) is xw.Response, "XPCShell worker delivers valid 1st response"
    assert type(responses[1]) is xw.Response, "XPCShell worker delivers valid 2nd response"

    info_response, quit_response = responses

    assert info_response.id == 1, "Info response has expected ID"
    assert info_response.success, "Info command was successful"
    assert "appConstants" in info_response.result, "Info response contains `appConstants`"
    assert "nssInfo" in info_response.result, "Info response contains `nssInfo`"
    assert info_response.result["appConstants"]["MOZ_UPDATE_CHANNEL"] == "nightly", "Info response has expected value"

    assert quit_response.id == 2, "Quit response has expected ID"
    assert info_response.success, "Quit command was successful"

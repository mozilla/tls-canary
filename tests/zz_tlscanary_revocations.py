# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import glob
import io
import json
import os
import pkg_resources as pkgr
import pytest
import unittest.mock as mock

from tlscanary import main


@pytest.mark.slow
def test_tlscanary_revocations(tmpdir, nightly_archive):
    """TLS Canary detect OneCRL revocations"""

    work_dir = tmpdir.join("workdir")
    revocations_file = pkgr.resource_filename(__name__, "files/revocations_nodigicert.txt")

    # Run a quick regression scan against a revoked DigiCert Root CA
    argv = [
        "--workdir", str(work_dir),
        "regression",
        "-t", nightly_archive,
        "-b", nightly_archive,
        "-x", "2",
        "-s", "digicert",
        "-o", revocations_file
    ]
    ret = main.main(argv)
    assert ret == 0, "regression run finished without error"

    # Check log
    argv = [
        "--workdir", str(work_dir),
        "log",
        "-a", "json",
        "-i", "1"
    ]
    with mock.patch('sys.stdout', new=io.StringIO()) as mock_stdout:
        ret = main.main(argv)
        stdout = mock_stdout.getvalue()
    assert ret == 0, "regression log dump finished without error"
    assert len(stdout) > 0, "regression log dump is not empty"
    log = json.loads(stdout)
    assert type(log) is list, "regression JSON log is list"
    assert len(log) == 1, "there is one log in the dump"
    assert "meta" in log[0] and "data" in log[0], "log has meta and data"
    assert len(log[0]["data"]) > 10, "log contains mostly regressions"

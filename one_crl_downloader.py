# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from distutils.spawn import find_executable
import logging
import os
import subprocess
import sys
from shutil import rmtree

logger = logging.getLogger(__name__)


def get_list(onecrl_env, profile_dir, workdir):
    global logger

    # Find Go binary
    go_bin = find_executable("go")
    if go_bin is None:
        logger.critical("Cannot find Go compiler")
        sys.exit(5)
    logger.debug("Using Go compiler at `%s`" % go_bin)

    # Prepare Go environment within our workdir
    go_path = os.path.join(workdir, "go")
    logger.debug("Using GOPATH `%s`" % go_path)
    go_env = os.environ.copy()
    go_env["GOPATH"] = go_path

    # Install / update oneCRL2RevocationsTxt package
    package = "github.com/mozmark/OneCRL-Tools/oneCRL2RevocationsTxt"
    logger.debug("Installing / updating Go package `%s`" % package)
    if subprocess.call([go_bin, "get", package], env=go_env) != 0:
        logger.critical("Cannot get Go package `%s`" % package)
        sys.exit(5)
    if subprocess.call([go_bin, "install", package], env=go_env) != 0:
        logger.critical("Cannot install Go package `%s`" % package)
        sys.exit(5)

    # Run OneCRL Go binary to retrieve OnceCRL data
    onecrl_bin = os.path.join(go_path, "bin", "oneCRL2RevocationsTxt")
    if not os.path.isfile(onecrl_bin):
        logger.critical("Go package `oneCRL2RevocationsTxt` is missing executable")
        sys.exit(5)
    onecrl_cmd = [onecrl_bin, "--env", onecrl_env]
    logger.debug("Running shell command `%s`" % " ".join(onecrl_cmd))
    try:
        revocations_data = subprocess.check_output(onecrl_cmd, env=go_env)
    except subprocess.CalledProcessError as error:
        logger.critical("Could not fetch revocations data: %s" % error)
        sys.exit(5)

    # oneCRL2RevocationsTxt does not indicate failure, but the result is empty.
    # Can we be sure this can never happen during regular operation?
    # See https://github.com/mozmark/OneCRL-Tools/issues/3
    if len(revocations_data) == 0:
        logger.critical("Revocations data was empty. Likely network failure.")
        sys.exit(5)

    # Write OneCRL data to file in profile directory
    revocations_file = os.path.join(profile_dir, "revocations.txt")
    logger.debug("Writing OneCRL revocations data to `%s`" % revocations_file)
    with open(revocations_file, "w") as f:
        f.write(revocations_data)

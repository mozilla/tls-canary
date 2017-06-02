# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from distutils.spawn import find_executable
import logging
import os
import subprocess
import sys

import cache


logger = logging.getLogger(__name__)


def get_list(onecrl_env, workdir, use_cache=True, cache_timeout=60*60):
    global logger

    dc = cache.DiskCache(os.path.join(workdir, "cache"), cache_timeout, purge=True)
    cache_id = "%s_revocations.txt" % onecrl_env
    if not use_cache:
        # Enforce re-extraction even if cached
        dc.delete(cache_id)
    cache_file = dc[cache_id]

    if cache_id not in dc:

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
        if subprocess.call([go_bin, "get", "-u", package], env=go_env) != 0:
            logger.critical("Cannot get Go package `%s`" % package)
            sys.exit(5)
        if subprocess.call([go_bin, "install", package], env=go_env) != 0:
            logger.critical("Cannot install Go package `%s`" % package)
            sys.exit(5)

        # Run OneCRL Go binary to retrieve OnceCRL data
        if sys.platform == "win32":
            onecrl_bin = os.path.join(go_path, "bin", "oneCRL2RevocationsTxt.exe")
        else:
            onecrl_bin = os.path.join(go_path, "bin", "oneCRL2RevocationsTxt")
        if not os.path.isfile(onecrl_bin):
            logger.critical("Go package `oneCRL2RevocationsTxt` is missing executable")
            sys.exit(5)
        onecrl_cmd = [onecrl_bin, "--onecrlenv", onecrl_env]
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

        # Write OneCRL data to cache
        logger.debug("Caching OneCRL revocations data in `%s`" % cache_file)
        with open(cache_file, "w") as f:
            f.write(revocations_data)

    else:
        logger.warning("Using cached OneCRL revocations data from `%s`" % cache_file)

    return cache_file

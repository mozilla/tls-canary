# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from distutils.spawn import find_executable
import logging
import os
import subprocess
import sys

from . import cache


logger = logging.getLogger(__name__)


_ONE_CRL_TOOLS_GIT_URL = "https://github.com/mozilla/OneCRL-Tools.git"
_ONE_CRL_TOOLS_REPO = "OneCRL-Tools"

# populate_cert_storage creates an LMDB database populated with the contents of the provided
# OneCRL environment (one of either "stage" or "production"). The created database will be
# located at <WORKDIR>/cache/<ONE_CRL_ENV>_cert_storage/security/data.safe.bin. This database
# should in turn be copied to <FIREFOX_PROFILE>/security_state/data.safe.bin.
def populate_cert_storage(onecrl_env, workdir, commit="master", use_cache=True, cache_timeout=60*60):
    global logger

    dc = cache.DiskCache(os.path.join(workdir, "cache"), cache_timeout, purge=True)
    cache_id = "%s_cert_storage" % onecrl_env
    if not use_cache:
        # Enforce re-extraction even if cached
        dc.delete(cache_id)
    if cache_id in dc:
        logger.warning("Using cached OneCRL cert_storage data from `%s`" % dc[cache_id])
        return

    if _ONE_CRL_TOOLS_REPO not in dc:
        subprocess.call(["git", "clone", _ONE_CRL_TOOLS_GIT_URL, dc[_ONE_CRL_TOOLS_REPO]])

    cached_security_state = dc[cache_id]
    os.makedirs(cached_security_state)

    repo_dir = dc[_ONE_CRL_TOOLS_REPO]

    cargo_bin = find_executable("cargo")
    if cargo_bin is None:
        logger.critical("Cannot find Cargo toolchain")
        sys.exit(5)
    logger.debug("Using Cargo toolchain at `%s`" % cargo_bin)

    # Checkout a known-working commit before running
    logger.debug("Checking out commit `%s` in `%s`" % (commit, repo_dir))
    if subprocess.call(["git", "checkout", "-q", commit], cwd=repo_dir) != 0:
        logger.critical("Cannot checkout OneCRL-Tools git commit `%s`" % commit)
        sys.exit(5)
    tool_dir = os.path.join(repo_dir, "one_crl_to_cert_storage")
    # The user may have their global toolchain set to nightly, but we would
    # like if the local use of the toolchain pointed to stable.
    if subprocess.call(["rustup", "override", "set", "--path", tool_dir, "stable"]) != 0:
        logger.critical("Cannot set the working toolchain for `%s` to stable" % tool_dir)
        sys.exit(5)
    # cargo run --manifest-path one_crl_to_cert_storage/Cargo.toml -- --env $onecrl_env --profile $profile_path
    manifest = os.path.join(tool_dir, "Cargo.toml")
    result = subprocess.call([
        # "--" delimits arguments given to Cargo from the arguments given to the built tool.
        "cargo", "run", "--manifest-path", manifest, "--", 
        # arguments for the tool itself
        "--env", onecrl_env, "--profile", cached_security_state])
    if result != 0:
        logger.critical("Cannot populate cert_storage from OneCRL")
        sys.exit(5)
    return os.path.join(cached_security_state, "security_state", "data.safe.bin")
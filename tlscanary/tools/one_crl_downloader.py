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


def get_list(onecrl_env, workdir, commit, use_cache=True, cache_timeout=60*60):
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
        package = "github.com/mozilla/OneCRL-Tools/oneCRL2RevocationsTxt"
        repo_dir = os.path.join(go_path, "src", "github.com", "mozilla", "OneCRL-Tools")
        # If the package has already been downloaded, checkout master, else `go get` will fail
        if os.path.isdir(os.path.join(repo_dir, ".git")):
            logger.debug("Checking out commit `master` in `%s` for update" % repo_dir)
            if subprocess.call(["git", "checkout", "-q", "master"], cwd=repo_dir) != 0:
                logger.critical("Cannot checkout OneCRL-Tools git commit `master`")
                sys.exit(5)
        # `go get` internally uses `git pull`. `-d` prevents installation
        logger.debug("Installing / updating Go package `%s`" % package)
        if subprocess.call([go_bin, "get", "-u", "-d", package], env=go_env) != 0:
            logger.critical("Cannot get Go package `%s`" % package)
            sys.exit(5)
        # Checkout a known-working commit before installation
        logger.debug("Checking out commit `%s` in `%s`" % (commit, repo_dir))
        if subprocess.call(["git", "checkout", "-q", commit], cwd=repo_dir) != 0:
            logger.critical("Cannot checkout OneCRL-Tools git commit `%s`" % commit)
            sys.exit(5)
        # Install package
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
        with open(cache_file, "wb") as f:
            f.write(revocations_data)

    else:
        logger.warning("Using cached OneCRL revocations data from `%s`" % cache_file)

    return cache_file

# populate_cert_storage creates an LMDB database populated with the contents of the provided
# OneCRL environment (one of either "stage" or "production"). The created database will be
# located at <WORKDIR>/cache/<ONE_CRL_ENV>_cert_storage/security/data.safe.bin. This database
# should in turn be copied to <FIREFOX_PROFILE>/security_state/data.safe.bin.
def populate_cert_storage(onecrl_env, workdir, commit, use_cache=True, cache_timeout=60*60):

    # @TODO PATH needs `/.cargo/bin
    global logger

    dc = cache.DiskCache(os.path.join(workdir, "cache"), cache_timeout, purge=True)
    cache_id = "%s_cert_storage" % onecrl_env
    if not use_cache:
        # Enforce re-extraction even if cached
        dc.delete(cache_id)
    if cache_id in dc:
        logger.warning("Using cached OneCRL cert_storage data from `%s`" % cached_security_state)
        return

    cached_security_state = dc[cache_id]
    os.makedirs(cached_security_state)
    # @TODO
    # What should this be? Above, we were essentially relying on the GOPATH as
    # a default place to have a cloned repo.
    repo_dir = "/Users/chris/Documents/Contracting/mozilla/OneCRL-Tools"

    os.putenv("")
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

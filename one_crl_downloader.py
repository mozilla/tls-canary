# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import os
import sys
from shutil import rmtree

logger = logging.getLogger(__name__)


class OneCRLDownloader(object):

    @staticmethod
    def get_list(one_crl_environ, workdir):

        # find go installation and create subdirectories
        locations = os.environ.get("PATH").split(os.pathsep)
        candidates = []
        for location in locations:
            candidate = os.path.join(location, 'go')
            if os.path.isfile(candidate):
                candidates.append(candidate)
        go_orig = candidates[0]
        go_real_path = os.path.realpath(go_orig)
        go_src_path = os.path.normpath(go_real_path+"../../../src")

        src_dir = os.path.join(go_src_path, "github.com")
        tmp_dir = os.path.join(src_dir, "mozmark")
        git_src_path = os.path.join(tmp_dir, "OneCRL-Tools")

        if not os.path.exists(git_src_path):
            logger.info("Downloading OneCRL tools")
            os.mkdir(src_dir)
            os.mkdir(tmp_dir)
            os.mkdir(git_src_path)
            # put OneCRL code into this directory
            git_cmd = "git clone https://github.com/mozmark/OneCRL-Tools %s" % git_src_path
            os.system(git_cmd)

        # obtain OneCRL list and write to disk
        logger.info("Obtaining OneCRL entries from %s and writing to disk " % one_crl_environ)
        one_crl_app = os.path.join(git_src_path, "oneCRL2RevocationsTxt/main.go")
        go_cmd = "go run %s %s > %s/revocations.txt" % (one_crl_app, one_crl_environ, workdir)
        os.system(go_cmd)

        # optional: remove temporary source directory
        # rmtree(src_dir)
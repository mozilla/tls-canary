# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import logging
import os
import pkg_resources as pkgr
import sys

from basemode import BaseMode
import tlscanary.firefox_downloader as fd
import tlscanary.report as report
import tlscanary.sources_db as sdb


logger = logging.getLogger(__name__)


class ScanMode(BaseMode):

    name = "scan"

    def __init__(self, args, module_dir, tmp_dir):
        global logger

        super(ScanMode, self).__init__(args, module_dir, tmp_dir)

        # Define instance attributes for later use
        self.url_set = None
        self.info_uri_set = None
        self.test_profile = None
        self.test_app = None
        self.test_metadata = None
        self.start_time = None

    def setup(self):
        global logger

        # argument validation logic to make sure user has specified only test build
        if self.args.test is None:
            logger.critical('Must specify test build for scan')
            sys.exit(1)
        elif self.args.base is not None:
            logger.debug('Found base build parameter, ignoring')

        # Code paths after this will generate a report, so check
        # whether the report dir is a valid target. Specifically, prevent
        # writing to the module directory.
        module_dir = pkgr.require("tlscanary")[0].location
        if os.path.normcase(os.path.realpath(self.args.reportdir))\
                .startswith(os.path.normcase(os.path.realpath(module_dir))):
            logger.critical("Refusing to write report to module directory. Please set --reportdir")
            sys.exit(1)

        # Compile the set of URLs to test
        db = sdb.SourcesDB(self.args)
        logger.info("Reading `%s` host database" % self.args.source)
        self.url_set = db.read(self.args.source).as_set()
        logger.info("%d URLs in test set" % len(self.url_set))

        # Create custom profile
        self.test_profile = self.make_profile("test_profile")

        # Download app and extract metadata
        logger.info("Starting pass with %d URLs" % len(self.url_set))
        self.test_app = self.get_test_candidate(self.args.test)
        self.test_metadata = self.collect_worker_info(self.test_app)
        logger.info("Testing Firefox %s %s scan run" %
                    (self.test_metadata["appVersion"], self.test_metadata["branch"]))

    def run(self):
        # Perform the scan
        self.start_time = datetime.datetime.now()
        self.info_uri_set = self.run_test(self.test_app, self.url_set, profile=self.test_profile,
                                          prefs=self.args.prefs, get_info=True,
                                          get_certs=True, progress=True, return_only_errors=False)

    def report(self):
        header = {
            "mode": self.args.mode,
            "timestamp": self.start_time.strftime("%Y-%m-%d-%H-%M-%S"),
            "branch": self.test_metadata["branch"].capitalize(),
            "description": "Fx%s %s scan run" % (self.test_metadata["appVersion"], self.test_metadata["branch"]),
            "source": self.args.source,
            "test build url": fd.FirefoxDownloader.get_download_url(self.args.test, self.test_app.platform),
            "test build metadata": "%s, %s" % (self.test_metadata["nssVersion"], self.test_metadata["nsprVersion"]),
            "Total time": "%d minutes" % int(round((datetime.datetime.now() - self.start_time).total_seconds() / 60))
        }
        report.generate(self.args, header, self.info_uri_set, self.start_time, False)

    def teardown(self):
        self.save_profile("test_profile", self.start_time)

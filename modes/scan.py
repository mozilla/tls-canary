# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import logging
import os
import sys

from basemode import BaseMode
import firefox_downloader as fd
import report
import url_store as us


logger = logging.getLogger(__name__)


class ScanMode(BaseMode):

    def __init__(self, args, module_dir, tmp_dir):
        global logger

        super(ScanMode, self).__init__(args, module_dir, tmp_dir)

        # argument validation logic to make sure user has specified only test build
        if args.test is None:
            logger.critical('Must specify test build for scan')
            sys.exit(1)
        elif args.base is not None:
            logger.debug('Found base build parameter, ignoring')


    def setup(self):
        # Compile the set of URLs to test
        self.sources_dir = os.path.join(self.module_dir, 'sources')
        logger.info (self.args)
        urldb = us.URLStore(self.sources_dir, limit=self.args.limit)
        urldb.load(self.args.source)
        self.url_set = set(urldb)
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
        self.info_uri_set = self.run_test(self.test_app, self.url_set, profile=self.test_profile, get_info=True, get_certs=True,
                                     progress=True, return_only_errors=False)
        return self.info_uri_set

    def report(self):
        header = {
            "mode" : self.args.mode,
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


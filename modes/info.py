# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import logging
import os
import sys

from modes.basemode import BaseMode
import firefox_downloader as fd
import report
import url_store as us


logger = logging.getLogger(__name__)


class InfoMode(BaseMode):

    name = "info"

    def __init__(self, args, module_dir, tmp_dir):
        global logger

        super(InfoMode, self).__init__(args, module_dir, tmp_dir)

        # argument validation logic to make sure user has specified only test build
        if args.test is None:
            logger.critical('Must specify test build for info run')
            sys.exit(1)
        elif args.base is not None:
            logger.debug('Found base build parameter, ignoring')

        # Compile the set of URLs to test
        sources_dir = os.path.join(module_dir, 'sources')
        urldb = us.URLStore(sources_dir, limit=args.limit)
        urldb.load(args.source)
        url_set = set(urldb)
        logger.info("%d URLs in test set" % len(url_set))

        # Create custom profile
        test_profile = self.make_profile("test_profile")

        # Download app and extract metadata
        logger.info("Starting pass with %d URLs" % len(url_set))
        test_app = self.get_test_candidate(args.test)
        test_metadata = self.collect_worker_info(test_app)
        logger.info("Testing Firefox %s %s info run" %
                    (test_metadata["appVersion"], test_metadata["branch"]))

        # Perform the info scan
        start_time = datetime.datetime.now()
        info_uri_set = self.run_test(test_app, url_set, profile=test_profile, get_info=True, get_certs=True,
                                     progress=True, return_only_errors=False)

        header = {
            "timestamp": start_time.strftime("%Y-%m-%d-%H-%M-%S"),
            "branch": test_metadata["branch"].capitalize(),
            "description": "Fx%s %s info run" % (test_metadata["appVersion"], test_metadata["branch"]),
            "source": args.source,
            "test build url": fd.FirefoxDownloader.get_download_url(args.test, test_app.platform),
            "test build metadata": "%s, %s" % (test_metadata["nssVersion"], test_metadata["nsprVersion"]),
            "Total time": "%d minutes" % int(round((datetime.datetime.now() - start_time).total_seconds() / 60))
        }

        report.generate(args, header, info_uri_set, start_time, False)
        self.save_profile("test_profile", start_time)
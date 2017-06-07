# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from math import ceil
import datetime
import logging
import os

from basemode import BaseMode
import firefox_downloader as fd
import report
import url_store as us


logger = logging.getLogger(__name__)


class RegressionMode(BaseMode):
    def __init__(self, args, module_dir, tmp_dir):
        global logger

        super(RegressionMode, self).__init__(args, module_dir, tmp_dir)
        # TODO: argument validation logic 

        # Define instance attributes for later use
        self.test_app = None
        self.base_app = None
        self.test_metadata = None
        self.base_metadata = None
        self.test_profile = None
        self.base_profile = None
        self.start_time = None
        self.url_set = None
        self.error_set = None

    def setup(self):
        self.test_app = self.get_test_candidate(self.args.test)
        self.base_app = self.get_test_candidate(self.args.base)

        self.test_metadata = self.collect_worker_info(self.test_app)
        self.base_metadata = self.collect_worker_info(self.base_app)

        # Setup custom profiles
        self.test_profile = self.make_profile("test_profile")
        self.base_profile = self.make_profile("base_profile")

        # Compile the set of URLs to test
        sources_dir = os.path.join(self.module_dir, 'sources')
        urldb = us.URLStore(sources_dir, limit=self.args.limit)
        urldb.load(self.args.source)
        self.url_set = set(urldb)
        logger.info("%d URLs in test set" % len(self.url_set))

    def run(self):
        logger.info("Testing Firefox %s %s against Firefox %s %s" %
                    (self.test_metadata["appVersion"], self.test_metadata["branch"],
                     self.base_metadata["appVersion"], self.base_metadata["branch"]))

        self.start_time = datetime.datetime.now()
        self.error_set = self.run_regression_passes(self.module_dir, self.test_app, self.base_app)

    def report(self):
        header = {
            "mode": self.args.mode,
            "timestamp": self.start_time.strftime("%Y-%m-%d-%H-%M-%S"),
            "branch": self.test_metadata["branch"].capitalize(),
            "description": "Fx%s %s vs Fx%s %s" % (self.test_metadata["appVersion"], self.test_metadata["branch"],
                                                   self.base_metadata["appVersion"], self.base_metadata["branch"]),
            "source": self.args.source,
            "test build url": fd.FirefoxDownloader.get_download_url(self.args.test, self.test_app.platform),
            "release build url": fd.FirefoxDownloader.get_download_url(self.args.base, self.base_app.platform),
            "test build metadata": "%s, %s" % (self.test_metadata["nssVersion"], self.test_metadata["nsprVersion"]),
            "release build metadata": "%s, %s" % (self.base_metadata["nssVersion"], self.base_metadata["nsprVersion"]),
            "Total time": "%d minutes" % int(round((datetime.datetime.now() - self.start_time).total_seconds() / 60))
        }
        report.generate(self.args, header, self.error_set, self.start_time)

    def teardown(self):
        self.save_profile("test_profile", self.start_time)
        self.save_profile("base_profile", self.start_time)

    def run_regression_passes(self, module_dir, test_app, base_app):
        del module_dir, test_app, base_app  # unused parameters
        global logger

        # Compile set of error URLs in three passes 

        # First pass:
        # - Run full test set against the test candidate
        # - Run new error set against baseline candidate
        # - Filter for errors from test candidate but not baseline

        logger.info("Starting first pass with %d URLs" % len(self.url_set))

        test_error_set = self.run_test(self.test_app, self.url_set, profile=self.test_profile, progress=True)
        logger.info("First test candidate pass yielded %d error URLs" % len(test_error_set))
        logger.debug("First test candidate pass errors: %s" % ' '.join(["%d,%s" % (r, u) for r, u in test_error_set]))

        base_error_set = self.run_test(self.base_app, test_error_set, profile=self.base_profile, progress=True)
        logger.info("First baseline candidate pass yielded %d error URLs" % len(base_error_set))
        logger.debug(
            "First baseline candidate pass errors: %s" % ' '.join(["%d,%s" % (r, u) for r, u in base_error_set]))

        error_set = test_error_set.difference(base_error_set)

        # Second pass:
        # - Run error set from first pass against the test candidate
        # - Run new error set against baseline candidate, slower with higher timeout
        # - Filter for errors from test candidate but not baseline

        logger.info("Starting second pass with %d URLs" % len(error_set))

        test_error_set = self.run_test(self.test_app, error_set, profile=self.test_profile,
                                       num_workers=int(ceil(self.args.parallel / 1.414)),
                                       n_per_worker=int(ceil(self.args.requestsperworker / 1.414)))
        logger.info("Second test candidate pass yielded %d error URLs" % len(test_error_set))
        logger.debug("Second test candidate pass errors: %s" % ' '.join(["%d,%s" % (r, u) for r, u in test_error_set]))

        base_error_set = self.run_test(self.base_app, test_error_set, profile=self.base_profile)
        logger.info("Second baseline candidate pass yielded %d error URLs" % len(base_error_set))
        logger.debug(
            "Second baseline candidate pass errors: %s" % ' '.join(["%d,%s" % (r, u) for r, u in base_error_set]))

        error_set = test_error_set.difference(base_error_set)

        # Third pass:
        # - Run error set from first pass against the test candidate with less workers
        # - Run new error set against baseline candidate with less workers
        # - Filter for errors from test candidate but not baseline

        logger.info("Starting third pass with %d URLs" % len(error_set))

        test_error_set = self.run_test(self.test_app, error_set, profile=self.test_profile, num_workers=2,
                                       n_per_worker=10)
        logger.info("Third test candidate pass yielded %d error URLs" % len(test_error_set))
        logger.debug("Third test candidate pass errors: %s" % ' '.join(["%d,%s" % (r, u) for r, u in test_error_set]))

        base_error_set = self.run_test(self.base_app, test_error_set, profile=self.base_profile, num_workers=2,
                                       n_per_worker=10)
        logger.info("Third baseline candidate pass yielded %d error URLs" % len(base_error_set))
        logger.debug(
            "Third baseline candidate pass errors: %s" % ' '.join(["%d,%s" % (r, u) for r, u in base_error_set]))

        error_set = test_error_set.difference(base_error_set)
        logger.info("Error set is %d URLs: %s" % (len(error_set), ' '.join(["%d,%s" % (r, u) for r, u in error_set])))

        # Fourth pass, information extraction:
        # - Run error set from third pass against the test candidate with less workers
        # - Have workers return extra runtime information, including certificates

        logger.info("Extracting runtime information from %d URLs" % (len(error_set)))
        final_error_set = self.run_test(self.test_app, error_set, profile=self.test_profile, num_workers=1,
                                        n_per_worker=10, get_info=True, get_certs=True)

        # Final set includes additional result data, so filter that out before comparison
        stripped_final_set = set()

        for rank, host, data in final_error_set:
            stripped_final_set.add((rank, host))

        if stripped_final_set != error_set:
            diff_set = error_set.difference(stripped_final_set)
            logger.warning("Domains dropped out of final error set: %s" % diff_set)

        return final_error_set

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import logging
import sys

from regression import RegressionMode
import tlscanary.firefox_downloader as fd
import tlscanary.report as report


logger = logging.getLogger(__name__)


class PerformanceMode(RegressionMode):

    name = "performance"

    def __init__(self, args, module_dir, tmp_dir):
        global logger

        super(PerformanceMode, self).__init__(args, module_dir, tmp_dir)

        # Define instance attributes for later use
        self.start_time = None
        self.test_uri_set = None
        self.base_uri_set = None
        self.total_change = None
        self.error_set = None

    def setup(self):
        # Additional argument validation for hard-coded limits,
        # because 1000 URIs x 20 scans per URI x 2 builds is a lot of data
        # will investigate upper limit later
        if self.args.limit > 1000:
            logger.critical("Limiting performance test to 1000 URIs for now")
            sys.exit(1)
        if self.args.scans > 20:
            logger.critical("Limiting performance test to 20 scans per URI list for now")
            sys.exit(1)
        super(PerformanceMode, self).setup()



    def run(self):
        # Perform the scan
        self.start_time = datetime.datetime.now()
        test_uri_sets = []
        base_uri_sets = []

        self.total_change = 0
        test_speed_aggregate = 0
        base_speed_aggregate = 0

        for i in xrange(0, self.args.scans):
            test_uri_sets.append(self.run_test(self.test_app, self.url_set, profile=self.test_profile,
                                               prefs=self.args.prefs_test, get_info=True, get_certs=True,
                                               progress=True, return_only_errors=False))

            base_uri_sets.append(self.run_test(self.base_app, self.url_set, profile=self.base_profile,
                                               prefs=self.args.prefs_base, get_info=True, get_certs=True,
                                               progress=True, return_only_errors=False))

        # extract connection speed from all scans
        test_connections_all = []
        for uri_set in test_uri_sets:
            test_connections_all.append(self.extract_connection_speed(uri_set))

        base_connections_all = []
        for uri_set in base_uri_sets:
            base_connections_all.append(self.extract_connection_speed(uri_set))

        # collapse all scan data into one URI set
        self.consolidate_connection_speed_info(test_uri_sets[0], test_connections_all)
        self.consolidate_connection_speed_info(base_uri_sets[0], base_connections_all)

        # the first URI set becomes our primary set
        self.test_uri_set = test_uri_sets[0]
        self.base_uri_set = base_uri_sets[0]

        # new values to be inserted into response
        for test_record in self.test_uri_set:
            base_record = [d for d in self.base_uri_set if d[1] == test_record[1]][0]
            test_response_time = float(test_record[2].response.connection_speed_average)
            base_response_time = float(base_record[2].response.connection_speed_average)
            test_speed_aggregate += test_response_time
            base_speed_aggregate += base_response_time
            pct_change = float((test_response_time - base_response_time) / base_response_time) * 100
            test_record[2].response.connection_speed_change = int(pct_change)
            # save the speed samples of the base record to the test record for now,
            # in case we decide we want to include this in the report later
            test_record[2].response.connection_speed_base_samples = base_record[2].response.connection_speed_samples

        self.total_change = float((test_speed_aggregate - base_speed_aggregate) / base_speed_aggregate) * 100
        self.error_set = self.test_uri_set

    @staticmethod
    def extract_connection_speed(uri_set):
        new_set = []
        for record in uri_set:
            new_set.append([
                record[0],  # URI rank
                record[2].response.response_time - record[2].response.command_time  # connection speed
            ])
        return new_set

    def consolidate_connection_speed_info(self, uri_set, connection_sets):
        for record in uri_set:
            temp_speeds = []
            speed_aggregate = 0
            for connection_set in connection_sets:
                speed = [d for d in connection_set if d[0] == record[0]][0][1]
                speed_aggregate += speed
                temp_speeds.append(speed)
            record[2].response.connection_speed_average = speed_aggregate / self.args.scans
            record[2].response.connection_speed_samples = str(temp_speeds).strip('[]')

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
            "Total time": "%d minutes" % int(round((datetime.datetime.now() - self.start_time).total_seconds() / 60)),
            "Total percent speed change": "%s" % int(self.total_change)
        }
        # For now, do not update runs log, as this is not a regression test.
        #
        # We will change the reporting UI later to accomodate the display
        # of all types of test modes.
        report.generate(self.args, header, self.error_set, self.start_time, False)

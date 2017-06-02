# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import logging
import os
import sys

from basemode import BaseMode
from regression import RegressionMode
from scan import ScanMode
import firefox_downloader as fd
import report
import url_store as us

import operator

logger = logging.getLogger(__name__)


class PerformanceMode(RegressionMode):

    def __init__(self, args, module_dir, tmp_dir):
        global logger

        super(PerformanceMode, self).__init__(args, module_dir, tmp_dir)

        # TBD: argument validation logic to make sure user has specified two builds, etc.

        # TBD: This whole class will inherit from regression and override run method only



    def run(self):
        # Perform the scan
        self.start_time = datetime.datetime.now()
        test_sets = []
        base_sets = []

        for i in range (1,10):
            test_sets.append (self.run_test(self.test_app, self.url_set, profile=self.test_profile, get_info=True, get_certs=True,
                                     progress=True, return_only_errors=False) )

            base_sets.append (self.run_test(self.base_app, self.url_set, profile=self.base_profile, get_info=True, get_certs=True,
                                     progress=True, return_only_errors=False))


        self.test_uri_set = test_sets[0]
        self.base_uri_set = base_sets[0]

        # logic to parse connection speed and generate JSON
        # look up site rank in test set and index that out of base set to obtain record

        # temp

        #new_set = sorted (self.test_uri_set, key=operator.itemgetter(0))
        # scan_result.response.response_time - scan_result.response.command_time

        for test_record in self.test_uri_set:
            base_record = [d for d in self.base_uri_set if d[1] == test_record[1]][0]
            test_response_time = float (test_record[2].response.response_time - test_record[2].response.command_time)
            base_response_time = float (base_record[2].response.response_time - base_record[2].response.command_time)
            # check
            logger.info("test time %s, %s ", test_response_time, test_record[1])
            logger.info("base time %s, %s ", base_response_time, base_record[1])
            pct_change = float ((test_response_time - base_response_time) / base_response_time ) * 100
            test_record[2].response.response_time_change = int(pct_change)
            logger.info ("%s percent change for test build", int (pct_change))
            # 300 - 400 (-100/300 = -33%)
            #

            #logger.info (report.collect_scan_info(item[2])['site_info']['connectionSpeed'])

        # TBD: do not update main runs.txt file w/o adding more metadata

        # temp
        self.error_set = self.test_uri_set


    def report(self):
        header = {
            "mode" : self.args.mode,
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

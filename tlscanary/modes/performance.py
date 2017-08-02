# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import json
import logging
import mock
import pkg_resources as pkgr
import sys
import StringIO
import tlscanary.runlog as rl

from log import LogMode
from regression import RegressionMode
from scan import ScanMode

logger = logging.getLogger(__name__)


class PerformanceMode(RegressionMode):

    # TODO:
    # - revisit argument validation and limits
    # - create custom arguments object instead of passing around default
    # - should 'connection_speeds' be renamed 'connection_speeds_test'?
    # - review logging, enhance where needed
    # - test large values on AWS

    name = "performance"
    help = "Run a performance regression test on two Firefox builds"

    def __init__(self, args, module_dir, tmp_dir):
        global logger

        super(PerformanceMode, self).__init__(args, module_dir, tmp_dir)
        # Define instance attributes for later use
        self.start_time = None
        self.total_change = None
        self.temp_hosts = None

    def setup(self):
        # Additional argument validation for hard-coded limits,
        # because 1000 URIs x 20 scans per URI x 2 builds is a lot of data
        # will investigate upper limit later
        if self.args.limit > 1000:
            logger.warning("Limiting performance tests to 1000 hosts.")
            self.args.limit = 1000
        if self.args.scans > 50:
            logger.critical("Limiting performance test to 50 scans per URI list for now")
            sys.exit(1)
        super(PerformanceMode, self).setup()

    def run(self):

        # why do we need this? not used anywhere AFAICT
        self.start_time = datetime.datetime.now()

        meta = {
            "tlscanary_version": pkgr.require("tlscanary")[0].version,
            "mode": self.name,
            "args": vars(self.args),
            "argv": sys.argv,
            "test_metadata": self.test_metadata,
            "base_metadata": self.base_metadata,
            "run_start_time": datetime.datetime.utcnow().isoformat()
        }

        rldb = rl.RunLogDB(self.args)
        log = rldb.new_log()
        log.start(meta=meta)

        # TODO:
        # construct a custom run_args object that will be
        # passed to each test mode, instead of just reusing ours

        argv = self.args
        test_build = self.args.test
        base_build = self.args.base
        self.temp_hosts = []

        initialize = True
        test_aggregate = 0
        base_aggregate = 0

        # Scans for both builds are interleaved,
        # to try to reduce biased results caused by
        # changing network conditions
        for perf_scan in xrange(0, argv.scans):
            logging.info("Starting performance scan %s out of %s" % (perf_scan+1, argv.scans))

            argv.test = test_build
            s = ScanMode(argv, self.module_dir, self.tmp_dir)
            s.setup()
            s.run()

            # After the very first scan run, we want to capture
            # that and use it as our base log, in which
            # we will also hold our speed samples
            if initialize:
                base_log = self.get_log_to_json(argv)
                base_host_list = sorted(base_log["data"], key=lambda x: x["rank"])
                self.temp_hosts = base_host_list
                for i in xrange(0, argv.limit):
                    self.temp_hosts[i]["connection_speeds"] = []
                    self.temp_hosts[i]["connection_speeds_base"] = []
                    initialize = False

            #self.process_scan(argv, "connection_speeds")

            argv.test = base_build
            s = ScanMode(argv, self.module_dir, self.tmp_dir)
            s.setup()
            s.run()
            #self.process_scan(argv, "connection_speeds_base")

        for perf_scan in xrange(0, argv.scans):
            self.process_scan(argv, "connection_speeds_base")
            self.process_scan(argv, "connection_speeds")

        # Sort sample arrays and extract average, median
        for i in xrange(0, argv.limit):
            current_host = self.temp_hosts[i]
            test_average = self.calculate_average_speed(current_host["connection_speeds"])
            base_average = self.calculate_average_speed(current_host["connection_speeds_base"])
            current_host["connection_speed_change_average"] = self.calculate_speed_change(test_average, base_average)

            test_aggregate += test_average
            base_aggregate += base_average

            test_median = self.calculate_median_speed(current_host["connection_speeds"])
            base_median = self.calculate_median_speed(current_host["connection_speeds_base"])
            current_host["connection_speed_change_median"] = self.calculate_speed_change(test_median, base_median)

        # Tally overall performance of test vs release
        self.total_change = self.calculate_speed_change(test_aggregate, base_aggregate)

        for result in self.temp_hosts:
            log.log(result)

        meta["run_finish_time"] = datetime.datetime.utcnow().isoformat()
        meta["performance_change"] = self.total_change
        self.save_profile(self.test_profile, "test_profile", log)
        self.save_profile(self.base_profile, "base_profile", log)
        log.stop(meta=meta)

        # this will go away post-development
        self.temp_debug_output()

    # temporary debugging function
    def temp_debug_output(self):
        logging.info("Total change: %s" % self.total_change)
        for i in xrange (0,3):
            logging.info("Host: %s " % self.temp_hosts[i]["host"])
            logging.info("Average change: %s " % self.temp_hosts[i]["connection_speed_change_average"])
            logging.info("Median change: %s " % self.temp_hosts[i]["connection_speed_change_median"])
            logging.info(self.temp_hosts[i]["connection_speeds"])
            logging.info(self.temp_hosts[i]["connection_speeds_base"])

    @staticmethod
    def calculate_average_speed(sample_list):
        num_samples = len(sample_list)
        running_total = 0
        for i in xrange(0, num_samples):
            running_total += sample_list[i]
        return float(running_total / num_samples)

    @staticmethod
    def calculate_median_speed(sample_list):
        sample_list.sort()
        num_samples = len(sample_list)
        middle = num_samples/2
        if num_samples % 2 == 1:
            median = sample_list[middle]
        else:
            median = (sample_list[middle] + sample_list[middle-1]) / 2
        return float(median)

    @staticmethod
    def calculate_speed_change(a, b):
        change = (float(a - b) / b) * 100
        format_to_two_decimals = float('%.2f' % change)
        return format_to_two_decimals

    def delete_last_log(self):
        argv = self.args
        argv.action = "delete"
        argv.really = True
        argv.include = ['1']
        argv.exclude = []
        log_delete = LogMode(argv, self.module_dir, self.tmp_dir)
        log_delete.setup()
        log_delete.run()

    def extract_connection_speed(self, host_list, array_name):
        for j in xrange(0, self.args.limit):
            connection_speed = host_list[j]["response"]["response_time"] - host_list[j]["response"]["command_time"]
            self.temp_hosts[j][array_name].append(
                connection_speed
            )

    def get_log_to_json(self, argv):
        with mock.patch('sys.stdout', new=StringIO.StringIO()) as mock_stdout:
            argv.action = "json"
            argv.include = ['1']
            argv.exclude = []
            scan_run = LogMode(argv, self.module_dir, self.tmp_dir)
            scan_run.setup()
            scan_run.run()
            stdout = mock_stdout.getvalue()
        return json.loads(stdout)[0]

    def process_scan(self, argv, array_name):
        current_log = self.get_log_to_json(argv)
        host_list = sorted(current_log["data"], key=lambda x: x["rank"])
        self.extract_connection_speed(host_list, array_name)
        self.delete_last_log()

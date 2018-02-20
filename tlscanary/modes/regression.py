# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import logging
import pkg_resources as pkgr
import sys

from basemode import BaseMode
import tlscanary.progress as pr
import tlscanary.runlog as rl
import tlscanary.sources_db as sdb

logger = logging.getLogger(__name__)


class RegressionMode(BaseMode):
    name = "regression"
    help = "Run a TLS regression test on two Firefox versions"

    def __init__(self, args, module_dir, tmp_dir):
        global logger

        super(RegressionMode, self).__init__(args, module_dir, tmp_dir)

        # Define instance attributes for later use
        self.start_time = None
        self.test_app = None
        self.base_app = None
        self.test_metadata = None
        self.base_metadata = None
        self.test_profile = None
        self.base_profile = None
        self.altered_profile = None
        self.sources = None
        self.revoked_source = None
        self.custom_ocsp_pref = None

    def one_crl_sanity_check(self):
        global logger

        # Query host(s) with a known revoked cert and examine the results
        # These hosts must be revoked via OCSP and/or OneCRL
        db = sdb.SourcesDB(self.args)
        self.revoked_source = db.read("revoked")
        logger.debug("%d host(s) in revoked test set" % len(self.revoked_source))
        next_chunk = self.revoked_source.iter_chunks(chunk_size=1/50, min_chunk_size=1000)
        host_set_chunk = next_chunk(as_set=True)

        # Note: turn off OCSP for this test, to factor out that mechanism
        self.custom_ocsp_pref = ["security.OCSP.enabled;0"]

        # First, use the test build and profile as-is
        # This should return errors, which means OneCRL is working
        test_result = self.run_test(self.test_app, url_list=host_set_chunk, profile=self.test_profile,
                                    prefs=self.custom_ocsp_pref, num_workers=1, n_per_worker=1)

        # Second, use the test build with a profile that is missing OneCRL entries
        # This should NOT return errors, which means we've turned off protection
        self.altered_profile = self.make_profile("altered_profile", "none")

        base_result = self.run_test(self.test_app, url_list=host_set_chunk, profile=self.altered_profile,
                                    prefs=self.custom_ocsp_pref, num_workers=1, n_per_worker=1)

        logger.debug("Length of first OneCRL check, with revocation: %d" % len(test_result))
        logger.debug("Length of second OneCRL check, without revocation: %d" % len(base_result))

        # If our list of revoked sites are all blocked, and we can verify
        # that they can be unblocked, this confirms that OneCRL is working
        if len(test_result) == len(self.revoked_source) and len(base_result) == 0:
            return True
        else:
            return False

    def setup(self):
        global logger

        # Argument validation logic
        # Make sure user has test build
        if self.args.test is None:
            logger.critical("Must specify test build for regression testing")
            sys.exit(5)
        elif self.args.base is None:
            logger.critical("Must specify base build for regression testing")
            sys.exit(5)

        if self.args.scans < 2:
            logger.critical("Must specify minimum of 2 scans for regression testing")
            sys.exit(5)

        if self.args.prefs is not None:
            if self.args.prefs_test is not None or self.args.prefs_base is not None:
                logger.warning("Detected both global prefs and individual build prefs.")

        self.test_app = self.get_test_candidate(self.args.test)
        self.base_app = self.get_test_candidate(self.args.base)

        self.test_metadata = self.collect_worker_info(self.test_app)
        self.base_metadata = self.collect_worker_info(self.base_app)

        # Setup custom profiles
        self.test_profile = self.make_profile("test_profile", self.args.onecrl)
        self.base_profile = self.make_profile("base_profile", "production")

        # Compile the set of hosts to test
        db = sdb.SourcesDB(self.args)
        logger.info("Reading `%s` host database" % self.args.source)
        self.sources = db.read(self.args.source)
        logger.info("%d hosts in test set" % len(self.sources))

        # Sanity check for OneCRL - if it fails, abort run
        if not self.one_crl_sanity_check():
            logger.critical("OneCRL sanity check failed, aborting run")
            sys.exit(5)

    def run(self):
        global logger

        logger.info("Testing Firefox %s %s against Firefox %s %s" %
                    (self.test_metadata["app_version"], self.test_metadata["branch"],
                     self.base_metadata["app_version"], self.base_metadata["branch"]))

        self.start_time = datetime.datetime.now()

        meta = {
            "tlscanary_version": pkgr.require("tlscanary")[0].version,
            "mode": self.name,
            "args": vars(self.args),
            "argv": sys.argv,
            "sources_size": len(self.sources),
            "test_metadata": self.test_metadata,
            "base_metadata": self.base_metadata,
            "run_start_time": datetime.datetime.utcnow().isoformat()
        }

        rldb = rl.RunLogDB(self.args)
        log = rldb.new_log()
        log.start(meta=meta)
        progress = pr.ProgressTracker(total=len(self.sources), unit="hosts", average=30*60.0)

        limit = len(self.sources) if self.args.limit is None else self.args.limit

        # Split work into 50 chunks to conserve memory, but make no chunk smaller than 1000 hosts
        next_chunk = self.sources.iter_chunks(chunk_size=limit/50, min_chunk_size=1000)

        try:
            while True:
                host_set_chunk = next_chunk(as_set=True)
                if host_set_chunk is None:
                    break

                logger.info("Starting regression run on chunk of %d hosts" % len(host_set_chunk))

                error_set = self.run_regression_passes(host_set_chunk, report_completed=progress.log_completed,
                                                       report_overhead=progress.log_overhead)
                # Log progress per chunk
                logger.info("Progress: %s" % str(progress))

                # Commit results to log
                for rank, host, result in error_set:
                    log.log(result.as_dict())

        except KeyboardInterrupt:
            logger.critical("Ctrl-C received")
            progress.stop_reporting()
            raise KeyboardInterrupt

        finally:
            progress.stop_reporting()

        meta["run_finish_time"] = datetime.datetime.utcnow().isoformat()
        self.save_profile(self.test_profile, "test_profile", log)
        self.save_profile(self.base_profile, "base_profile", log)
        self.save_profile(self.altered_profile, "altered_profile", log)
        log.stop(meta=meta)

    def run_regression_passes(self, host_set, report_completed=None, report_overhead=None):
        global logger
        # Compile set of error hosts in multiple scans

        # Each scan:
        # - Runs full test set against the test candidate
        # - Runs new error set against baseline candidate
        # - Take any remaining errors and repeat the above steps

        current_host_set = host_set
        num_workers = self.args.parallel
        requests_per_worker = self.args.requestsperworker
        timeout = self.args.timeout
        max_timeout = self.args.max_timeout

        for current_scan in xrange(1, self.args.scans + 1):

            # Specify different callback only for initial test scan
            if current_scan == 1:
                report_callback_value = report_completed
            else:
                report_callback_value = report_overhead

            # Actual test running for both builds
            test_error_set = self.run_test(self.test_app, current_host_set, profile=self.test_profile,
                                           prefs=self.args.prefs_test, num_workers=num_workers,
                                           n_per_worker=requests_per_worker, timeout=timeout,
                                           report_callback=report_callback_value)
            logger.info("Scan #%d with test candidate yielded %d error hosts"
                        % (current_scan, len(test_error_set)))
            logger.debug("Scan #%d test candidate errors: %s"
                         % (current_scan, ' '.join(["%d,%s" % (r, u) for r, u in test_error_set])))
            base_error_set = self.run_test(self.base_app, test_error_set, profile=self.base_profile,
                                           prefs=self.args.prefs_base, num_workers=num_workers,
                                           n_per_worker=requests_per_worker, timeout=timeout,
                                           report_callback=report_overhead)
            logger.info("Scan #%d with baseline candidate yielded %d error hosts"
                        % (current_scan, len(base_error_set)))
            logger.debug("Scan #%d baseline candidate errors: %s"
                         % (current_scan, ' '.join(["%d,%s" % (r, u) for r, u in base_error_set])))

            current_host_set = test_error_set.difference(base_error_set)

            # If no errors, no need to keep scanning
            if len(current_host_set) == 0:
                break
            else:
                # Slow down number of workers and scans with each pass
                # to make results more precise
                num_workers = max(1, int(num_workers * 0.75))
                requests_per_worker = max(1, int(requests_per_worker * 0.75))
                timeout = min(max_timeout, timeout * 1.25)

        last_error_set = current_host_set

        # Final pass, information extraction only:
        # - Run error set from previous pass against the test candidate with minimal workers, requests
        # - Have workers return extra runtime information, including certificates

        logger.debug("Extracting runtime information from %d hosts" % (len(last_error_set)))
        final_error_set = self.run_test(self.test_app, last_error_set, profile=self.test_profile,
                                        prefs=self.args.prefs_test, num_workers=1, n_per_worker=1,
                                        get_info=True, get_certs=(not self.args.remove_certs),
                                        report_callback=report_overhead)

        if len(final_error_set) > 0:
            logger.warning("%d potential regressions found: %s"
                           % (len(final_error_set), ' '.join(["%d,%s" % (r, u) for r, u, d in final_error_set])))

        # Find out if the information extraction pass changed the results
        if self.args.debug:
            # Final set includes additional result data, so filter that out before comparison
            stripped_final_set = set()

            for rank, host, data in final_error_set:
                stripped_final_set.add((rank, host))

            if stripped_final_set != last_error_set:
                diff_set = last_error_set.difference(stripped_final_set)
                logger.debug("Number of hosts dropped out of final error set: %d" % len(diff_set))
                logger.debug(diff_set)

        return final_error_set

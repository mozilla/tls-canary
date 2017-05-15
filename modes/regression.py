# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.



from math import ceil
import coloredlogs
import datetime
import json
import logging
import os
import sys



from basemode import BaseMode
import firefox_downloader as fd
import report
import url_store as us


logger = logging.getLogger(__name__)


class RegressionMode (BaseMode):

	def __init__(self, args, module_dir, tmp_dir):
		global logger

		super(RegressionMode,self).__init__(args, module_dir, tmp_dir)

		# TODO: argument validation logic 

		test_app = super(RegressionMode,self).get_test_candidate(args, args.test)
		base_app = super(RegressionMode,self).get_test_candidate(args, args.base)

		test_metadata = super(RegressionMode,self).collect_worker_info(test_app)
		base_metadata = super(RegressionMode,self).collect_worker_info(base_app)
    	
		logger.info("Testing Firefox %s %s against Firefox %s %s" %
		            (test_metadata["appVersion"], test_metadata["branch"],
		             base_metadata["appVersion"], base_metadata["branch"]))

		start_time = datetime.datetime.now()
		error_set = self.run_regression_passes(args, module_dir, test_app, base_app)

		header = {
		    "timestamp": start_time.strftime("%Y-%m-%d-%H-%M-%S"),
		    "branch": test_metadata["branch"].capitalize(),
		    "description": "Fx%s %s vs Fx%s %s" % (test_metadata["appVersion"], test_metadata["branch"],
		                                           base_metadata["appVersion"], base_metadata["branch"]),
		    "source": args.source,
		    "test build url": fd.FirefoxDownloader.get_download_url(args.test, test_app.platform),
		    "release build url": fd.FirefoxDownloader.get_download_url(args.base, base_app.platform),
		    "test build metadata": "%s, %s" % (test_metadata["nssVersion"], test_metadata["nsprVersion"]),
		    "release build metadata": "%s, %s" % (base_metadata["nssVersion"], base_metadata["nsprVersion"]),
		    "Total time": "%d minutes" % int(round((datetime.datetime.now() - start_time).total_seconds() / 60))
		}

		report.generate(args, header, error_set, start_time)
		super(RegressionMode,self).save_profile(args, "test_profile", start_time)
		super(RegressionMode,self).save_profile(args, "base_profile", start_time)


	def run_regression_passes(self, args, module_dir, test_app, base_app):
		global logger
		sources_dir = os.path.join(module_dir, 'sources')

		# Compile the set of URLs to test
	    
		urldb = us.URLStore(sources_dir, limit=args.limit)
		urldb.load(args.source)
		url_set = set(urldb)
		logger.info("%d URLs in test set" % len(url_set))

		# Setup custom profiles
		#test_profile, base_profile, _ = make_profiles(args)
		test_profile = super(RegressionMode,self).make_profile(args, "test_profile")
		base_profile = super(RegressionMode,self).make_profile(args, "base_profile")

		# Compile set of error URLs in three passes	

		# First pass:
		# - Run full test set against the test candidate
		# - Run new error set against baseline candidate
		# - Filter for errors from test candidate but not baseline

		logger.info("Starting first pass with %d URLs" % len(url_set))

		test_error_set = super(RegressionMode,self).run_test(test_app, url_set, args, profile=test_profile, progress=True)
		logger.info("First test candidate pass yielded %d error URLs" % len(test_error_set))
		logger.debug("First test candidate pass errors: %s" % ' '.join(["%d,%s" % (r, u) for r, u in test_error_set]))

		base_error_set = super(RegressionMode,self).run_test(base_app, test_error_set, args, profile=base_profile, progress=True)
		logger.info("First baseline candidate pass yielded %d error URLs" % len(base_error_set))
		logger.debug("First baseline candidate pass errors: %s" % ' '.join(["%d,%s" % (r, u) for r, u in base_error_set]))

		error_set = test_error_set.difference(base_error_set)

	    # Second pass:
	    # - Run error set from first pass against the test candidate
	    # - Run new error set against baseline candidate, slower with higher timeout
	    # - Filter for errors from test candidate but not baseline

		logger.info("Starting second pass with %d URLs" % len(error_set))

		test_error_set = super(RegressionMode,self).run_test(test_app, error_set, args, profile=test_profile,
	                              num_workers=int(ceil(args.parallel/1.414)),
	                              n_per_worker=int(ceil(args.requestsperworker/1.414)))
		logger.info("Second test candidate pass yielded %d error URLs" % len(test_error_set))
		logger.debug("Second test candidate pass errors: %s" % ' '.join(["%d,%s" % (r, u) for r, u in test_error_set]))

		base_error_set = super(RegressionMode,self).run_test(base_app, test_error_set, args, profile=base_profile)
		logger.info("Second baseline candidate pass yielded %d error URLs" % len(base_error_set))
		logger.debug("Second baseline candidate pass errors: %s" % ' '.join(["%d,%s" % (r, u) for r, u in base_error_set]))

		error_set = test_error_set.difference(base_error_set)

	    # Third pass:
	    # - Run error set from first pass against the test candidate with less workers
	    # - Run new error set against baseline candidate with less workers
	    # - Filter for errors from test candidate but not baseline

		logger.info("Starting third pass with %d URLs" % len(error_set))

		test_error_set = super(RegressionMode,self).run_test(test_app, error_set, args, profile=test_profile, num_workers=2, n_per_worker=10)
		logger.info("Third test candidate pass yielded %d error URLs" % len(test_error_set))
		logger.debug("Third test candidate pass errors: %s" % ' '.join(["%d,%s" % (r, u) for r, u in test_error_set]))

		base_error_set = super(RegressionMode,self).run_test(base_app, test_error_set, args, profile=base_profile, num_workers=2, n_per_worker=10)
		logger.info("Third baseline candidate pass yielded %d error URLs" % len(base_error_set))
		logger.debug("Third baseline candidate pass errors: %s" % ' '.join(["%d,%s" % (r, u) for r, u in base_error_set]))

		error_set = test_error_set.difference(base_error_set)
		logger.info("Error set is %d URLs: %s" % (len(error_set), ' '.join(["%d,%s" % (r, u) for r, u in error_set])))

	    # Fourth pass, information extraction:
	    # - Run error set from third pass against the test candidate with less workers
	    # - Have workers return extra runtime information, including certificates

		logger.info("Extracting runtime information from %d URLs" % (len(error_set)))
		final_error_set = super(RegressionMode,self).run_test(test_app, error_set, args, profile=test_profile, num_workers=1,
	                               n_per_worker=10, get_info=True, get_certs=True)

	    # Final set includes additional result data, so filter that out before comparison
		stripped_final_set = set()

		for rank, host, data in final_error_set:
			stripped_final_set.add((rank, host))

		if stripped_final_set != error_set:
			diff_set = error_set.difference(stripped_final_set)
			logger.warning("Domains dropped out of final error set: %s" % diff_set)

		return final_error_set

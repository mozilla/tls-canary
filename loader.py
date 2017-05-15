# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.


import logging
import sys

from modes.info import InfoMode as info
from modes.regression import RegressionMode as regression

# Eventualy import other future tests, like 
# pin, performance

logger = logging.getLogger(__name__)


def run (args, module_dir, tmp_dir):
    # determine which test to run
    if args.mode == 'regression':
    	regression(args, module_dir, tmp_dir)
    elif args.mode == 'info':
		info(args, module_dir, tmp_dir)
    else:
    	# Should this throw instead?
    	logger.critical ("Mode not found, please choose \'info\' or \'regression\'")
        sys.exit(1)


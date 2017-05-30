# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import sys

from modes.performance import PerformanceMode as performance
from modes.regression import RegressionMode as regression
from modes.scan import ScanMode as scan


# Eventually import other future tests, like
# pin, performance


logger = logging.getLogger(__name__)


def run(args, module_dir, tmp_dir):
    # determine which test to run
    if args.mode == 'regression':
        current_mode = regression(args, module_dir, tmp_dir)
        current_mode.setup()
        current_mode.run()
        current_mode.report()
        current_mode.teardown()
    elif args.mode == 'scan':
        current_mode = scan(args, module_dir, tmp_dir)
        current_mode.setup()
        current_mode.run()
        current_mode.report()
        current_mode.teardown()
    elif args.mode == 'performance':
        current_mode = performance(args, module_dir, tmp_dir)
        current_mode.setup()
        current_mode.run()
        current_mode.report()
        current_mode.teardown()
    else:
        # Should this throw instead?
        logger.critical("Mode not found, please choose `scan`, `regression` or `performance`")
        sys.exit(1)

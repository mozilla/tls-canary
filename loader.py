# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import sys

import modes


# Eventually import other future tests, like
# pin, performance


logger = logging.getLogger(__name__)


def run(args, module_dir, tmp_dir):

    try:
        current_mode = modes.all_modes[args.mode](args, module_dir, tmp_dir)
    except KeyError:
        logger.critical("Unknown run mode `%s`. Choose one of: %s" % (args.mode, ", ".join(args.all_mode_names)))
        sys.exit(1)

    current_mode.setup()
    current_mode.run()
    current_mode.report()
    current_mode.teardown()

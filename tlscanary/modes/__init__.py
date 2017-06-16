# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import basemode
import performance
import regression
import scan
import sourceupdate

__all__ = ["performance", "regression", "scan", "sourceupdate"]


def __subclasses_of(cls):
    sub_classes = cls.__subclasses__()
    sub_sub_classes = []
    for sub_cls in sub_classes:
        sub_sub_classes += __subclasses_of(sub_cls)
    return sub_classes + sub_sub_classes


# Keep a record of all BaseMode subclasses
all_modes = dict([(mode.name, mode) for mode in __subclasses_of(basemode.BaseMode)])
all_mode_names = all_modes.keys()
all_mode_names.sort()
default_mode = "regression"  # name of the default mode as listed in <mode class>.name
assert default_mode in all_mode_names

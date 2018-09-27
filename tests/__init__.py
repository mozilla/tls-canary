# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.


class ArgsMock(object):
    """
    Mock used for testing functionality that
    requires access to an args-style object.
    """
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __getattr__(self, attr):
        try:
            return self.kwargs[attr]
        except KeyError:
            return None

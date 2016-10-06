# -*- coding: utf-8 -*-

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

class ProgressBar(object):
    """A neat progress bar for the terminal"""

    _box = u' ▏▎▍▌▋▊▉█'
    _boundary_l = u'|'
    _boundary_r = u'|'

    def __init__(self, min_value, max_value, outer_width=50,
                 show_percent=False, show_boundary=False):
        self._min = min_value
        self._max = max_value
        self._diff = self._max - self._min
        self._value = self._min
        self._outer_width = outer_width
        self._show_percent = show_percent
        self._show_boundary = show_boundary
        self._bar_width = self._outer_width
        if show_percent:
            self._bar_width -= 5
        if show_boundary:
            self._bar_width -= len(self._boundary_l + self._boundary_r)
        if self._bar_width < 1:
            raise Exception('Insufficient outer width for progress bar')

    def set(self, value):
        """Set the current value. Will be limited to [min, max]"""
        self._value = max(self._min, min(self._max, value))

    def _draw_bar(self):
        """Helper function that returns the bare bar as a string"""

        # There is a fixed number of boxes in the whole progress bar.
        n_boxes = self._bar_width
        # Every box has a fixed number of states between empty and full.
        n_box_states = len(self._box) - 1
        # So the whole bar has a fixed number of states, too.
        n_bar_states = n_box_states * n_boxes
        
        # Calculate the set value relative to the total number of bar states.
        bar_value = int(n_bar_states * (self._value - self._min) / self._diff)

        # This is what happens next: Number each box i = 0..n_boxes-1
        # bar = range(0, n_boxes)

        # Calculate the base state number for each box.
        # bar = map(lambda i: n_box_states * i, bar)

        # Subtract each box's base state number from the current bar value.
        # bar = map(lambda base: bar_value - base, bar)

        # Restrict each box to a value in [0..n_box_states].
        # bar = map(lambda x: max(0, min(n_box_states, x)), bar)

        # Look up the `eigths box` unicode character for every box state.
        # bar = map(lambda state: self._box[state], bar)

        # This is an equivalent but about twice as efficient one-liner:
        bar = [self._box[max(0, min(n_box_states, bar_value - n_box_states * i))] \
                for i in xrange(0, n_boxes)]

        return u''.join(bar)

    def __unicode__(self):
        """Returns the `rendered` bar as a unicode string"""

        line = u''
        if self._show_percent:
            percent = int(100.0 * (self._value - self._min) / self._diff)
            line += u'%3d%% ' % percent
        if self._show_boundary:
            line += self._boundary_l
        line += self._draw_bar()
        if self._show_boundary:
            line += self._boundary_r

        return line

    def __str__(self):
        """Returns the `rendered` bar as a utf-8 string"""
        return unicode(self).encode('utf-8')

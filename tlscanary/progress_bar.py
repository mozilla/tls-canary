# -*- coding: utf-8 -*-

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime


class ProgressBar(object):
    """A neat progress bar for the terminal"""

    _box = u' ▏▎▍▌▋▊▉█'
    _boundary_l = u'|'
    _boundary_r = u'|'

    def __init__(self, min_value, max_value, outer_width=50,
                 show_percent=False, show_boundary=False, stats_window=0):
        self._min = float(min_value)
        self._max = float(max_value)
        self._diff = self._max - self._min
        self._value = self._min
        self._outer_width = outer_width
        self._show_percent = show_percent
        self._show_boundary = show_boundary
        self._bar_width = self._outer_width
        self._stats_window = stats_window
        self._stats = []
        self._start_time = None
        if show_percent:
            self._bar_width -= 5
        if show_boundary:
            self._bar_width -= len(self._boundary_l + self._boundary_r)
        if self._bar_width < 1:
            raise Exception('Insufficient outer width for progress bar')

    def set(self, value):
        """Set the current value. Will be limited to [min, max]"""
        self._value = float(max(self._min, min(self._max, value)))
        if self._start_time is None:
            self._start_time = datetime.datetime.now()
        if self._stats_window > 0:
            self._stats.append((datetime.datetime.now(), self._value))
            if len(self._stats) > self._stats_window:
                self._stats = self._stats[-self._stats_window:]

    def stats(self):
        """Return a list of runtime statistics"""

        past = datetime.datetime.now() - datetime.timedelta(1)
        if len(self._stats) < 2:
            return 0., datetime.timedelta(0), past, 0., datetime.timedelta(0), past

        relative_done = (self._value - self._min) / self._diff
        relative_todo = 1.0 - relative_done

        # Calculate rate and ETA relative to overall progress
        try:
            latest_update_time, _ = self._stats[-1]
            elapsed_time = latest_update_time - self._start_time
            overall_rate = relative_done / elapsed_time.seconds
            overall_rest_time = datetime.timedelta(seconds=(relative_todo / overall_rate))
            overall_eta = latest_update_time + overall_rest_time
        except ZeroDivisionError:
            # If rate was zero
            overall_rest_time = datetime.timedelta(0)
            overall_eta = past

        # Calculate rate and ETA relative to current progress
        try:
            window_start_time, window_start_value = self._stats[0]
            window_end_time, window_end_value = self._stats[-1]
            window_elapsed_time = window_end_time - window_start_time
            window_done = (window_end_value - window_start_value) / self._diff
            current_rate = window_done / window_elapsed_time.seconds
            current_rest_time = datetime.timedelta(seconds=(relative_todo / current_rate))
            current_eta = window_end_time + current_rest_time
        except ZeroDivisionError:
            # If rate is zero
            current_rest_time = datetime.timedelta(0)
            current_eta = past

        return overall_rate * self._diff, overall_rest_time, overall_eta, \
            current_rate * self._diff, current_rest_time, current_eta

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
        bar = [self._box[max(0, min(n_box_states, bar_value - n_box_states * i))]
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

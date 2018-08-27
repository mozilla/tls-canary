# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import threading
import time
from functools import reduce

logger = logging.getLogger(__name__)


class ProgressTracker(object):
    """Class that implements progress tracking"""

    def __init__(self, total, unit=None, percent=True, speed=True, eta=True, average=30*60.0):
        """
        Constructor for a ProcessLogger

        The class keeps track of completed and overhead calculations, and
        can estimate current progress speed and time of completion (ETA).

        :param total: int total calculations required for completion
        :param unit: str for unit used for speed
        :param percent: bool whether to show percent
        :param speed: bool whether or not to show speed
        :param eta: bool whether or not to show ETA
        :param average: float length of averaging window
        """
        self.total = total
        self.completed = 0
        self.overhead = 0
        self.unit = "" if unit is None else " %s" % unit
        self.show_percent = percent
        self.show_speed = speed
        self.show_eta = eta
        self.average_window = average
        self.log = []
        self.write_lock = threading.Lock()
        self.start_time = time.time()
        self.logger_thread = None

    def log_completed(self, completed):
        """
        Log a number of completed calculations

        :param completed: Number of completed items
        :return: None
        """
        self.write_lock.acquire()
        try:
            self.log.append((time.time(), completed, 0))
            self.completed += completed
        finally:
            self.write_lock.release()

    def log_overhead(self, overhead):
        """
        Log a number of overhead calculations
        :param overhead:
        :return:
        """
        self.write_lock.acquire()
        try:
            self.log.append((time.time(), 0, overhead))
            self.overhead += overhead
        finally:
            self.write_lock.release()

    def log_window(self, window):
        """
        Return current averaging window

        :param window: float time span for window
        :return: list of (time, int completed, int overhead)
        """
        earliest_time = time.time() - window
        latest_entry = len(self.log)
        earliest_entry = latest_entry
        for i in range(latest_entry - 1, -1, -1):
            if self.log[i][0] >= earliest_time:
                earliest_entry = i
            else:
                break
        return self.log[earliest_entry:latest_entry]

    @staticmethod
    def __window_parameters(log_window):
        """
        Calculate timespan and sums of completed and overhead for log window

        :param log_window: list
        :return: float time span, int completed, int overhead
        """
        # Skip first log entry in window, because it logs values from before target timeframe
        earliest, _, _ = log_window[0]
        latest, completed, overhead = reduce(lambda x, y: (y[0], x[1] + y[1], x[2] + y[2]), log_window[1:])
        span = latest - earliest
        return span, completed, overhead

    def __str__(self):
        """
        Return string representation of current progress

        :return: str
        """

        now = time.time()
        overall_time = now - self.start_time

        # Calculate overall progress and percentages
        net_total = self.total
        net_done = self.completed
        # net_todo = self.total - net_done
        net_percent = min(100.0 * net_done / net_total, 100.0)

        # Gross values take overhead into account
        gross_done = self.completed + self.overhead
        # Gross total is estimated by total overhead so far
        gross_total = net_total if net_done == 0 else net_total * gross_done / net_done
        gross_todo = gross_total - gross_done

        # Overhead is relative to net total
        overhead_percent = 0.0 if net_done == 0 else 100.0 * self.overhead / net_done

        # Get current averaging window
        log_window = self.log_window(self.average_window)

        # Bail out if there is not enough data in the window
        if len(log_window) < 2:
            s = ""
            if self.show_percent:
                s += "%.0f%% " % net_percent
            s += "%d/%d" % (min(net_done, net_total), net_total)
            s += ", %.0f%% overhead" % overhead_percent
            if self.show_speed:
                s += ", --%s/s net" % self.unit
                s += ", --%s/s gross" % self.unit
            if self.show_eta:
                s += ", ETA --"
            return s

        # Get values for current averaging window
        win_span, win_completed, win_overhead = self.__window_parameters(log_window)

        # Calculate overall and current net and gross speeds, and ETA
        # net_speed = float(net_done) / overall_time
        gross_speed = float(gross_done) / overall_time
        net_win_speed = float(win_completed) / win_span
        gross_win_speed = float(win_completed + win_overhead) / win_span
        # Speed might have been zero
        if gross_win_speed != 0.0:
            gross_eta = now + gross_todo / gross_win_speed
        else:
            gross_eta = None

        # Build the string according to config
        s = ""
        if self.show_percent:
            s += "%.0f%% " % net_percent
        s += "%d/%d" % (min(net_done, net_total), net_total)
        s += ", %.1f%% overhead" % overhead_percent
        if self.show_speed:
            match = [
                (0.001, "%s/ms" % self.unit),
                (1.0, "%s/s" % self.unit),
                (60.0, "%s/min" % self.unit),
                (60.0 * 60.0, "%s/h" % self.unit),
                (24.0 * 60.0 * 60.0, "%s/day" % self.unit)
            ]
            scale, unit = match[1]
            for scale, unit in match:
                if gross_speed * scale > 100:
                    break
            s += ", %.0f%s net" % (scale * net_win_speed, unit)
            s += ", %.0f%s gross" % (scale * gross_win_speed, unit)
        if self.show_eta:
            if gross_eta is not None:
                s += ", ETA %s" % time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(gross_eta))
            else:
                s += ", ETA --"
        return s

    def start_reporting(self, interval, first_interval=None):
        """
        Spawn logger thread

        :param interval: float seconds between log update
        :param first_interval: optional float seconds before first log update
        :return: None
        """
        global logger

        if self.logger_thread is None:
            logger.debug("Starting progress logger thread")
            self.logger_thread = ProgressLogger(self, first_interval, interval)
            self.logger_thread.setName("Progress")
            self.logger_thread.daemon = True  # Thread dies with worker
            self.logger_thread.start()

    def stop_reporting(self):
        """
        Stop logger thread

        :return: None
        """
        global logger

        if self.logger_thread is not None:
            logger.debug("Terminating progress logger thread")
            try:
                self.logger_thread.quit()
            except AttributeError:
                pass
            finally:
                self.logger_thread = None


class ProgressLogger(threading.Thread):
    """Progress logger thread that logs progress updates"""

    def __init__(self, pr, first_interval, regular_interval):
        """
        Constructor

        :param pr: ProgressTracker instance to monitor
        :param first_interval: float seconds before first log update
        :param regular_interval: float seconds between log update
        """
        super(ProgressLogger, self).__init__()
        self.pr = pr
        self.first_interval = first_interval
        self.regular_interval = regular_interval
        self.updated_at = time.time()
        self.__quit = False

    def __update_time(self):
        """
        Iterator that returns time of next progress update.
        The first update may be different from the rest.

        :return: float iterator
        """
        if self.first_interval is not None:
            yield self.updated_at + self.first_interval
        while True:
            yield self.updated_at + self.regular_interval

    def run(self):
        """
        Start thread

        :return: None
        """
        global logger

        logger.debug("ProgressLogger thread starting")
        update_time = self.__update_time()
        next_update = next(update_time)
        while not self.__quit:
            time.sleep(1)
            now = time.time()
            if now >= next_update:
                logger.info(str(self.pr))
                self.updated_at = now
                next_update = next(update_time)
        logger.debug("ProgressLogger thread exiting")

    def quit(self):
        """
        Signal thread to terminate

        :return: None
        """
        self.__quit = True

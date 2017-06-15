# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import logging
from threading import Thread
import time
from worq.pool.thread import WorkerPool
from worq import get_broker, get_queue, TaskSpace

import progress_bar
import xpcshell_worker as xw


logger = logging.getLogger(__name__)
ts = TaskSpace(__name__)


def init(worq_url):
    global logger, ts
    broker = get_broker(worq_url)
    broker.expose(ts)
    return broker


def start_pool(worq_url, num_workers=1, **kw):
    broker = init(worq_url)
    pool = WorkerPool(broker, workers=num_workers)
    pool.start(**kw)
    return pool


class ScanResult(object):
    """Class to hold and evaluate scan responses."""

    def __init__(self, response):
        self.response = response
        self.success = self.evaluate_success(response)
        self.host = self.get_host()
        self.rank = self.get_rank()

    def get_host(self):
        return self.response.original_cmd["args"]["host"]

    def get_rank(self):
        return self.response.original_cmd["args"]["rank"]

    @staticmethod
    def evaluate_success(response):
        global logger

        # if .success is true, the result came through the requests
        # `load` handler with state == 4 (fully loaded).
        if response.success:
            return True

        # Else, check whether the error was due to a redirect error, with the first hop being OK.
        uri = response.result["info"]["original_uri"]
        status = response.result["info"]["status"]
        origin = response.result["origin"]
        if origin == "error_handler" and status == 0:  # NS_OK
            logger.debug("Ignored redirect by `%s`" % uri)
            return True

        # Else, the request had some sort of issue
        return False


@ts.task
def scan_urls(app, target_list, profile=None, prefs=None, get_certs=False, timeout=10):
    global logger

    logger.debug("scan_urls task called with %s" % repr(target_list))

    # Spawn a worker instance
    xpcw = xw.XPCShellWorker(app, profile=profile, prefs=prefs)
    xpcw.spawn()

    # Enqueue all host scans for this worker instance
    wakeup_cmd = xw.Command("wakeup")
    cmd_count = 0
    for rank, host in target_list:
        scan_cmd = xw.Command("scan", host=host, rank=rank, include_certificates=get_certs, timeout=timeout)
        xpcw.send(scan_cmd)
        if cmd_count % 10 == 0:
            xpcw.send(wakeup_cmd)
        cmd_count += 1

    # Fetch results from queue, until all results are in or until the last
    # scan must have into timeout. Note that ACKs come in strict sequence of
    # their respective commands.
    results = {}
    timeout_time = time.time() + timeout + 1
    while time.time() < timeout_time:
        for response in xpcw.receive():
            if response.result == "ACK":
                # Reset timeout when scan commands are ACKed.
                if response.original_cmd["mode"] == "scan":
                    timeout_time = time.time() + timeout + 1
                # Ignore other ACKs.
                continue
            # Else we know this is the result of a scan command.
            result = ScanResult(response)
            results[result.host] = result
        if len(results) >= len(target_list):
            break
        xpcw.send(wakeup_cmd)
        time.sleep(0.1)

    if len(results) < len(target_list):
        logger.warning("Worker dropped results, yielded %d instead of %d" % (len(results), len(target_list)))

    # Wind down the worker
    xpcw.send(xw.Command("quit"))
    xpcw.terminate()

    return results


@ts.task
def collect(result_dicts):
    combined_results = {}
    for result in result_dicts:
        combined_results.update(result)
    return combined_results


def __as_chunks(flat_list, chunk_size):
    for i in range(0, len(flat_list), chunk_size):
        yield flat_list[i:i + chunk_size]


pool = None
progress_thread = None
progress_thread_running = False


def progress_reporter(queue, multiplier, update_interval=60.0):
    global logger, progress_thread_running

    logger.debug("Progress reporter thread started")

    overall_len = len(queue) * multiplier
    next_update = datetime.datetime.now() + datetime.timedelta(seconds=update_interval)

    progress = progress_bar.ProgressBar(0, overall_len, show_percent=True,
                                        show_boundary=True, stats_window=60)

    progress_thread_running = True
    while progress_thread_running:
        time.sleep(1)
        urls_todo = len(queue) * multiplier
        if urls_todo == 0:
            break
        urls_done = overall_len - urls_todo
        progress.set(urls_done)
        now = datetime.datetime.now()
        if now >= next_update:
            overall_rate, overall_rest_time, overall_eta, \
                current_rate, current_rest_time, current_eta = progress.stats()
            logger.info("%d URLs to go. Current rate %d URLs/minute, rest time %d minutes, ETA %s" % (
                urls_todo,
                round(current_rate * 60.0),
                round(current_rest_time.seconds / 60.0),
                current_eta.isoformat()))
            next_update = now + datetime.timedelta(seconds=update_interval)

    progress_thread_running = False
    logger.debug("Progress reporter thread finished")


def stop():
        global pool, progress_thread, progress_thread_running
        if progress_thread is not None:
            progress_thread_running = False
            progress_thread = None
        if pool is not None:
            pool.stop()
            pool = None


# CAVE: run_scans is not re-entrant due to use of global variables.
def run_scans(app, target_list, profile=None, prefs=None, num_workers=4, targets_per_worker=50, worq_url="memory://",
              progress=False, get_certs=False, timeout=10):
    global pool, progress_thread, progress_thread_running

    pool = start_pool(worq_url, timeout=1, num_workers=num_workers)

    chunks = __as_chunks(target_list, targets_per_worker)
    try:
        queue = get_queue(worq_url, target=__name__)

        if progress:
            progress_thread = Thread(target=progress_reporter, name="progress_reporter",
                                     args=(queue, targets_per_worker))
            progress_thread.daemon = True  # Thread dies with worker
            progress_thread_running = False

        # Enqueue tasks to be executed in parallel
        scan_results = [queue.scan_urls(app, targets, profile=profile, prefs=prefs,
                                        get_certs=get_certs, timeout=timeout)
                        for targets in chunks]
        result = queue.collect(scan_results)

        if progress:
            progress_thread.start()

        result.wait(timeout=2**60)

    except KeyboardInterrupt:
        stop()
        raise KeyboardInterrupt

    finally:
        stop()

    return result.value

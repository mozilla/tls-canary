# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import select
from worq.pool.thread import WorkerPool
from worq import get_broker, get_queue, TaskSpace

import xpcshell_worker as xw


logger = logging.getLogger(__name__)
ts = TaskSpace(__name__)
pool = None


def init(worq_url):
    global ts
    broker = get_broker(worq_url)
    broker.expose(ts)
    return broker


def start_pool(worq_url, num_workers=1, **kw):
    broker = init(worq_url)
    new_pool = WorkerPool(broker, workers=num_workers)
    new_pool.start(**kw)
    return new_pool


def stop():
    global logger, pool
    logger.debug("Stopping worker pool %s" % pool)
    if pool is not None:
        pool.stop()
        pool = None


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

    def as_dict(self):
        return {
            "response": self.response.as_dict(),
            "success": self.success,
            "host": self.host,
            "rank": self.rank
        }


@ts.task
def scan_urls(app, target_list, profile=None, prefs=None, get_certs=False, timeout=10, parallel=50):
    logger = logging.getLogger(__name__ + " scan_url")

    # logger.debug("scan_urls task called with %d targets" % len(target_list))

    # Spawn a worker instance
    xpcw = xw.XPCShellWorker(app, profile=profile, prefs=prefs)
    xpcw.spawn()

    next_target = iter(target_list)
    in_flight = {}
    results = []

    while len(results) < len(target_list):
        # logger.critical("results: %d, in_flight: %d, parallel: %d" % (len(results), len(in_flight), parallel))

        while len(in_flight) < parallel:
            # Enqueue next target
            try:
                rank, host = next_target.next()
            except StopIteration:
                # Nothing left to do but wait for outstanding results
                break
            conn = xpcw.get_connection(timeout=2)
            conn.connect()
            cmd = xw.Command("scan", host=host, rank=rank, include_certificates=get_certs, timeout=timeout)
            # logger.critical("sending command %s" % cmd)
            conn.send(cmd)
            in_flight[conn.id] = (cmd, conn)

        # Compile list of all in-flight sockets
        read_conns = [in_flight[i][1] for i in in_flight]

        # Select readables and exceptions
        readable, _, exceptions = select.select(read_conns, [], read_conns, 1.5*timeout)

        if len(readable) == 0 and len(exceptions) == 0:
            logger.warning("Task's socket select ran into timeout. Dropping outstanding results")
            break

        # Do all the reads
        for conn in readable:
            res = conn.receive(timeout=2)
            if res is None:
                cmd = in_flight[conn.id][0]
                logger.warning("Requeueing command %s" % cmd.id)
                conn.send(cmd)
            else:
                results.append(ScanResult(res))
                del in_flight[conn.id]

        # Drop all the exceptions
        if len(exceptions) > 0:
            for i in in_flight:
                cmd, conn = in_flight[i]
                if conn in exceptions:
                    logger.error("Task dropping command %s" % cmd.id)
                    results.append(None)  # TODO: append ad-hoc result object
                    del in_flight[i]

    # Wind down the worker
    xpcw.quit()

    logger.debug("Worker task finished, returning %d results" % len(results))

    return results


# CAVE: run_scans is not re-entrant due to use of global variables.
def run_scans(app, target_list, profile=None, prefs=None, num_workers=4, targets_per_worker=50, worq_url="memory://",
              get_certs=False, timeout=10, progress_callback=None):
    global logger, pool

    # logger.critical("run_scans called with %d hosts" % len(target_list))

    pool = start_pool(worq_url, timeout=1.5*timeout, num_workers=num_workers)

    try:
        queue = get_queue(worq_url, target=__name__)

        # Enqueue tasks to be executed in parallel
        result = queue.scan_urls(app, target_list, profile=profile, prefs=prefs,
                                 get_certs=get_certs, timeout=timeout, parallel=targets_per_worker)

        # from IPython import embed
        # embed()

        finished = False
        while not finished:
            finished = result.wait(timeout=0.1)

        num_results = len(result.value)
        if num_results != len(target_list):
            logger.warning("Got %d instead of %d results" % (num_results, len(target_list)))

        if progress_callback is not None:
            progress_callback(num_results)

    except KeyboardInterrupt:
        logger.critical("Ctrl-C received. Winding down workers...")
        stop()
        logger.debug("Signaled workers to quit")
        raise KeyboardInterrupt

    finally:
        stop()

    return result.value

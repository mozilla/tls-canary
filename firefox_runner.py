# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import logging
import os
from Queue import Queue, Empty
import subprocess
from threading import Thread
import time


logger = logging.getLogger(__name__)


def read_from_worker(worker, queue):
    logger.debug('Reader thread started for worker %s' % worker)
    for line in iter(worker.stdout.readline, b''):
        try:
            queue.put(json.loads(line))
        except ValueError:
            logger.warning("Unexpected script output: %s" % line.strip())
    logger.debug('Reader thread finished for worker %s' % worker)
    worker.stdout.close()


class FirefoxRunner(object):
    def __init__(self, exe_file, work_list, work_dir, data_dir, num_workers=None, get_certs=False):
        self._exe_file = exe_file
        self.work_list = Queue(maxsize=len(work_list))
        for row in work_list:
            self.work_list.put(row)
        self.work_dir = work_dir
        self.data_dir = data_dir
        if num_workers is None:
            self._num_workers = 10
        else:
            self._num_workers = num_workers
        self.workers = []
        self.results = Queue(maxsize=len(work_list))
        self._get_certs = get_certs

    def maintain_worker_queue(self):
        for worker in self.workers:
            ret = worker.poll()
            if ret is not None:
                logger.debug('Worker terminated with return code %d' % ret)
                self.workers.remove(worker)
        while len(self.workers) < self._num_workers:
            if self.work_list.empty():
                return
            rank, url = self.work_list.get()
            rank_url = "%d,%s" % (rank, url)
            cmd = [self._exe_file,
                   '-xpcshell',
                   os.path.join(self.data_dir, "js", "scan_url.js"),
                   '-u=%s' % rank_url,
                   '-d=%s' % self.data_dir]
            if self._get_certs:
                cmd.append("-j=true")
                cmd.append("-c=/tmp/")
            logger.debug("Executing shell command `%s`" % ' '.join(cmd))
            worker = subprocess.Popen(
                cmd,
                cwd=self.data_dir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1)  # `1` means line-buffered
            self.workers.append(worker)
            # Spawn a reader thread, because stdio reads are blocking
            reader = Thread(target=read_from_worker, name="Reader_"+rank_url, args=(worker, self.results))
            reader.daemon = True  # Thread dies with worker
            reader.start()
            logger.debug('Spawned worker, now %d in queue' % len(self.workers))

    def is_done(self):
        return len(self.workers) == 0 and self.work_list.empty()

    def get_result(self):
        """Read from result queue. Returns None if empty."""
        try:
            return self.results.get_nowait()
        except Empty:
            return None

    def _wait_for_remaining_workers(self, delay):
        kill_time = time.time() + delay
        while time.time() < kill_time:
            for worker in self.workers:
                ret = worker.poll()
                if ret is not None:
                    logger.debug('Worker terminated with return code %d' % ret)
                    self.workers.remove(worker)
            if len(self.workers) == 0:
                break
            time.sleep(0.05)

    def terminate_workers(self):
        # Signal workers to terminate
        for worker in self.workers:
            worker.terminate()
        # Wait for 5 seconds for workers to finish
        self._wait_for_remaining_workers(5)

        # Kill remaining workers
        for worker in self.workers:
            worker.kill()  # Same as .terminate() on Windows
        # Wait for 5 seconds for workers to finish
        self._wait_for_remaining_workers(5)

        if len(self.workers) != 0:
            logger.warning('There are %d non-terminating workers remaining' % len(self.workers))

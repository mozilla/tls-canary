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
    global logger
    logger.debug('Reader thread started for worker %s' % worker)
    for line in iter(worker.stdout.readline, b''):
        try:
            queue.put(json.loads(line))
        except ValueError:
            # FIXME: XPCshell is currently issuing many warnings, constant warning is too verbose
            # logger.warning("Unexpected script output: %s" % line.strip())
            logger.debug("Unexpected script output: %s" % line.strip())
    logger.debug('Reader thread finished for worker %s' % worker)
    worker.stdout.close()


class FirefoxRunner(object):
    def __init__(self, exe_file, work_list, work_dir, data_dir, num_workers=10, info=False, cert_dir=None):
        self.__exe_file = exe_file
        self.__work_list = Queue(maxsize=len(work_list))
        for row in work_list:
            self.__work_list.put(row)
        self.__work_dir = work_dir  # usually ~/.tlscanary
        self.__data_dir = data_dir  # usually module directory
        self.__num_workers = num_workers
        self.workers = []
        self.results = Queue(maxsize=len(work_list))
        self.__info = info
        self.__cert_dir = cert_dir

    def maintain_worker_queue(self):
        for worker in self.workers:
            ret = worker.poll()
            if ret is not None:
                logger.debug('Worker terminated with return code %d' % ret)
                self.workers.remove(worker)

        while len(self.workers) < self.__num_workers:
            if self.__work_list.empty():
                return 0
            rank, url = self.__work_list.get()
            rank_url = "%d,%s" % (rank, url)
            cmd = [self.__exe_file,
                   '-xpcshell',
                   os.path.join(self.__data_dir, "js", "scan_url.js"),
                   '-u=%s' % rank_url,
                   '-d=%s' % self.__data_dir]
            if self.__info:
                cmd.append("-j=true")
            if self.__cert_dir is not None:
                cmd.append("-c=%s" % self.__cert_dir)
            logger.debug("Executing shell command `%s`" % ' '.join(cmd))
            worker = subprocess.Popen(
                cmd,
                cwd=self.__data_dir,
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

        return self.__work_list.qsize()

    def is_done(self):
        return len(self.workers) == 0 and self.__work_list.empty()

    def get_result(self):
        """Read from result queue. Returns None if empty."""
        try:
            return self.results.get_nowait()
        except Empty:
            return None

    def __wait_for_remaining_workers(self, delay):
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
        self.__wait_for_remaining_workers(5)

        # Kill remaining workers
        for worker in self.workers:
            worker.kill()  # Same as .terminate() on Windows
        # Wait for 5 seconds for workers to finish
        self.__wait_for_remaining_workers(5)

        if len(self.workers) != 0:
            logger.warning('There are %d non-terminating workers remaining' % len(self.workers))

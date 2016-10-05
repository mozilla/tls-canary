# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from Queue import Queue, Empty
import subprocess
from threading import Thread
import time


def read_from_worker(worker, queue):
    print 'Reader thread started for worker', worker
    for line in iter(worker.stdout.readline, b''):
        queue.put(line.rstrip('\n'))
    print 'Reader thread finished for worker', worker
    worker.stdout.close()


class FirefoxRunner(object):
    def __init__(self, exe_file, workers=None):
        self._exe_file = exe_file
        if workers is None:
            self._num_workers = 10
        else:
            self._num_workers = workers
        self.workers = []
        self.results = Queue()

    def maintain_worker_queue(self):
        for worker in self.workers:
            ret = worker.poll()
            if ret is not None:
                print 'Worker terminated with return code %d' % ret
                self.workers.remove(worker)
        while len(self.workers) < self._num_workers:
            worker = subprocess.Popen(
                [self._exe_file, '-xpcshell', '-v', '180', '/tmp/test.js'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1)  # `1` means line-buffered
            self.workers.append(worker)
            # Spawn a reader thread, because stdio reads are blocking
            reader = Thread(target=read_from_worker, args=(worker, self.results))
            reader.daemon = True  # Thread dies with worker
            reader.start()
            print 'Spawned worker, now %d in queue' % len(self.workers)

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
                    print 'Worker terminated with return code %d' % ret
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
            print 'There are %d non-terminating workers remaining' % len(self.workers)

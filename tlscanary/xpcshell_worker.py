# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import logging
import os
import socket
import subprocess
from threading import Thread
import time
from uuid import uuid1


logger = logging.getLogger(__name__)
module_dir = os.path.split(__file__)[0]


class XPCShellWorker(object):
    """XPCShell worker implementing an asynchronous, JSON-based message system"""

    def __init__(self, app, worker_id=None, script=None, profile=None, prefs=None):
        global module_dir

        self.id = str(worker_id) if worker_id is not None else str(uuid1())
        self.port = None
        self.__app = app
        if script is None:
            self.__script = os.path.join(module_dir, "js", "xpcshell_worker.js")
        else:
            self.__script = script
        self.__profile = profile
        self.__prefs = prefs
        self.worker_process = None
        self.__reader_thread = None

    def spawn(self, port=None):
        """Spawn the worker process and its dedicated handler threads"""
        global logger, module_dir

        if self.is_running():
            logger.warning("Re-spawning worker %s which was already running" % self.id)
            self.terminate()

        if port is None:
            port = self.port if self.port is not None else 0

        cmd = [self.__app.exe, '-xpcshell', "-g", self.__app.gredir,
               "-a", self.__app.browser, self.__script, str(port)]
        logger.debug("Executing worker shell command `%s`" % ' '.join(cmd))

        self.worker_process = subprocess.Popen(
            cmd,
            cwd=self.__app.browser,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1)  # `1` means line-buffered

        if self.worker_process.poll() is not None:
            logger.critical("Unable to start worker %s process. Poll yields %d"
                            % (self.id, self.worker_process.poll()))
            self.terminate()
            return False

        # First line the worker prints to stdout reports success or fail.
        status = self.worker_process.stdout.readline().strip()
        logger.debug("Worker %s reported startup status: %s" % (self.id, status))
        if not status.startswith("INFO:"):
            logger.critical("Worker %s can't get socket on requested port %d" % (self.id, port))
            self.terminate()
            return False

        # Actual port is reported as last word on INFO line
        self.port = int(status.split(" ")[-1])
        logger.debug("Worker %s has PID %s and is listening on port %d"
                     % (self.id, self.worker_process.pid, self.port))

        # Spawn a reader thread for worker log messages,
        # because stdio reads are blocking.
        self.__reader_thread = WorkerReader(self, daemon=True)
        self.__reader_thread.start()

        conn = WorkerConnection(self.port, timeout=2)

        logger.debug("Syncing worker ID to %s" % repr(self.id))
        res = conn.ask(Command("setid", id=self.id))
        if res is None or not res.is_ack() or not res.is_success():
            logger.error("Failed to sync worker ID to `%s`" % self.id)
            self.terminate()
            return False

        if self.__profile is not None:
            logger.critical("Changing profiles is currently disabled due to Nightly breakage")
            # logger.debug("Changing worker profile to `%s`" % self.__profile)
            # res = conn.ask(Command("useprofile", path=self.__profile))
            # if res is None or not res.is_ack() or not res.is_success():
            #     logger.error("Worker failed to switch profile to `%s`" % self.__profile)
            #     self.terminate()
            #     return False

        if self.__prefs is not None:
            logger.debug("Setting worker prefs to `%s`" % self.__prefs)
            res = conn.ask(Command("setprefs", prefs=self.__prefs))
            if res is None or not res.is_ack() or not res.is_success():
                logger.error("Worker failed to set prefs to `%s`" % self.__prefs)
                self.terminate()
                return False

        return True

    def quit(self, timeout=5):
        """Send `quit` command to worker."""
        if self.is_running():
            return self.ask(Command("quit"), timeout=timeout)
        else:
            logger.warning("Not quitting a stopped worker")
            return None

    def terminate(self):
        """Signal the worker process to quit"""
        # The reader thread dies when the Firefox process quits
        self.worker_process.terminate()

    def kill(self):
        """Kill the worker process"""
        self.worker_process.kill()

    def is_running(self):
        """Check whether the worker is still fully running"""
        if self.worker_process is None:
            return False
        return self.worker_process.poll() is None

    def helper_threads(self):
        """Return list of helper threads"""
        helpers = []
        if self.__reader_thread is not None:
            helpers.append(self.__reader_thread)
        return helpers

    def helpers_running(self):
        """Returns whether helpers are still running"""
        for helper in self.helper_threads():
            if helper.is_alive():
                return True
        return False

    def get_connection(self, timeout=None):
        if not self.is_running() or self.port is None:
            return None
        return WorkerConnection(self.port, timeout=timeout)

    def ask(self, cmd, always_reconnect=False, retry=True, timeout=5):
        """Send command or worker and return response"""
        connection = self.get_connection(timeout=timeout)
        if connection is None:
            logger.warning("Asking stopped worker %s", self.id)
            return None
        reply = connection.ask(cmd, always_reconnect=always_reconnect, retry=retry)
        connection.close()
        return reply

    def chat(self, cmds, always_reconnect=False, timeout=5):
        """Send list of commands to worker and return responses"""
        connection = self.get_connection(timeout=timeout)
        if connection is None:
            logger.warning("Chatting stopped worker %s", self.id)
            return [None] * len(cmds)
        replies = connection.chat(cmds, always_reconnect=always_reconnect)
        connection.close()
        return replies


class WorkerReader(Thread):
    """
    Reader thread that reads log messages from the worker's stdout.
    """
    def __init__(self, worker, daemon=False, name="WorkerReader"):
        """
        WorkerReader constructor

        :param worker: XPCShellWorker parent instance
        """
        super(WorkerReader, self).__init__()
        self.worker = worker
        self.daemon = daemon
        if name is not None:
            self.setName(name)

    def run(self):
        global logger
        logger.debug('Reader thread started for worker %s' % self.worker.id)

        # This thread will automatically terminate when worker's stdout is closed
        for line in iter(self.worker.worker_process.stdout.readline, b''):
            line = line.strip()
            if line.startswith("JavaScript error:"):
                logger.error("JS error from worker %s: %s" % (self.worker.id, line))
            elif line.startswith("JavaScript warning:"):
                logger.warning("JS warning from worker %s: %s" % (self.worker.id, line))
            elif line.startswith("DEBUG:"):
                logger.debug("Worker %s: %s" % (self.worker.id, line[7:]))
            elif line.startswith("INFO:"):
                logger.info("Worker %s: %s" % (self.worker.id, line[6:]))
            elif line.startswith("WARNING:"):
                logger.warning("Worker %s: %s" % (self.worker.id, line[9:]))
            elif line.startswith("ERROR:"):
                logger.error("Worker %s: %s" % (self.worker.id, line[7:]))
            elif line.startswith("CRITICAL:"):
                logger.critical("Worker %s: %s" % (self.worker.id, line[10:]))
            else:
                logger.critical("Unexpected output from worker %s: %s" % (self.worker.id, line))

        self.worker.worker_process.stdout.close()
        logger.debug('Reader thread finished for worker %s' % self.worker.id)
        del self.worker  # Breaks cyclic reference


class WorkerConnection(object):
    """
    Worker connection handler that tries to be smart.
    The design philosophy is to open connections ad-hoc,
    but to keep re-using an existing connection until it fails.

    It generally tries to re-send requests when a connection fails.
    """
    def __init__(self, port, host="localhost", timeout=120):
        """
        Connection to a socket-based XPCShell Worker

        :param port: int TCP port the worker is listening on
        :param host: str hostname the worker is running on (default `localhost`)
        :param timeout: int default timeout for requests in seconds (default 120)
        """
        self.id = str(uuid1())
        self.host = host
        self.port = port
        self.timeout = timeout
        self.s = None  # `None` here signifies closed connection and socket

    def fileno(self):
        """Method required for select.select() to work on the object"""
        return self.s.fileno()

    def connect(self, reuse=False, retry_delay=2, timeout=-1):
        """
        Open TCP connection to worker. If there is no socket object, yet, a new one
        is created and the connection opened. If reuse is requested and there is already
        a socket object instance, the socket will be closed and re-opened.

        :param reuse: bool flag for re-using an existing connection (default False)
        :param retry_delay: delay before trying reconnect in seconds (default 2)
        :param timeout: int connection timeout in seconds (default -1, connection default)
        :return: None
        """
        timeout = timeout if timeout is None or timeout >= 0 else self.timeout

        if self.s is not None:
            if reuse:
                return
            else:
                logger.warning("Worker connection is already open. Closing existing connection.")
                self.close()

        timeout_time = time.time() + timeout if timeout is not None else None
        while True:

            if timeout_time is not None and time.time() >= timeout_time:
                self.close()
                raise socket.timeout("Worker connect timeout")

            try:
                self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.s.settimeout(timeout)
                self.s.connect((self.host, self.port))
                return

            except socket.error as err:
                if err.errno == 61:
                    logger.warning("Worker refused connection. Is it even listening? Retrying")
                    time.sleep(retry_delay)
                    continue
                elif err.errno == 49:  # Can't assign requested address
                    # The OS may need some time to garbage collect closed sockets.
                    logger.warning("OS is probably out of sockets. Retrying")
                    time.sleep(retry_delay)
                    continue
                else:
                    self.close()
                    raise err

    def close(self):
        """
        Close the socket connection to the worker.
        Closing a connection means that all outstanding replies to worker commands for
        that connection are lost.

        :return: None
        """
        if self.s is None:
            logger.warning("Worker socket on port %d is already closed" % self.port)
        else:
            self.s.close()
            self.s = None

    def reconnect(self, timeout=-1):
        """
        Close an existing connection (if any) and open it again.

        :param timeout: int (default -1, connection default)
        :return: None
        """
        if self.s is not None:
            self.close()
        self.connect(timeout=timeout)

    def send(self, request, retry=True, timeout=-1):
        """
        Send a raw string to the worker. The given request is converted to a string,
        then stripped of trailing newlines, and then sent to the worked, followed by
        a newline. It can handle multi-line requests, but the idea is to make one call
        to send() per command line.

        The worker answers commands asynchronously over the socket connection the
        command was received on. The caller to send() is responsible for associating
        commands and their respective replies.

        The connection is automatically opened if necessary. If retry is true,
        the socket will be reconnected when it was closed by the peer.

        The return value is a bool signifying whether the socket had to be reconnected.
        In this case, all outstanding replies that were sent over the socket are lost.
        The caller of send() is responsible to keep track of which commands have to be
        re-sent after the connection was lost.

        :param request: object to stringify for the request
        :param retry: bool
        :param timeout: int timeout (default -1, connection default)
        :return: bool
        """
        timeout = timeout if timeout is None or timeout >= 0 else self.timeout

        request = str(request).strip().encode("utf-8")

        if timeout is None:
            timeout = self.timeout

        reconnected = False
        timeout_time = time.time() + timeout if timeout is not None else None

        while True:

            if timeout_time is not None and time.time() >= timeout_time:
                raise socket.timeout("Worker timeout while sending request on port %d" % self.port)

            if self.s is None:
                self.connect(reuse=True)
                reconnected = True

            try:
                # Let send() throw an error when the connection isn't open
                logger.debug("Sending request `%s` on port %d" % (request, self.port))
                self.s.settimeout(timeout)
                r = self.s.sendall(request + "\n")
                break

            except socket.error as err:
                logger.warning("Socket error during worker send on port %d: %s" % (self.port, err))
                if err.errno == 32:  # Broken pipe
                    if retry:
                        self.reconnect()
                        reconnected = True
                        break
                    else:
                        self.close()
                        break
                raise err

        return reconnected

    def receive(self, raw=False, timeout=-1):
        """
        Blocking read from the worker socket. The reply is wrapped in a Response()
        object unless raw is true.

        It returns None if the connection is not open or closed by the worker during read.

        :param raw: bool (default false)
        :param timeout: int timeout (default -1, connection default)
        :return: Response object or str or None
        """
        timeout = timeout if timeout is None or timeout >= 0 else self.timeout

        received = u""

        try:
            while not received.endswith("\n"):
                self.s.settimeout(timeout)
                # Assuming that recv will not return more than one message ending with newline
                r = self.s.recv(8192)
                if len(r) == 0:
                    logger.warning("Empty read likely caused by peer closing connection on port %d" % self.port)
                    self.close()
                    return None
                received += r.decode("utf-8")

        except socket.error as err:
            if err.errno == 54:
                # Connection reset by peer
                logger.warning("Connection reset by peer while receiving on port %d. Closing connection." % self.port)
                self.close()
                return None
            else:
                raise err

        except AttributeError:
            # Socket connection is not open
            logger.warning("Attempting to receive from closed worker socket on port %d" % self.port)
            return None

        received = received.strip()
        logger.debug("Received worker reply `%s` from port %d" % (received, self.port))

        if raw:
            return received
        else:
            return Response(received)

    def ask(self, request, always_reconnect=False, retry=True, timeout=-1):
        """Send single request to worker and wait for and return reply"""
        if always_reconnect:
            self.reconnect()
        else:
            self.connect(reuse=True, timeout=timeout)

        while True:
            self.send(request, timeout=timeout)
            reply = self.receive(timeout=timeout)
            if reply is not None or not retry:
                break
        return reply

    def chat(self, requests, always_reconnect=False, timeout=-1):
        """Conduct synchronous chat over commands or verbatim requests"""
        if always_reconnect:
            self.reconnect(timeout=timeout)
        else:
            self.connect(reuse=True, timeout=timeout)
        timeout = timeout if timeout is None or timeout >= 0 else self.timeout

        replies = []
        for request in requests:
            reply = None
            timeout_time = time.time() + timeout if timeout is not None else None
            while reply is None:
                if timeout_time is not None and time.time() >= timeout_time:
                    raise socket.timeout("Worker timeout during chat")
                self.send(request, timeout=timeout)
                reply = self.receive(timeout=timeout)
            replies.append(reply)
        return replies

    def async_chat(self, requests, timeout=-1):
        """
        Conduct asynchronous chat with worker.
        There is no guarantee that replies arrive in order of requests,
        hence all requests must be re-sent if the connection fails at
        any time.
        """
        self.connect(reuse=True, timeout=timeout)
        timeout_time = time.time() + timeout if timeout is not None else None
        while True:

            if timeout_time is not None and time.time() >= timeout_time:
                self.close()
                raise socket.timeout("Worker async chat timeout")

            # Send all the requests
            for request in requests:
                reconnected = self.send(request, timeout=timeout)
                if reconnected:
                    self.reconnect(timeout=timeout)
                    continue
            # Listen for replies until done or connection breaks
            replies = []
            while True:
                received = self.receive(timeout=timeout)
                if received is None:
                    break
                replies.append(received)
                if len(replies) == len(requests):
                    return replies


class Command(object):
    """Worker command object"""

    def __init__(self, mode_or_dict, **kwargs):
        if type(mode_or_dict) is str:
            self.id = str(uuid1())
            self.mode = mode_or_dict
            self.args = kwargs
        elif type(mode_or_dict) is dict:
            self.id = mode_or_dict["id"]
            self.mode = mode_or_dict["mode"]
            self.args = mode_or_dict["args"]
        else:
            raise Exception("Argument must be mode string or dict with command specs")

    def as_dict(self):
        return {"id": self.id, "mode": self.mode, "args": self.args}

    def __str__(self):
        return json.dumps(self.as_dict())


class Response(object):

    def __init__(self, message_string=None, closed=False):
        global logger

        self.id = None
        self.worker_id = None
        self.original_cmd = None
        self.success = None
        self.result = None
        self.elapsed_ms = None
        self.connection_closed = closed is True

        if message_string is None or len(message_string) == 0:
            return

        message = json.loads(message_string)  # May throw ValueError
        if "id" in message:
            self.id = message["id"]
        if "worker_id" in message:
            self.worker_id = message["worker_id"]
        if "original_cmd" in message:
            self.original_cmd = message["original_cmd"]
        if "success" in message:
            self.success = message["success"]
        if "result" in message:
            self.result = message["result"]
        if "command_time" in message:
            self.command_time = message["command_time"]
        if "response_time" in message:
            self.response_time = message["response_time"]
        if len(message) != 7:
            logger.error("Worker response has unexpected format: %s" % message_string)

    def is_ack(self):
        try:
            return self.result.startswith("ACK")
        except AttributeError:
            return False

    def is_success(self):
        return self.success is True

    def has_content(self):
        return self.success is not None

    def as_dict(self):
        return {
            "id": self.id,
            "original_cmd": self.original_cmd,
            "worker_id": self.worker_id,
            "success": self.success,
            "result": self.result,
            "command_time": self.command_time,
            "response_time": self.response_time,
            "connection_closed": self.connection_closed
        }

    def __str__(self):
        return json.dumps(self.as_dict())

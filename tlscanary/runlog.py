# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import io
import datetime
import glob
import bz2
import hashfs
import json
import logging
import os
import shutil

logger = logging.getLogger(__name__)


class CertDB(object):
    """
    Class to efficiently store SSL certificates
    """
    # TODO: CertDB needs testing

    def __init__(self, args):
        self.args = args
        self.cert_dir = self.log_dir = os.path.abspath(os.path.join(args.workdir, "certs"))
        if not os.path.isdir(self.cert_dir):
            os.makedirs(self.cert_dir)
        self.hash_fs = hashfs.HashFS(self.cert_dir, depth=4, width=1, algorithm='sha256')

    def put(self, der_data):
        if type(der_data) is str:
            hash_address = self.hash_fs.put(io.StringIO(str(der_data)), "der")
            logger.debug("Wrote certificate data to `%s`" % hash_address.abspath)
            return hash_address.id
        elif type(der_data) is list:
            return list(map(self.put, der_data))
        else:
            raise Exception("Unsupported argument type")

    def exists(self, hash_id):
        return self.hash_fs.exists(hash_id)

    def get_abspath(self, hash_id):
        hash_address = self.hash_fs.get(hash_id)
        if hash_address is None:
            return None
        else:
            return hash_address.abspath

    def get_relpath(self, hash_id):
        hash_address = self.hash_fs.get(hash_id)
        if hash_address is None:
            return None
        else:
            return hash_address.relpath


class RunLogDB(object):
    """
    Class to manage run log files
    """

    def __init__(self, args):
        self.args = args
        self.log_dir = os.path.abspath(os.path.join(args.workdir, "log"))
        if not os.path.isdir(self.log_dir):
            os.makedirs(self.log_dir)
        self.cert_db = CertDB(self.args)

    def handle_to_dir_name(self, handle):
        """
        Converts a log  handle to its directory name
        :param handle: str with handle
        :return: str with file name
        """
        # handle format is .strftime("%Y-%m-%dZ%H-%M-%S")
        year, month, _, _, _ = handle.split("-")
        return os.path.join(self.log_dir, year, month, handle)

    @staticmethod
    def dir_name_to_handle(dir_name):
        """
        Converts run log dir name to its handle
        :param dir_name: str
        :return: str with handle
        """
        return os.path.basename(dir_name)

    def exists(self, handle):
        """
        Check whether run log handle is valid
        :param handle: str with handle
        :return: bool
        """
        matches = glob.glob(os.path.join(self.log_dir, "2???", "??", "%s" % handle))
        return len(matches) > 0

    def list_logs(self):
        """
        Returns a list of available log directory names
        :return: list of str of available log directories
        """
        return glob.glob(os.path.join(self.log_dir, "2???", "??", "2???-??-??*"))

    def list(self):
        """
        Returns a list of log handles
        :return: list of str of log handles
        """
        return [self.dir_name_to_handle(dir_name) for dir_name in self.list_logs()]

    def delete(self, handle):
        """
        Delete a log specified by its handle. All associated
        files are purged from the database. There is no undo.
        :param handle: str with log handle
        :return: None
        """
        global logger
        # TODO: method needs testing
        dir_name = self.handle_to_dir_name(handle)
        logger.debug("Purging `%s` from run log database" % dir_name)
        shutil.rmtree(dir_name)

    def list_parts(self, handle):
        """
        Returns a list of parts for a log handles
        :return: list of str of log parts
        """
        # TODO: method needs testing
        return os.listdir(self.handle_to_dir_name(handle))

    def part_path(self, handle, part):
        """
        Return absolute path of a part inside a log's directory.
        :param handle: str with log handle
        :param part: str with part handle
        :return: str with absolute path
        """
        # TODO: method needs testing
        log_dir_path = self.handle_to_dir_name(handle)
        return os.path.join(log_dir_path, part)

    def open(self, handle, part, mode="r", compress=True):
        """
        Open a log file by handle and part name
        :param handle: str log handle
        :param part: str part name
        :param mode: str file mode
        :param compress: bool
        :return: file object
        """
        global logger

        part_name = self.part_path(handle, part)
        if "w" in mode and not os.path.isdir(os.path.dirname(part_name)):
            os.makedirs(os.path.dirname(part_name))

        if "r" in mode:
            if os.path.exists(part_name + ".bz2"):
                part_name = part_name + ".bz2"
        else:
            if compress:
                part_name += ".bz2"

        logger.debug("Opening run log file `%s` in mode `%s`" % (part_name, mode))

        try:
            if part_name.endswith(".bz2"):
                return bz2.BZ2File(part_name, mode)
            else:
                return open(part_name, mode)
        except IOError as err:
            raise Exception("Error opening run log file for handle `%s` part `%s`: %s" % (handle, part, err))

    def read(self, handle, part):
        """
        Return the string content of a log file referenced by its handle
        :param handle: str with handle
        :param part: str with part name
        :return: str with content of logfile
        """
        global logger
        logger.debug("Reading run log `%s` part `%s`" % (handle, part))
        with self.open(handle, part, "r") as f:
            return f.read().decode("utf-8")

    def write(self, handle, part, data):
        """
        Write to log file referenced by handle and part.
        The data object will be passed through str().encode("utf-8").
        :param handle: str with handle
        :param part: str with part name
        :param data: object to write
        :return: None
        """
        global logger
        logger.debug("Writing run log `%s`" % handle)
        with self.open(handle, part, "w") as f:
            f.write(str(data).encode("utf-8"))

    def put_cert(self, cert_data):
        """
        Add a certificate to the certificate database. Returns handle
        :param cert_data: str with DER data
        :return: str handle
        """
        # TODO: method needs testing
        return self.cert_db.put(cert_data)

    def new_log(self):
        """
        Return a new RunLog object that supports incremental logging
        :return:
        """
        handle = datetime.datetime.utcnow().strftime("%Y-%m-%dZ%H-%M-%S")
        return RunLog(handle, "w", self)

    def read_log(self, handle):
        """
        Return a RunLog object that works on the existing log
        refered to by handle.
        :param handle: str with handle
        :return: RunLog object
        """
        return RunLog(handle, "r", self)


class RunLog(object):
    """
    Class to keep state about runs in a generic format
    suitable for later processing. Calling the .log() method is
    designed to work incrementally such that we don't need to keep
    aggregating all results in memory.
    """

    format_revision = 2

    def __init__(self, handle, mode, db):
        """
        Constructor for RunLog

        The `mode` argument determines solely how the run log object
        behaves when called in a `with` statement. If the mode is "w",
        then .start() is called.

        Calling .start() switches the log to running mode. Iterating the
        log or calling len() while running throws an exception.

        :param handle: str with log handle
        :param mode: str with mode ("r" or "w")
        :param db: RunLogDB instance
        """
        self.db = db
        self.handle = handle
        self.mode = mode
        self.parts = []
        self.log_fh = None
        self.meta_fh = None
        self.filter = None
        self.meta = None
        self.is_running = False

    def part(self, part_handle):
        """
        Returns absolute path for an additional log part, referenced
        by its handle, inside the log directory.
        :param part_handle: str with handle
        :return: str with absolute path
        """
        # TODO: method needs testing
        return self.db.part_path(self.handle, part_handle)

    def open_part(self, part_handle, mode="r", compress=True):
        """
        Returns file object of given log part, openend in specified mode
        and compression. The class keeps internally track of file objects
        generated by this method, so they can all be closed at once.

        :param part_handle: str with handle
        :param mode: str with file mode
        :param compress: bool
        :return: file object
        """
        part_fh = self.db.open(self.handle, part_handle, mode, compress)
        self.parts.append(part_fh)
        return part_fh

    def close(self):
        """
        Close all files that were opened through .open_part().
        """
        if self.is_running:
            self.stop()

        if self.log_fh is not None:
            self.log_fh.close()
            self.log_fh = None
        if self.meta_fh is not None:
            self.meta_fh.close()
            self.meta_fh = None
        for f in self.parts:
            if not f.closed:
                f.close()
        self.parts = []

    def start(self, meta=None, log_filter=lambda x: x):
        """
        Start logging. Writes a metadata header to the file.

        Calling this method puts the log in running mode.
        Starting an existing log will overwrite log and meta data.

        :param meta: optional dict with metadata to write
        :param log_filter: filter lambda to map on every log line
        :return: None
        """
        if self.is_running:
            raise Exception("Can't restart already running log `%s`", self.handle)

        self.meta = meta if meta is not None else {}
        self.meta["format_revision"] = self.format_revision
        self.meta["run_completed"] = False
        self.meta["log_lines"] = 0
        self.filter = log_filter

        self.log_fh = self.open_part("log", self.mode, compress=True)
        self.meta_fh = self.open_part("meta", self.mode, compress=False)

        self.meta_fh.seek(0)
        self.meta_fh.write(json.dumps(self.meta, indent=4, sort_keys=True))
        self.meta_fh.truncate()

        self.is_running = True

    def log(self, result_batch):
        """
        Write an individual or multiple lines to the log file.
        Each line is passed through the filter function set by .start().
        A line is not logged if the filter returns None.
        :param result_batch: log item or list of log items
        :return: None
        """
        if not self.is_running:
            raise Exception("Unable to write to stopped log `%s`" % self.handle)

        if type(result_batch) is not list:
            result_batch = [result_batch]
        for result in map(self.filter, result_batch):
            if result is not None:
                self.log_fh.write(("%s\n" % json.dumps(result)).encode("utf-8"))
                self.meta["log_lines"] += 1

    def stop(self, meta=None):
        """
        Wrap up the log file. The given metadata is joined with previously
        provided metadata and appended at the end of the file. Finally, an
        indicator is written to the log file that is used for distinguishing
        between complete and partial log files.

        Metadata given to .stop() has precedence over metadata given to .start().
        :param meta: dict with additional metadata
        :return: None
        """
        if not self.is_running:
            raise Exception("Unable to stop stopped log `%s`", self.handle)

        if meta is None:
            meta = {}
        self.meta.update(meta)
        self.meta["run_completed"] = True
        self.meta_fh.seek(0)
        self.meta_fh.write(json.dumps(self.meta, indent=4, sort_keys=True))
        self.meta_fh.truncate()

        self.meta_fh.close()
        self.meta_fh = None
        self.log_fh.close()
        self.log_fh = None

        self.is_running = False

    def has_finished(self):
        """
        Checks whether the run finished. If the log file is in write mode,
        it checks whether the .stop() method has been called, yet. If the log is in
        read mode, it checks for the presence of the `run_completed` metadata.
        :return: bool
        """
        if self.is_running:
            return False
        meta = self.get_meta()
        if "run_completed" not in meta:
            return False
        else:
            return meta["run_completed"]

    def is_compatible(self):
        """
        Returns whether the log has the same revision as RunLog.format_revision.
        :return: bool
        """
        if self.is_running:
            return True
        meta = self.get_meta()
        if "format_revision" not in meta:
            return False
        else:
            return meta["format_revision"] == self.format_revision

    def update_meta(self, meta):
        """
        Update the metadata on a log. If the log is running, it will not be
        written until .stop() is called.

        Keep in mind that metadata is only updated with the data provided.
        Keys can't be deleted.
        :param meta: dict
        :return: None
        """
        if self.is_running:
            self.meta.update(meta)
        else:
            self.get_meta()
            self.meta.update(meta)
            with self.open_part("meta", "w") as f:
                f.write(json.dumps(self.meta, indent=4, sort_keys=True))

    def get_meta(self):
        """
        Get metadata from log. If the log is running, the metadata collected
        by calls to .start() and .stop() is returned. If the log is not running,
        metadata is taken from the `meta` property of this object.
        :return: dict with metadata
        """
        if self.is_running:
            return self.meta
        if self.meta is None:
            with self.open_part("meta") as f:
                meta = f.read().strip()
            try:
                self.meta = json.loads(meta)
            except ValueError:
                self.meta = {"CORRUPTED": True}
        return self.meta

    def __iter__(self):
        """
        If the log is in read mode, iterate over all log lines.
        :return: iterator
        """
        if self.is_running:
            raise Exception("Unable to iterate running log `%s`", self.handle)

        with self.open_part("log") as f:
            line_number = 0
            while True:
                try:
                    line_number += 1
                    line = f.readline().decode("utf-8")
                except EOFError:
                    logger.debug("EOFError on log `%s`. Log is truncated." % self.handle)
                    break
                if line == "":
                    break
                if not line.startswith("#"):
                    try:
                        json_line = json.loads(line.strip())
                    except ValueError as err:
                        raise Exception("JSON error in run log `%s` line %d: %s"
                                        % (self.handle, line_number, str(err)))
                    yield json_line

    def __len__(self):
        """
        Return the number of lines in the log.

        If the log is running, returns the number of lines written so far.
        If the log is not running and was completed, it returns the value of
        `log_lines` from the metadata.
        If the log is not running and was not completed, it iterates all the
        log lines to count determine the number (slow!).
        """
        # TODO: method needs testing
        if self.is_running:
            return self.meta["log_lines"]

        if self.has_finished():
            return self.get_meta()["log_lines"]

        logger.debug("Counting lines in incomplete log `%s`" % self.handle)
        incomplete_log_lines = 0
        for _ in self:
            incomplete_log_lines += 1
        return incomplete_log_lines

    def __enter__(self):
        """Called when object enters a `with` block"""
        if "w" in self.mode:
            self.start()
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        """Called when object exits a `with` block"""
        if self.is_running:
            self.stop()
        self.close()
        if exception_type is not None:
            logger.error("Exception while handling run log %s: %s %s %s"
                         % (self.handle, exception_type, exception_value, traceback))
        return self

    def delete(self):
        """
        Delete this log from the log database. All associated files are
        purged from disk. Be careful! There is no undo.

        After calling this method, the log object becomes dysfunctional.
        No other methods should be called hereafter.
        :return: None
        """
        # TODO: method needs testing
        if self.is_running:
            self.stop()
        self.close()
        self.db.delete(self.handle)

    def put_cert(self, cert_data):
        """
        Add a certificate to the certificate database. Return handle
        :param cert_data: str with DER data
        :return: str handle
        """
        # TODO: method needs testing
        return self.db.put_cert(cert_data)
